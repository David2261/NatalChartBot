import datetime
import os
from admin import admin_only
from dotenv import load_dotenv
import telebot
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from states import is_paid, set_paid, set_state, get_state, get_data, user_states
from calculator import calculate_full_chart
from texts import generate_free_interpretation, generate_paid_interpretation
from payments import send_full_chart_invoice

load_dotenv()

TOKEN = os.getenv("TOKEN")

bot = telebot.TeleBot(TOKEN)


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

	if is_paid(uid):
		bot.answer_callback_query(call.id, "Вы уже оплатили полный разбор", show_alert=True)
		# можно сразу отправить разбор
		chart = get_data(uid).get('chart')
		if chart:
			paid_text = generate_paid_interpretation(chart)
			bot.send_message(chat_id, paid_text, parse_mode='HTML')
		return

	# Отправляем инвойс
	send_full_chart_invoice(bot, chat_id)
	bot.answer_callback_query(call.id, "Открываем оплату...")


@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout_handler(pre_checkout_query):
	"""
	Обязательный обработчик для подтверждения возможности оплаты
	"""
	bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


def send_full_result(bot, chat_id, uid=None):
	"""
	Отправляет полный натальный разбор пользователю.
	
	Аргументы:
		bot: экземпляр telebot.TeleBot
		chat_id: ID чата (обычно message.chat.id)
		uid: ID пользователя (message.from_user.id). Если None — берётся из chat_id (для личных чатов)
	
	Проверяет оплату, наличие рассчитанной карты и отправляет текст.
	"""
	if uid is None:
		uid = chat_id

	# 1. Проверка оплаты
	if not is_paid(uid):
		bot.send_message(
			chat_id,
			"❌ Доступ к полному разбору только после оплаты (100 ★).\n"
			"Нажмите кнопку «Купить полный разбор» ниже."
		)
		return

	# 2. Получаем сохранённые данные
	data = get_data(uid)
	chart = data.get('chart')

	if not chart:
		bot.send_message(
			chat_id,
			"⚠️ Натальная карта не найдена.\n"
			"Пожалуйста, рассчитайте карту заново: /start → «Рассчитать натальную карту»"
		)
		return

	# 3. Генерируем и отправляем полный текст
	try:
		paid_text = generate_paid_interpretation(chart)
		bot.send_message(
			chat_id,
			paid_text,
			parse_mode='HTML',
			disable_web_page_preview=True
		)
		# Опционально: можно добавить кнопку "Рассчитать ещё одну карту"
		markup = InlineKeyboardMarkup()
		markup.add(InlineKeyboardButton("Рассчитать новую карту", callback_data="new_calc"))
		bot.send_message(chat_id, "Хотите рассчитать карту для другого человека?", reply_markup=markup)

	except Exception as e:
		bot.send_message(
			chat_id,
			f"❌ Ошибка при формировании полного разбора: {str(e)}\n"
			"Пожалуйста, попробуйте позже или напишите @support."
		)


@bot.message_handler(content_types=['successful_payment'])
def successful_payment_handler(message):
	uid = message.from_user.id
	chat_id = message.chat.id

	# Помечаем пользователя как оплатившего
	set_paid(uid, message.successful_payment.telegram_payment_charge_id)

	data = get_data(uid)
	chart = data.get('chart')

	if chart:
		bot.send_message(chat_id, "Оплата прошла успешно! 🎉\nВот ваш полный натальный разбор:")
		paid_text = generate_paid_interpretation(chart)
		bot.send_message(chat_id, paid_text, parse_mode='HTML')
	else:
		bot.send_message(
			chat_id,
			"Оплата прошла успешно, но натальная карта не найдена.\n"
			"Пожалуйста, начните расчёт заново (/start)"
		)

	set_state(uid, "START")


# Admin command to broadcast a message to all paid users
@bot.message_handler(commands=['admin', 'stats'])
@admin_only
def admin_stats(message):
	uid = message.from_user.id
	text = f"Статистика на {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
	
	# если есть user_states
	active_users = len([uid for uid in user_states if get_state(uid) != 'START'])
	paid_users = sum(1 for uid in user_states if is_paid(uid))
	
	text += f"Активных сессий: {active_users}\n"
	text += f"Оплативших полный разбор: {paid_users}\n"
	
	bot.reply_to(message, text)


@bot.message_handler(commands=['broadcast'])
@admin_only
def broadcast(message):
	# очень простой вариант — текст после команды
	text = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
	if not text:
		bot.reply_to(message, "Напишите: /broadcast Ваш текст для рассылки")
		return
	
	sent = 0
	for uid in user_states:
		try:
			bot.send_message(uid, text)
			sent += 1
		except:
			pass  # пользователь заблокировал бота или удалил чат
	
	bot.reply_to(message, f"Рассылка завершена. Отправлено: {sent}")


@bot.message_handler(commands=['testpay'])
def testpay(message):
    uid = message.from_user.id
    set_paid(uid, "test123")
    bot.send_message(message.chat.id, "Тест: оплата прошла")
    send_full_result(bot, message.chat.id, uid)


if __name__ == "__main__":
	bot.infinity_polling()
