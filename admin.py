import os
from functools import wraps
from dotenv import load_dotenv

load_dotenv()
ADMIN_IDS = set(
	int(x.strip()) 
	for x in os.getenv("ADMIN_IDS", "123456789").split(",")
	if x.strip().isdigit()
)


def admin_only(func):
	@wraps(func)
	def wrapper(*args, **kwargs):        
		if args and hasattr(args[0], 'from_user'):
			message_or_call = args[0]
			uid = message_or_call.from_user.id
			bot = args[0].bot if hasattr(args[0], 'bot') else None
		else:
			return func(*args, **kwargs)

		if uid not in ADMIN_IDS:
			if bot and hasattr(message_or_call, 'reply_to'):
				bot.reply_to(message_or_call, "⛔ Доступ запрещён. Вы не администратор.")
			elif bot and hasattr(message_or_call, 'answer_callback_query'):
				bot.answer_callback_query(
					message_or_call.id,
					"⛔ Доступ запрещён. Вы не администратор.",
					show_alert=True
				)
			print(f"[ADMIN DENIED] User {uid} (@{message_or_call.from_user.username or 'no username'}) tried admin command")
			return

		return func(*args, **kwargs)
	
	return wrapper
