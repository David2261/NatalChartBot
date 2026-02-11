from __future__ import annotations

import os
import sqlite3
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64
from pathlib import Path

from states import ensure_user_exists

load_dotenv()

DB_FERNET_KEY = os.getenv("DB_FERNET_KEY")

def derive_fernet_key_from_passphrase(passphrase: str, salt: bytes = b"natalbot-salt") -> bytes:
	kdf = PBKDF2HMAC(
		algorithm=hashes.SHA256(),
		length=32,
		salt=salt,
		iterations=390000,
		backend=default_backend(),
	)
	key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
	return key


class EncryptedDB:
	def __init__(self, path: str = "db/data.sqlite", fernet_key: Optional[str] = None):
		self._path = path
		if fernet_key is None:
			env = os.environ.get("DB_FERNET_KEY")
			if env:
				fernet_key = env
		if fernet_key is None:
			raise ValueError("No Fernet key provided. Set DB_FERNET_KEY or pass fernet_key.")

		# Accept either raw 32-byte base64 key or passphrase
		try:
			# If key is valid base64 urlsafe Fernet key, this will succeed
			Fernet(fernet_key)
			self._fernet = Fernet(fernet_key)
		except Exception:
			# Treat as passphrase
			key = derive_fernet_key_from_passphrase(fernet_key)
			self._fernet = Fernet(key)

		# Ensure directory exists
		db_path = Path(self._path)
		if not db_path.parent.exists():
			db_path.parent.mkdir(parents=True, exist_ok=True)

		# Create connection
		self._conn = self._connect()

	def init_db(self) -> None:
		schema_path = os.path.join(os.path.dirname(__file__), "db", "schema.sql")
		if os.path.exists(schema_path):
			with open(schema_path, "r", encoding="utf-8") as f:
				self._conn.executescript(f.read())
		else:
			# Fallback: create minimal tables
			self._conn.execute(
				"""
				CREATE TABLE IF NOT EXISTS user_states (
					telegram_id INTEGER UNIQUE NOT NULL,
					state TEXT,
					data BLOB,
					created_at TEXT DEFAULT (datetime('now')),
					updated_at TEXT DEFAULT (datetime('now'))
				);
				"""
			)
		self._conn.commit()

	def _encrypt(self, plaintext_bytes: bytes) -> bytes:
		return self._fernet.encrypt(plaintext_bytes)

	def _decrypt(self, blob: Optional[bytes]) -> Optional[bytes]:
		if blob is None:
			return None
		try:
			return self._fernet.decrypt(blob)
		except Exception:
			return None
	
	def _connect(self):
		conn = sqlite3.connect(self._path)
		conn.row_factory = sqlite3.Row
		conn.execute("PRAGMA journal_mode=WAL;")
		return conn

	def set_state(self, telegram_id: int, state: Optional[str], data: Optional[Dict[str, Any]]) -> None:
		payload = None
		if data is not None:
			payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
			payload = self._encrypt(payload)

		cur = self._conn.cursor()
		cur.execute(
			"INSERT INTO user_states(telegram_id, state, data, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))"
			" ON CONFLICT(telegram_id) DO UPDATE SET state=excluded.state, data=excluded.data, updated_at=datetime('now')",
			(telegram_id, state, payload),
		)
		self._conn.commit()

	def get_state(self, telegram_id: int) -> Optional[Dict[str, Any]]:
		cur = self._conn.execute("SELECT state, data FROM user_states WHERE telegram_id = ?", (telegram_id,))
		row = cur.fetchone()
		if not row:
			return None
		state = row["state"]
		blob = row["data"]
		dec = self._decrypt(blob)
		data = None
		if dec is not None:
			try:
				data = json.loads(dec.decode("utf-8"))
			except Exception:
				data = None
		return {"state": state, "data": data}

	def migrate_from_memory(self, memory_states: Dict[int, Dict[str, Any]]) -> int:
		"""Migrate an in-memory dict mapping telegram_id -> {state, data}.

		Returns number of rows migrated.
		"""
		count = 0
		for telegram_id, payload in memory_states.items():
			state = payload.get("state")
			data = payload.get("data")
			self.set_state(int(telegram_id), state, data)
			count += 1
		return count

	def close(self) -> None:
		try:
			self._conn.commit()
		except Exception:
			pass
		self._conn.close()

	def __enter__(self) -> "EncryptedDB":
		return self

	def __exit__(self, exc_type, exc, tb) -> None:
		self.close()


if __name__ == "__main__":
	# quick self-test (do not run in production without setting DB_FERNET_KEY)
	key = os.environ.get("DB_FERNET_KEY")
	if not key:
		print("Set DB_FERNET_KEY env var before running this test.")
	else:
		db = EncryptedDB("db/test_data.sqlite", fernet_key=key)
		db.init_db()
		ensure_user_exists(db, 12345)
		db.set_state(12345, "TEST", {"hello": "world"})
		db.close()
