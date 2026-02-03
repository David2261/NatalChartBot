import os
from dotenv import load_dotenv
from telebot.types import LabeledPrice

load_dotenv()

PRICE_STARS = int(os.getenv("PRICE_STARS", "100"))


def send_full_chart_invoice(bot, chat_id):
	"""
	Отправляет инвойс на оплату полного натального разбора (Telegram Stars / XTR)
	"""
	prices = [LabeledPrice(label="Полный натальный разбор", amount=PRICE_STARS)]

	bot.send_invoice(
		chat_id=chat_id,
		title="Полный натальный разбор",
		description="Все планеты в знаках и домах, ключевые аспекты, "
					"отношения, деньги и карьера, кармические темы, главная жизненная задача",
		invoice_payload=f"natal_full_{chat_id}_{os.urandom(4).hex()}",
		provider_token="",
		currency="XTR",
		prices=prices,
	)
