import json
import os

CONTENT_DIR = os.path.join(os.path.dirname(__file__), "source")

# Эмодзи планет
PLANET_EMOJI = {
	'Sun': '🌞', 'Moon': '🌙', 'Mercury': '☿', 'Venus': '♀', 'Mars': '♂',
	'Jupiter': '♃', 'Saturn': '♄', 'Uranus': '♅', 'Neptune': '♆', 'Pluto': '♇'
}

# Русские названия аспектов
ASPECT_NAMES_RU = {
	'conj': '☌ соединение',
	'opp': '☍ оппозиция',
	'trine': '△ трин',
	'square': '□ квадратура',
	'sextile': '⚹ секстиль'
}

# Сопоставление типа аспекта → имя файла
ASPECT_TYPE_TO_FILE = {
	'conj': 'conjunction.json',
	'opp': 'opposition.json',
	'trine': 'trine.json',
	'square': 'square.json',
	'sextile': 'sextile.json'
}


def load_json(file_path: str) -> dict:
	full_path = os.path.join(CONTENT_DIR, file_path)
	if not os.path.exists(full_path):
		return {}
	try:
		with open(full_path, 'r', encoding='utf-8') as f:
			return json.load(f)
	except Exception:
		return {}


def deg_to_sign(deg: float) -> str:
	signs = ["Овна", "Тельца", "Близнецов", "Рака", "Льва", "Девы",
			 "Весов", "Скорпиона", "Стрельца", "Козерога", "Водолея", "Рыб"]
	sign_index = int(deg // 30)
	deg_in_sign = deg % 30
	minutes = int((deg_in_sign % 1) * 60)
	return f"{int(deg_in_sign)}°{minutes:02d}' {signs[sign_index]}"


def get_sign_name(deg: float) -> str:
	"""Возвращает название знака на английском (как в JSON ключах)"""
	signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
			 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
	sign_index = int(deg // 30)
	return signs[sign_index]


def get_house(cusps: list, planet_deg: float) -> int:
	if not cusps or len(cusps) < 12:
		return 1

	for i in range(12):
		start = cusps[i]
		end = cusps[(i + 1) % 12]
		
		if start <= end:
			if start <= planet_deg < end:
				return i + 1
		else:
			if planet_deg >= start or planet_deg < end:
				return i + 1
	
	return 1


def get_planet_interpretation(planet: str, sign: str) -> str:
	"""Получает интерпретацию планеты в знаке (первые 3 предложения из JSON)"""
	file = f"planets/{planet.lower()}.json"
	data = load_json(file)
	
	if not data or 'descriptions' not in data:
		return ""
	
	text_list = data['descriptions'].get(sign, [])
	if not text_list:
		return ""
	
	return ' '.join(text_list[:3]) if len(text_list) >= 3 else ' '.join(text_list)


def get_ascendant_interpretation(sign: str) -> str:
	"""Получает интерпретацию Асцендента в знаке (первые 3 предложения из JSON)"""
	data = load_json("ascendant/ascendant.json")
	
	if not data or 'descriptions' not in data:
		return ""
	
	text_list = data['descriptions'].get(sign, [])
	if not text_list:
		return ""
	
	return ' '.join(text_list[:3]) if len(text_list) >= 3 else ' '.join(text_list)


def get_aspect_interpretation(p1: str, p2: str, aspect_type: str, orb: float) -> str:
	"""Получает интерпретацию аспекта (первые 3 предложения, выбирает strong/normal по орбу)"""
	file_name = ASPECT_TYPE_TO_FILE.get(aspect_type)
	if not file_name:
		return ""
	
	data = load_json(f"aspects/{file_name}")
	if not data or 'descriptions' not in data:
		return ""

	# Ключи в JSON: "Sun_Moon", "Mercury_Venus" и т.д. (с капиталью)
	pair_key = f"{p1}_{p2}"
	rev_pair = f"{p2}_{p1}"
	
	entry = data['descriptions'].get(pair_key) or data['descriptions'].get(rev_pair)
	if not entry:
		return ""
	
	intensity = "strong" if orb < 1.0 else "normal"
	text_list = entry.get(intensity, [])
	
	return ' '.join(text_list[:3]) if len(text_list) >= 3 else ' '.join(text_list)


def _sort_aspects(aspects: list) -> list:
	"""
	Сортирует аспекты по важности типа, затем по точности орба.
	
	Порядок важности: conj > opp > square > trine > sextile
	"""
	aspect_priority = {'conj': 0, 'opp': 1, 'square': 2, 'trine': 3, 'sextile': 4}
	
	return sorted(
		aspects,
		key=lambda a: (aspect_priority.get(a['type'], 999), a['orb'])
	)


def _group_planets_by_house(positions: dict, cusps: list) -> dict:
	"""
	Группирует планеты по домам.
	
	Returns:
		{1: [планеты], 2: [планеты], ..., 12: [планеты]}
	"""
	planets_by_house = {i: [] for i in range(1, 13)}
	
	planet_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter',
					'Saturn', 'Uranus', 'Neptune', 'Pluto']
	
	for planet in planet_order:
		if planet in positions:
			house_num = get_house(cusps, positions[planet])
			planets_by_house[house_num].append(planet)
	
	return planets_by_house


def generate_free_interpretation(chart):
	pos = chart['positions']
	asc = chart['asc']
	aspects = chart.get('aspects', [])

	sun_sign = deg_to_sign(pos['Sun'])
	moon_sign = deg_to_sign(pos['Moon'])
	asc_sign = deg_to_sign(asc)

	sun_sign_name = get_sign_name(pos['Sun'])
	moon_sign_name = get_sign_name(pos['Moon'])
	asc_sign_name = get_sign_name(asc)

	sun_text = get_planet_interpretation("sun", sun_sign_name)
	moon_text = get_planet_interpretation("moon", moon_sign_name)
	asc_text = get_ascendant_interpretation(asc_sign_name)

	text = "<b>Краткий предварительный разбор вашей натальной карты</b>\n\n"

	text += f"🌞 <b>Солнце в {sun_sign}</b>\n{sun_text}\n\n"
	text += f"🌙 <b>Луна в {moon_sign}</b>\n{moon_text}\n\n"
	text += f"↑ <b>Асцендент в {asc_sign}</b>\n{asc_text}\n\n"

	if aspects:
		best = min(aspects, key=lambda a: a['orb'])
		p1, p2 = best['p1'], best['p2']
		aspect_text = get_aspect_interpretation(p1, p2, best['type'], best['orb'])
		text += f"<b>Ключевой аспект:</b> {p1} {best['type']} {p2} (орб {best['orb']:.1f}°)\n"
		text += f"{aspect_text}\n\n"

	text += "────────────────────────────\n"
	text += "<i>Это только первые штрихи — как обложка книги.</i>\n\n"
	text += "<b>В полной версии вы получите гораздо больше:</b>\n"
	text += "• все планеты в знаках и домах\n"
	text += "• 7–9 самых важных аспектов с объяснением\n"
	text += "• любовь, секс и партнёрство\n"
	text += "• деньги и карьера\n"
	text += "• теневые стороны и блоки\n"
	text += "• совместимость\n"
	text += "• главная жизненная задача + текущий период (2025–2027)\n\n"
	text += "<b>Хотите увидеть полную картину?</b>\nНажмите кнопку ниже 👇"

	return text


# def generate_paid_interpretation(chart):
# 	"""Полная платная версия"""
# 	pos = chart['positions']
# 	asc = chart['asc']
# 	mc = chart['mc']
# 	cusps = chart['cusps']
# 	aspects = chart.get('aspects', [])

# 	text = "<b>Полный натальный разбор</b>\n\n"

# 	# Планеты в знаках и домах
# 	text += "<b>Планеты в знаках и домах</b>\n"
# 	order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter',
# 			 'Saturn', 'Uranus', 'Neptune', 'Pluto']
# 	planet_emoji = {
# 		'Sun': '🌞', 'Moon': '🌙', 'Mercury': '☿', 'Venus': '♀', 'Mars': '♂',
# 		'Jupiter': '♃', 'Saturn': '♄', 'Uranus': '♅', 'Neptune': '♆', 'Pluto': '♇'
# 	}

# 	for planet in order:
# 		if planet in pos:
# 			deg = pos[planet]
# 			house = get_house(cusps, deg)
# 			text += f"{planet_emoji.get(planet, '')} <b>{planet}</b>: {deg_to_sign(deg)} — {house}-й дом\n"

# 	text += f"\n<b>Асцендент</b>: {deg_to_sign(asc)}\n"
# 	text += f"<b>Середина Неба (MC)</b>: {deg_to_sign(mc)}\n\n"

# 	# Ключевые аспекты
# 	if aspects:
# 		text += "<b>Ключевые аспекты и их влияние</b>\n"
# 		asp_ru = {
# 			'conj': '☌ соединение', 'opp': '☍ оппозиция', 'trine': '△ трин',
# 			'square': '□ квадратура', 'sextile': '⚹ секстиль'
# 		}
# 		for i, asp in enumerate(aspects[:7], 1):
# 			p1, p2 = asp['p1'], asp['p2']
# 			typ = asp_ru.get(asp['type'], asp['type'])
# 			orb = asp['orb']
# 			text += f"{i}. {p1} {typ} {p2} (орб {orb:.1f}°)\n"
# 		text += "\n"

# 	text += "────────────────────────────\n"
# 	text += "<i>Это интерпретация на основе классических правил.</i>"

# 	return text
