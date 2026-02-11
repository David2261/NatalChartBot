from __future__ import annotations
from datetime import datetime
import os
from typing import Optional, Dict, Any

try:
	from database import EncryptedDB
except ImportError:
	EncryptedDB = None

# In-memory fallback
_in_memory_states: Dict[int, Dict[str, Any]] = {}
CALLBACK_COOLDOWN: float = 3.5
last_callback_time: Dict[int, datetime] = {}

_db: Optional[EncryptedDB: Any] = None

if EncryptedDB is not None:
	key = os.environ.get("DB_FERNET_KEY")
	db_path = os.environ.get("DB_PATH", "db/data.sqlite")
	if key:
		try:
			_db = EncryptedDB(path=db_path, fernet_key=key)
			_db.init_db()
		except Exception as e:
			print(f"Не удалось инициализировать БД: {e}")
			_db = None


def _ensure_user_exists(telegram_id: int) -> None:
	"""Создаёт запись в users, если её нет (только для БД-режима)"""
	if not _db:
		return
	cur = _db._conn.cursor()
	cur.execute(
		"INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
		(telegram_id,)
	)
	_db._conn.commit()


def get_state(uid: int) -> str:
	if _db:
		state_data = _db.get_state(uid)
		return state_data.get("state") if state_data else "START"
	return _in_memory_states.get(uid, {}).get("state", "START")


def set_state(uid: int, state: str, data: Optional[Dict[str, Any]] = None) -> None:
	if _db:
		_ensure_user_exists(uid)
		
		current = _db.get_state(uid) or {"state": "START", "data": {}}
		new_data = current["data"].copy()
		if data:
			new_data.update(data)
		
		_db.set_state(uid, state, new_data)
		return

	# in-memory режим
	if uid not in _in_memory_states:
		_in_memory_states[uid] = {"state": "START", "data": {}, "paid": False}
	
	_in_memory_states[uid]["state"] = state
	if data:
		_in_memory_states[uid]["data"].update(data)


def get_data(uid: int) -> Dict[str, Any]:
	if _db:
		state_data = _db.get_state(uid)
		return state_data.get("data", {}) if state_data else {}
	return _in_memory_states.get(uid, {}).get("data", {})


def is_paid(uid: int) -> bool:
	if _db:
		state_data = _db.get_state(uid)
		if not state_data:
			return False
		return bool(state_data.get("data", {}).get("paid", False))
	
	user = _in_memory_states.get(uid, {})
	return bool(user.get("paid", False)) or bool(user.get("data", {}).get("paid", False))


def set_paid(uid: int, charge_id: Optional[str] = None) -> None:
	"""charge_id пока не используем, но оставляем для будущего расширения"""
	if _db:
		_ensure_user_exists(uid)
		
		current = _db.get_state(uid) or {"state": "START", "data": {}}
		new_data = current["data"].copy()
		new_data["paid"] = True
		if charge_id:
			new_data["charge_id"] = charge_id
		
		_db.set_state(uid, current["state"], new_data)
		return

	# in-memory
	if uid not in _in_memory_states:
		_in_memory_states[uid] = {"state": "START", "data": {}, "paid": False}
	
	_in_memory_states[uid]["paid"] = True
	if charge_id:
		_in_memory_states[uid]["data"]["charge_id"] = charge_id


def migrate_from_memory(memory_states: Dict[int, Dict[str, Any]]) -> int:
	if not _db:
		raise RuntimeError("База данных не настроена — миграция невозможна.")
	
	count = 0
	for uid, payload in memory_states.items():
		state = payload.get("state")
		data = payload.get("data", {})
		# переносим paid в data, если оно было отдельно
		if payload.get("paid") is True:
			data["paid"] = True
		
		_ensure_user_exists(uid)
		_db.set_state(int(uid), state, data)
		count += 1
	
	return count


def get_all_user_ids() -> list[int]:
	"""
	Возвращает список всех telegram_id, которые есть в хранилище (БД или память).
	"""
	if _db:
		cur = _db._conn.execute("SELECT telegram_id FROM user_states")
		return [row[0] for row in cur.fetchall()]
	
	# in-memory режим
	return list(_in_memory_states.keys())


def get_active_user_count() -> int:
	"""Считает пользователей, у которых состояние ≠ 'START'"""
	count = 0
	for uid in get_all_user_ids():
		if get_state(uid) != "START":
			count += 1
	return count


def get_paid_user_count() -> int:
	"""Считает пользователей с paid = True"""
	count = 0
	for uid in get_all_user_ids():
		if is_paid(uid):
			count += 1
	return count


if __name__ == "__main__":
	import json
	src = "user_states_export.json"
	if os.path.exists(src):
		with open(src, "r", encoding="utf-8") as f:
			data = json.load(f)
		try:
			count = migrate_from_memory(data)
			print(f"Успешно мигрировано {count} пользователей в БД")
		except Exception as e:
			print(f"Ошибка миграции: {e}")
	else:
		print(f"Файл {src} не найден. Поместите JSON-экспорт и запустите снова.")
