import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from calculator import deg_to_sign
from texts import ASPECT_NAMES_RU, PLANET_EMOJI, get_ascendant_interpretation, get_aspect_interpretation, get_house, get_planet_interpretation, get_sign_name

FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
TEMP_DIR = os.path.join(os.path.dirname(__file__), 'temp')

# Регистрация шрифтов (вызывается один раз при импорте)
try:
	pdfmetrics.registerFont(TTFont('DejaVu', os.path.join(FONTS_DIR, 'DejaVuSans.ttf')))
	pdfmetrics.registerFont(TTFont('DejaVuBold', os.path.join(FONTS_DIR, 'DejaVuSans-Bold.ttf')))
except Exception as e:
	print(f"Ошибка загрузки шрифтов: {e}. Используется стандартный шрифт.")


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


def create_natal_pdf(chart, uid, user_first_name, bot_username):
	"""
	Создаёт PDF с полным натальным разбором.
	
	Возвращает путь к файлу или поднимает исключение при ошибке.
	"""
	os.makedirs(TEMP_DIR, exist_ok=True)
	
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	pdf_filename = f"natal_chart_{uid}_{timestamp}.pdf"
	pdf_path = os.path.join(TEMP_DIR, pdf_filename)

	doc = SimpleDocTemplate(
		pdf_path,
		pagesize=A4,
		rightMargin=15*mm,
		leftMargin=15*mm,
		topMargin=20*mm,
		bottomMargin=20*mm
	)

	styles = getSampleStyleSheet()

	title_style = ParagraphStyle(
		name='Title',
		fontName='DejaVuBold',
		fontSize=28,
		textColor=colors.HexColor('#1E3A8A'),
		spaceAfter=18,
		alignment=1,
		leading=34
	)

	subtitle_style = ParagraphStyle(
		name='Subtitle',
		fontName='DejaVu',
		fontSize=16,
		textColor=colors.HexColor('#6D28D9'),
		spaceAfter=12,
		alignment=1
	)

	section_style = ParagraphStyle(
		name='Section',
		fontName='DejaVuBold',
		fontSize=16,
		textColor=colors.HexColor('#1E3A8A'),
		spaceBefore=24,
		spaceAfter=12
	)

	body_style = ParagraphStyle(
		name='Body',
		fontName='DejaVu',
		fontSize=11,
		leading=14,
		spaceAfter=8
	)

	small_style = ParagraphStyle(
		name='Small',
		fontName='DejaVu',
		fontSize=9,
		textColor=colors.grey,
		alignment=1,
		spaceBefore=30
	)

	story = []

	# Извлекаем данные из chart
	pos = chart['positions']
	asc = chart['asc']
	mc = chart['mc']
	cusps = chart['cusps']
	aspects = chart.get('aspects', [])

	# Обложка
	story.append(Spacer(1, 40*mm))

	logo_path = os.path.join(os.path.dirname(__file__), '..', 'bot_logo.png')
	if os.path.exists(logo_path):
		try:
			story.append(Image(logo_path, width=60*mm, height=60*mm, kind='proportional'))
			story.append(Spacer(1, 10*mm))
		except:
			pass

	story.append(Paragraph("Полный натальный разбор", title_style))
	story.append(Spacer(1, 6*mm))
	story.append(Paragraph("Ваша натальная карта", subtitle_style))
	story.append(Spacer(1, 20*mm))

	story.append(Paragraph(f"<b>{user_first_name}</b>", ParagraphStyle(
		name='Name',
		parent=body_style,
		fontSize=14,
		fontName='DejaVuBold',
		alignment=1
	)))
	story.append(Spacer(1, 8*mm))

	current_date = datetime.now().strftime("%d.%m.%Y")
	story.append(Paragraph(f"Сгенерировано: {current_date}", small_style))

	story.append(PageBreak())

	# Планеты
	story.append(Paragraph("🪐 Планеты в знаках и домах", section_style))
	story.append(Spacer(1, 4*mm))

	planets_by_house = _group_planets_by_house(pos, cusps)
	
	# Выводим планеты, сгруппированные по домам (1-12)
	for house_num in range(1, 13):
		planets_in_house = planets_by_house.get(house_num, [])
		if planets_in_house:
			# Заголовок дома
			story.append(Paragraph(f"<b>Дом {house_num}</b>", ParagraphStyle(
				'HouseHeader',
				parent=body_style,
				fontName='DejaVuBold',
				fontSize=12,
				textColor=colors.HexColor('#2D5A8C')
			)))
			story.append(Spacer(1, 0.1*cm))
			
			# Планеты в этом доме
			for planet in planets_in_house:
				deg = pos[planet]
				sign_name = get_sign_name(deg)
				sign_full = deg_to_sign(deg)
				emoji = PLANET_EMOJI.get(planet, '★')
				
				# Заголовок планеты
				planet_header = f"{emoji} <b>{planet}</b> в {sign_full}"
				story.append(Paragraph(planet_header, ParagraphStyle(
					'PlanetHeader',
					parent=body_style,
					fontName='DejaVuBold',
					fontSize=11
				)))
				
				# Интерпретация планеты
				planet_text = get_planet_interpretation(planet, sign_name)
				if planet_text:
					story.append(Paragraph(planet_text, body_style))
				
				story.append(Spacer(1, 0.15*cm))

	# Асцендент
	asc_sign_name = get_sign_name(asc)
	asc_sign_full = deg_to_sign(asc)
	asc_text = get_ascendant_interpretation(asc_sign_name)
	
	story.append(Spacer(1, 0.3*cm))
	story.append(Paragraph(f"↑ <b>Асцендент</b> в {asc_sign_full}", ParagraphStyle(
		'AscHeader',
		parent=body_style,
		fontName='DejaVuBold',
		fontSize=11
	)))
	
	if asc_text:
		story.append(Paragraph(asc_text, body_style))
	
	story.append(Spacer(1, 0.3*cm))
	story.append(Paragraph(f"☊ <b>Середина Неба (MC)</b>: {deg_to_sign(mc)}", body_style))

	story.append(PageBreak())

	# Аспекты
	if aspects:
		story.append(Paragraph("☆ Ключевые аспекты и их влияние", section_style))
		story.append(Spacer(1, 4*mm))

		# Сортируем аспекты по важности и орбу
		sorted_aspects = _sort_aspects(aspects)
		
		for i, asp in enumerate(sorted_aspects[:7], 1):
			p1, p2 = asp['p1'], asp['p2']
			typ = ASPECT_NAMES_RU.get(asp['type'], asp['type'])
			orb = asp['orb']

			story.append(Paragraph(f"{i}. {p1} {typ} {p2} (орб {orb:.1f}°)", body_style))

			interp = get_aspect_interpretation(p1, p2, asp['type'], orb)
			if interp:
				story.append(Paragraph(interp, body_style))
				story.append(Spacer(1, 2*mm))

		story.append(PageBreak())

	# Любовь, секс и партнёрство
	story.append(Paragraph("💕 Любовь, секс и партнёрство", section_style))
	story.append(Spacer(1, 4*mm))

	if 'Venus' in pos and 'Moon' in pos:
		venus_house = get_house(cusps, pos['Venus'])
		moon_house = get_house(cusps, pos['Moon'])
		story.append(Paragraph(
			f"Ваша Венера в {venus_house}-м доме показывает, каких людей вы привлекаете. "
			f"Луна в {moon_house}-м доме добавляет эмоциональный фон. "
			"Сейчас важно учиться балансу между «хочу» и «могу дать».",
			body_style
		))

	story.append(PageBreak())

	# Деньги и самореализация
	story.append(Paragraph("💰 Деньги и самореализация", section_style))
	story.append(Spacer(1, 4*mm))

	tenth_planets = planets_by_house.get(10, [])
	if tenth_planets:
		story.append(Paragraph(
			f"Скопление в 10-м доме ({', '.join(tenth_planets)}) указывает на большой потенциал в карьере. "
			"Вы можете достигать стабильности через упорство и правильный выбор направления.",
			body_style
		))
	else:
		story.append(Paragraph("10-й дом и его управитель указывают на ваш профессиональный путь.", body_style))

	story.append(PageBreak())

	# Теневые стороны
	story.append(Paragraph("⚫ Теневые стороны и блоки", section_style))
	story.append(Spacer(1, 4*mm))
	story.append(Paragraph(
		"Перфекционизм, страх потери контроля, внутренний бунт vs. желание стабильности. "
		"Проработка: принятие несовершенства, работа с гневом и доверием.",
		body_style
	))

	story.append(PageBreak())

	# Главная задача
	story.append(Paragraph("🎯 Главная жизненная задача", section_style))
	story.append(Spacer(1, 4*mm))
	story.append(Paragraph(
		"Развить уверенность в своей уникальности, сочетать аналитический ум с интуицией. "
		"Менять мир через точечную, глубокую помощь другим.",
		body_style
	))

	story.append(Spacer(1, 30*mm))

	# Заключение
	conclusion_text = (
		"Расчёт выполнен с помощью Swiss Ephemeris (Placidus).  <br/><br/>"
		"Спасибо, что позволили заглянуть в вашу карту.  <br/>"
		"Пусть этот разбор станет для вас маленьким светом на пути самопознания.<br/><br/>"
		"Помните: астрология — это инструмент для размышлений, а не руководство к действию.  <br/>"
		"Все решения и ответственность — только ваши.<br/><br/>"
		"С уважением,  <br/>"
		 f"@{bot_username}"
	)
	story.append(Paragraph(conclusion_text, ParagraphStyle(
		'Conclusion',
		parent=body_style,
		fontSize=10,
		textColor=colors.HexColor('#1E3A8A'),
		alignment=1,
		leading=14
	)))

	# Сборка
	doc.build(story)
	return pdf_path
