# NatalChartBot

Telegram bot that generates natal charts and astrological reports in PDF format.
Built with Python 3.11, SQLite (with encrypted fields), and ReportLab.

The bot collects user birth data, generates a natal chart report, and delivers a structured PDF file directly in Telegram.

---

## Features

* Telegram bot interface (pyTelegramBotAPI)
* Natal chart report generation in PDF (ReportLab)
* Encrypted storage of sensitive user data (Fernet + PBKDF2)
* SQLite database with WAL mode
* Persistent user state management
* Migration from in-memory state to database
* Environment-based configuration
* Designed for Linux server deployment

---

## Tech Stack

* **Python 3.11**
* **pyTelegramBotAPI (TeleBot)**
* **SQLite**
* **cryptography (Fernet, PBKDF2HMAC)**
* **ReportLab**
* **python-dotenv**

---

## Project Structure

```
NatalChartBot/
│
├── bot.py                # Telegram bot entry point
├── database.py           # Encrypted SQLite database logic
├── db/
│   └── schema.sql        # Database schema
│   └── data.sqlite       # SQLite database (generated)
├── assets/               # Templates and static resources
├── .env                  # Environment variables
└── requirements.txt
```

---

## Installation

### 1. Clone repository

```bash
git clone https://github.com/yourusername/NatalChartBot.git
cd NatalChartBot
```

### 2. Create virtual environment

```bash
poetry install
source venv/bin/activate
```

---

## Environment Variables

Create a `.env` file in the project root.

### Required variables

```
BOT_TOKEN=your_telegram_bot_token
DB_FERNET_KEY=your_fernet_key_or_passphrase
```

### Generating Fernet Key

You can generate a secure key with:

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

Alternatively, you may use a strong passphrase. The system will derive a Fernet key using PBKDF2.

---

## Database

* SQLite in WAL mode
* Foreign key constraints enabled
* Sensitive fields encrypted using Fernet
* User states persisted in `user_states` table
* Designed to replace in-memory dictionaries
* Supports migration from in-memory state

Example stored data:

* Telegram ID
* Current user state
* Encrypted JSON payload

---

## Running Locally

```bash
python bot.py
```

The bot runs in polling mode.

Make sure:

* BOT_TOKEN is valid
* DB_FERNET_KEY is set
* Database is initialized (`init_db()` is called)

---

## Production Deployment Notes

* Recommended OS: Linux
* Run inside virtual environment
* Use systemd service for auto-restart
* Restrict server access (SSH keys only)
* Ensure database file permissions are limited
* Rotate encryption keys carefully (requires migration strategy)

For higher scale:

* Replace SQLite with PostgreSQL
* Use Redis for ephemeral state
* Move to webhook mode behind reverse proxy

---

## Security Considerations

* Sensitive fields encrypted at rest
* No plaintext birth data stored in database
* WAL mode for safer concurrent access
* Avoid storing excessive historical state
* Consider adding TTL cleanup for old user states

This project assumes server-level security is properly configured.

---

## Example .env

```
PRICE_STARS =
TOKEN = tg_bot_token
ADMIN_IDS = your_ids
DB_FERNET_KEY=your_generated_fernet_key_here
```