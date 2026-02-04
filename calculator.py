import swisseph as swe
from datetime import datetime
from geopy.geocoders import Nominatim

swe.set_ephe_path('./ephe')

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

def calculate_full_chart(data):
	# Парсинг даты/времени
	dt_str = f"{data['birth_date']} {data.get('birth_time', '12:00')}"
	dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")

	year, month, day, hour, minute = dt.year, dt.month, dt.day, dt.hour, dt.minute
	
	jd = swe.utc_to_jd(year, month, day, hour, minute, 0, swe.GREG_CAL)[1]
	
	# Координаты
	geolocator = Nominatim(user_agent="natal_chart_bot")
	loc = geolocator.geocode(data['place'], timeout=10)
	if not loc:
		raise ValueError("Место не найдено")
	lat = loc.latitude
	lon = loc.longitude
	data['lat'] = lat
	data['lon'] = lon
	
	# Планеты
	positions = {}
	for name, pid in PLANETS.items():
		xx = swe.calc_ut(jd, pid)[0]
		positions[name] = xx[0] % 360
	
	# Дома Placidus
	cusps, ascmc = swe.houses(jd, lat, lon, b'P')  # b'P' → Placidus
	asc = ascmc[0] % 360
	mc = ascmc[1] % 360
	
	# Простые аспекты (MVP: major только)
	aspects = []
	orb = {'conj': 8, 'opp': 8, 'trine': 6, 'square': 6, 'sextile': 4}
	planet_list = list(positions.keys())
	for i in range(len(planet_list)):
		for j in range(i+1, len(planet_list)):
			p1, p2 = planet_list[i], planet_list[j]
			diff = min(abs(positions[p1] - positions[p2]), 360 - abs(positions[p1] - positions[p2]))
			for asp_name, asp_angle in [('conj', 0), ('sextile', 60), ('square', 90), ('trine', 120), ('opp', 180)]:
				if abs(diff - asp_angle) <= orb.get(asp_name, 5):
					aspects.append({
						'p1': p1, 'p2': p2, 'type': asp_name, 'diff': diff, 'orb': abs(diff - asp_angle)
					})
	
	return {
		'positions': positions,
		'asc': asc,
		'mc': mc,
		'cusps': cusps[:13],  # дома 1-12
		'aspects': sorted(aspects, key=lambda x: x['orb'])[:7]  # 7 ближайших
	}
