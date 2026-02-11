import datetime
import os
import threading
import time
from time import time as now_time
from admin import admin_only
from dotenv import load_dotenv
from pdf_generator import create_natal_pdf
import telebot
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import telebot.apihelper as apihelper
from states import get_active_user_count, get_paid_user_count, is_paid, set_paid, set_state, get_state, get_data, last_callback_time, CALLBACK_COOLDOWN
from calculator import calculate_full_chart
from texts import generate_free_interpretation
from payments import send_full_chart_invoice

load_dotenv()

TOKEN = os.getenv("TOKEN")

apihelper.API_TIMEOUT = 1000
apihelper.RETRY_ON_ERROR = True
apihelper.RETRY_DELAY = 2
apihelper.MAX_RETRIES = 5

bot = telebot.TeleBot(TOKEN)


def _generate_and_send_pdf(bot, chat_id, uid, chart, user_first_name, bot_username):
	pdf_path = None
	try:
		pdf_path = create_natal_pdf(
			chart,
			uid,
			user_first_name,
			bot_username
		)

		for attempt in range(1, 4):
			try:
				with open(pdf_path, "rb") as f:
					bot.send_document(
						chat_id,
						f,
						caption="Ваш полный натальный разбор в PDF\nСкачайте и сохраните ❤️",
						timeout=90 + attempt * 30
					)
				break

			except Exception as e:
				if attempt == 3:
					raise
				bot.send_message(chat_id, f"Попытка {attempt} не удалась, пробую ещё раз...")
				time.sleep(3)

	except Exception as e:
		bot.send_message(
			chat_id,
			f"❌ Ошибка при отправке PDF:\n{e}"
		)

	finally:
		if pdf_path and os.path.exists(pdf_path):
			os.remove(pdf_path)


@bot.message_handler(commands=['start'])
def start(message):
	uid = message.from_user.id
	set_state(uid, 'START')
	markup = ReplyKeyboardMarkup(resize_keyboard=True)
	markup.add("Рассчитать натальную карту")
	bot.send_message(message.chat.id, "Привет! Я рассчитаю твою натальную карту.", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "Рассчитать натальную карту")
def begin_calc(m):
	uid = m.from_user.id
	set_state(uid, "WAIT_DATE")
	bot.send_message(m.chat.id, "Введите дату рождения в формате ДД.ММ.ГГГГ")


@bot.message_handler(func=lambda m: get_state(m.from_user.id) == "WAIT_DATE")
def handle_date(m):
	uid = m.from_user.id
	get_data(uid)['birth_date'] = m.text
	set_state(uid, "WAIT_TIME")
	bot.send_message(m.chat.id, "Введите время рождения (ЧЧ:ММ) или 'не знаю'")


@bot.message_handler(func=lambda m: get_state(m.from_user.id) == "WAIT_TIME")
def handle_time(m):
	uid = m.from_user.id
	time_input = m.text.lower().strip()
	if time_input == "не знаю":
		get_data(uid)['birth_time'] = "12:00"
	else:
		get_data(uid)['birth_time'] = time_input
	set_state(uid, "WAIT_PLACE")
	bot.send_message(m.chat.id, "Введите место рождения (город, страна)")


@bot.message_handler(func=lambda m: get_state(m.from_user.id) == "WAIT_PLACE")
def handle_place(m):
	uid = m.from_user.id
	user_data = get_data(uid)
	user_data['place'] = m.text

	set_state(uid, "CALCULATING")
	msg = bot.send_message(m.chat.id, "Расчитываю карту... ⏳")

	try:
		chart_data = calculate_full_chart(user_data)
		user_data['chart'] = chart_data
		bot.edit_message_text("Готово!", m.chat.id, msg.message_id)
		
		free_text = generate_free_interpretation(chart_data)
		bot.send_message(m.chat.id, free_text, parse_mode='HTML')
		
		markup = InlineKeyboardMarkup()
		markup.add(InlineKeyboardButton("Купить полный разбор", callback_data="buy_full"))
		bot.send_message(m.chat.id, "Хотите увидеть полный разбор?", reply_markup=markup)
		
		set_state(uid, "SHOWING_RESULT")
	except Exception as e:
		bot.send_message(m.chat.id, f"Ошибка при расчёте: {e}")
		set_state(uid, "START")


@bot.callback_query_handler(func=lambda call: call.data == "buy_full")
def handle_buy_full(call):
	uid = call.from_user.id
	chat_id = call.message.chat.id
	user_first_name = call.from_user.first_name or ""

	now = now_time()

	# Проверяем кулдаун
	if uid in last_callback_time and now - last_callback_time[uid] < CALLBACK_COOLDOWN:
		bot.answer_callback_query(
			call.id,
			text="Подождите 3–4 секунды перед повторным нажатием",
			show_alert=False,
			cache_time=1
		)
		return

	last_callback_time[uid] = now

	user_first_name = call.from_user.first_name or ""

	if is_paid(uid):
		bot.answer_callback_query(call.id, "Вы уже оплатили полный разбор", show_alert=True)
		# Отправляем разбор если уже оплачено
		chart = get_data(uid).get('chart')
		if chart:
			try:
				bot_info = bot.get_me()
				bot_username = bot_info.username or "natal_chart_bot"
				
				pdf_path = create_natal_pdf(chart, uid, user_first_name, bot_username)
				
				with open(pdf_path, 'rb') as pdf_file:
					bot.send_document(
						chat_id,
						pdf_file,
						caption="Ваш полный натальный разбор в PDF"
					)
				
				os.remove(pdf_path)
			except Exception as e:
				bot.send_message(chat_id, f"Ошибка при создании PDF: {str(e)}")
		return

	# Отправляем инвойс
	try:
		send_full_chart_invoice(bot, chat_id)
		bot.answer_callback_query(call.id, "Открываем оплату...")
	except Exception as e:
		bot.answer_callback_query(call.id, f"Ошибка: {str(e)}", show_alert=True)
		print(f"Ошибка при send_invoice для {uid}: {e}")


@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_handler(pre_checkout_query):
	"""
	Обязательный обработчик для подтверждения возможности оплаты
	"""
	bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


def send_full_result(bot, chat_id, uid=None):
	"""
	Отправляет полный натальный разбор пользователю в виде PDF (без таймаутов).
	"""
	if uid is None:
		uid = chat_id

	# Проверка оплаты
	if not is_paid(uid):
		bot.send_message(
			chat_id,
			"❌ Доступ к полному разбору только после оплаты (100 ★).\n"
			"Нажмите кнопку «Купить полный разбор» ниже."
		)
		return

	data = get_data(uid)
	chart = data.get("chart")

	if not chart:
		bot.send_message(
			chat_id,
			"⚠️ Натальная карта не найдена.\n"
			"Пожалуйста, рассчитайте карту заново."
		)
		return

	user_first_name = data.get("user_first_name", "")

	try:
		bot_info = bot.get_me()
		bot_username = bot_info.username or "natal_chart_bot"
	except Exception:
		bot_username = "natal_chart_bot"

	bot.send_message(
		chat_id,
		"⏳ Формирую ваш полный натальный разбор.\n"
		"Это займет около 5–10 минут."
	)

	threading.Thread(
		target=_generate_and_send_pdf,
		args=(bot, chat_id, uid, chart, user_first_name, bot_username),
		daemon=True
	).start()


@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
	uid = message.from_user.id
	chat_id = message.chat.id
	user_first_name = message.from_user.first_name or ""

	set_paid(uid, message.successful_payment.telegram_payment_charge_id)

	data = get_data(uid)
	chart = data.get('chart')

	if not chart:
		bot.send_message(chat_id, "Оплата прошла, но карта не найдена. Начните заново (/start)")
		set_state(uid, "START")
		return

	loading_msg = bot.send_message(
		chat_id, 
		"✅ Оплата прошла успешно! 🎉\n\n"
		"🔄 *Генерирую ваш PDF-разбор...*\n"
		"⏳ Это займет несколько секунд\n"
		"⏳ Подготавливаю данные...",
		parse_mode="Markdown"
	)

	try:
		bot_info = bot.get_me()
		bot.edit_message_text(
			"✅ Оплата прошла успешно! 🎉\n\n"
			"🔄 *Генерирую ваш PDF-разбор...*\n"
			"⏳ Формирую натальную карту...",
			chat_id,
			loading_msg.message_id,
			parse_mode="Markdown"
		)
		bot_username = bot_info.username or "natal_chart_bot"

		pdf_path = create_natal_pdf(chart, uid, user_first_name, bot_username)

		bot.edit_message_text(
			"✅ *PDF успешно создан!*\n📤 Отправляю файл...",
			chat_id,
			loading_msg.message_id,
			parse_mode="Markdown"
		)

		with open(pdf_path, 'rb') as pdf_file:
			bot.send_document(
				chat_id,
				pdf_file,
				caption="Ваш полный натальный разбор в PDF\nСкачайте и сохраните ❤️",
				filename=f"natal_chart_{user_first_name}.pdf"
			)

		os.remove(pdf_path)

	except Exception as e:
		bot.send_message(chat_id, f"Ошибка при создании PDF: {str(e)}\nНапишите администратору.")

	set_state(uid, "START")


@bot.message_handler(commands=['admin', 'stats'])
@admin_only
def admin_stats(message):
	from datetime import datetime

	text = f"Статистика на {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

	active = get_active_user_count()
	paid = get_paid_user_count()

	text += f"Активных сессий: {active}\n"
	text += f"Оплативших полный разбор: {paid}\n"

	bot.reply_to(message, text)


@bot.message_handler(commands=['broadcast'])
@admin_only
def broadcast(message):
	if len(message.text.split()) <= 1:
		bot.reply_to(message, "Напишите: /broadcast Ваш текст для рассылки")
		return

	text = message.text.split(maxsplit=1)[1]
	sent = 0
	failed = 0

	bot.reply_to(message, "Рассылка запущена... Это может занять время.")

	for uid in list(user_states.keys()):
		try:
			bot.send_message(uid, text)
			sent += 1
		except Exception as e:
			failed += 1

		time.sleep(0.35)

	bot.reply_to(message, f"Рассылка завершена.\nОтправлено: {sent}\nНе удалось: {failed}")

@bot.message_handler(commands=['info', 'информация', 'помощь', 'help'])
def bot_info(message):
	uid = message.from_user.id
	text = (
		"🌟 <b>Натальный чарт-бот</b> 🌟\n\n"
		"Я помогаю рассчитать твою натальную карту и понять, как звёзды влияют на твою жизнь.\n\n"
		"<b>Что умеет бот:</b>\n"
		"• Бесплатно рассчитывает натальную карту по дате, времени и месту рождения\n"
		"• Даёт краткую бесплатную интерпретацию (аспекты, планеты в домах, стихии)\n"
		"• Предлагает купить <b>полный профессиональный разбор</b> в PDF (100 ★)\n"
		"  → 8-10 страниц детального текста\n"
		"  → Совместимость, прогрессии, синастрия (по запросу), рекомендации\n\n"
		"<b>Как пользоваться:</b>\n"
		"1. Нажми «Рассчитать натальную карту»\n"
		"2. Введи дату → время → место рождения\n"
		"3. Получи бесплатный обзор\n"
		"4. Если захочешь глубже — купи полный разбор за 100 Telegram Stars\n\n"
		"Все данные хранятся только до конца сессии или до /start\n\n"
		"Приятного исследования себя! ✨"
	)
	
	bot.send_message(
		message.chat.id,
		text,
		parse_mode='HTML',
		disable_web_page_preview=True
	)


# @bot.message_handler(commands=['testpay'])
# def testpay(message):
# 	uid = message.from_user.id
# 	set_paid(uid, "test123")
# 	bot.send_message(message.chat.id, "Тест: оплата прошла")
# 	send_full_result(bot, message.chat.id, uid)


if __name__ == "__main__":
	bot.infinity_polling()
