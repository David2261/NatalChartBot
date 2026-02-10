import swisseph as swe
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

swe.set_ephe_path('./ephe')

tf = TimezoneFinder(in_memory=True)

PLANETS = {
	'Sun': swe.SUN, 'Moon': swe.MOON, 'Mercury': swe.MERCURY,
	'Venus': swe.VENUS, 'Mars': swe.MARS, 'Jupiter': swe.JUPITER,
	'Saturn': swe.SATURN, 'Uranus': swe.URANUS, 'Neptune': swe.NEPTUNE,
	'Pluto': swe.PLUTO
}

SIGNS = ['Овен', 'Телец', 'Близнецы', 'Рак', 'Лев', 'Дева',
		 'Весы', 'Скорпион', 'Стрелец', 'Козерог', 'Водолей', 'Рыбы']

def deg_to_sign(deg):
	sign_idx = int(deg // 30)
	deg_in_sign = deg % 30
	return f"{deg_in_sign:.1f}° {SIGNS[sign_idx]}"

def calculate_full_chart(data: dict) -> dict:
	"""
	Рассчитывает натальную карту с учётом часового пояса.
	
	Аргументы:
		data: словарь с ключами
			- birth_date: str в формате "ДД.ММ.ГГГГ"
			- birth_time: str в формате "ЧЧ:ММ" (локальное время)
			- place: str (название места, например "Киев, Украина")
	
	Возвращает:
		dict с positions, asc, mc, cusps, aspects
	"""
	# Парсинг даты и локального времени
	dt_str = f"{data['birth_date']} {data.get('birth_time', '12:00')}"
	try:
		dt_local_naive = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
	except ValueError as e:
		raise ValueError(f"Неверный формат даты/времени: {dt_str}. Ожидается ДД.ММ.ГГГГ ЧЧ:ММ") from e

	# Получаем координаты места
	geolocator = Nominatim(user_agent="natal_chart_bot")
	try:
		loc = geolocator.geocode(data['place'], timeout=10)
		if not loc:
			raise ValueError(f"Место не найдено: {data['place']}")
		
		lat = loc.latitude
		lon = loc.longitude
		data['lat'] = lat
		data['lon'] = lon
	except (GeocoderTimedOut, GeocoderUnavailable) as e:
		raise RuntimeError(f"Ошибка геокодирования: {e}. Попробуйте позже или уточните место.")

	# Определяем часовой пояс по координатам
	timezone_str = tf.timezone_at(lat=lat, lng=lon)
	if not timezone_str:
		timezone_str = 'UTC'

	tz = pytz.timezone(timezone_str)

	# Делаем локальное время aware и конвертируем в UTC
	dt_local = tz.localize(dt_local_naive, is_dst=None)  # is_dst=None → использует исторические правила
	dt_utc = dt_local.astimezone(pytz.utc)

	year, month, day, hour, minute = dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour, dt_utc.minute

	# Юлианский день в UTC
	jd = swe.utc_to_jd(year, month, day, hour, minute, 0, swe.GREG_CAL)[1]

	# Позиции планет (тропические, геоцентрические)
	positions = {}
	for name, pid in PLANETS.items():
		try:
			xx = swe.calc_ut(jd, pid)[0]
			positions[name] = xx[0] % 360
		except Exception as e:
			print(f"Ошибка расчёта {name}: {e}")
			positions[name] = 0.0

	# Дома Placidus + Asc + MC
	try:
		cusps, ascmc = swe.houses(jd, lat, lon, b'P')
		asc = ascmc[0] % 360
		mc  = ascmc[1] % 360
	except Exception as e:
		raise RuntimeError(f"Ошибка расчёта домов: {e}")

	# Major аспекты (MVP)
	aspects = []
	orb_limits = {'conj': 8, 'opp': 8, 'trine': 6, 'square': 6, 'sextile': 4}
	planet_list = list(positions.keys())

	for i in range(len(planet_list)):
		for j in range(i + 1, len(planet_list)):
			p1, p2 = planet_list[i], planet_list[j]
			diff = min(abs(positions[p1] - positions[p2]), 360 - abs(positions[p1] - positions[p2]))

			for asp_name, asp_angle in [
				('conj',    0),
				('sextile', 60),
				('square',  90),
				('trine',   120),
				('opp',     180)
			]:
				orb = abs(diff - asp_angle)
				if orb <= orb_limits.get(asp_name, 5):
					aspects.append({
						'p1': p1,
						'p2': p2,
						'type': asp_name,
						'diff': diff,
						'orb': orb
					})

	# Сортируем по точности орба и берём топ-7
	aspects = sorted(aspects, key=lambda x: x['orb'])[:7]

	return {
		'positions': positions,
		'asc': asc,
		'mc': mc,
		'cusps': cusps[:13],
		'aspects': aspects,
	}
