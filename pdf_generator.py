import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from calculator import deg_to_sign
from mc_loader import get_mc_interpretation
from texts import ASPECT_NAMES_RU, PLANET_EMOJI, get_ascendant_interpretation, get_aspect_interpretation, get_house, get_planet_interpretation, get_sign_name
from love_ai import get_all_sections

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


def _draw_background_first_page(canvas, doc):
	canvas.saveState()

	page_width, page_height = A4

	canvas.drawImage(
		os.path.join(os.path.dirname(__file__), 'assets', 'main_template.png'),
		0,
		0,
		width=page_width,
		height=page_height,
		preserveAspectRatio=True,
		mask="auto"
	)

	canvas.restoreState()


def _draw_background_other_pages(canvas, doc):
	canvas.saveState()

	w, h = A4
	canvas.drawImage(
		os.path.join(os.path.dirname(__file__), 'assets', 'template_standart.png'),
		0, 0,
		width=w,
		height=h,
		preserveAspectRatio=True,
		mask="auto"
	)

	canvas.restoreState()


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
		rightMargin=10*mm,
		leftMargin=20*mm,
		topMargin=10*mm,
		bottomMargin=10*mm,
	)

	styles = getSampleStyleSheet()

	title_style = ParagraphStyle(
		name='Title',
		fontName='DejaVuBold',
		fontSize=28,
		textColor=colors.white,
		spaceAfter=18,
		alignment=1,
		leading=34
	)

	subtitle_style = ParagraphStyle(
		name='Subtitle',
		fontName='DejaVu',
		fontSize=16,
		textColor=colors.white,
		spaceAfter=12,
		alignment=1
	)

	section_style = ParagraphStyle(
		name='Section',
		fontName='DejaVuBold',
		fontSize=16,
		textColor=colors.white,
		spaceBefore=24,
		spaceAfter=12
	)

	body_style = ParagraphStyle(
		name='Body',
		fontName='DejaVu',
		fontSize=11,
		leading=14,
		textColor=colors.white,
		spaceAfter=8
	)

	small_style = ParagraphStyle(
		name='Small',
		fontName='DejaVu',
		fontSize=9,
		textColor=colors.white,
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

	story.append(Spacer(1, 30*mm))
	story.append(Paragraph("Полный натальный разбор", title_style))
	story.append(Spacer(1, 6*mm))
	story.append(Paragraph("Ваша натальная карта", subtitle_style))
	
	story.append(Spacer(1, 8*mm))

	current_date = datetime.now().strftime("%d.%m.%Y")
	story.append(Paragraph(f"Сгенерировано: {current_date}", small_style))

	story.append(PageBreak())

	# Планеты
	story.append(Paragraph("◎─◯ Планеты в знаках и домах", section_style))
	story.append(Spacer(1, 4*mm))

	planets_by_house = _group_planets_by_house(pos, cusps)

	for house_num in range(1, 13):
		planets_in_house = planets_by_house.get(house_num, [])
		if planets_in_house:
			# Заголовок дома
			story.append(Paragraph(f"<b>Дом {house_num}</b>", ParagraphStyle(
				'HouseHeader',
				parent=body_style,
				fontName='DejaVuBold',
				fontSize=12,
				textColor=colors.white,
			)))
			story.append(Spacer(1, 0.1*cm))
			
			# Планеты в этом доме
			if planets_in_house:
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
			else:
				story.append(Paragraph("Пустой дом — акцент на самостоятельном развитии этой сферы жизни", body_style))
				story.append(Spacer(1, 0.2*cm))

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
	mc_sign_ru = deg_to_sign(mc).split("° ")[-1].strip()
	mc_text = get_mc_interpretation(mc_sign_ru)
	story.append(Paragraph(f"<b>Середина Неба (MC)</b>: {deg_to_sign(mc)}", section_style))
	story.append(Paragraph(mc_text, body_style))

	story.append(PageBreak())

	# Аспекты
	if aspects:
		story.append(Paragraph("☆ Ключевые аспекты и их влияние", section_style))
		story.append(Spacer(1, 4*mm))

		# Сортируем аспекты по важности и орбу
		sorted_aspects = _sort_aspects(aspects)
		
		for i, asp in enumerate(sorted_aspects, 1):
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
	story.append(Paragraph("♥ Любовь, секс и партнёрство", section_style))
	story.append(Spacer(1, 4*mm))

	sections = get_all_sections(chart)
	story.append(KeepTogether([
		Paragraph(sections["love"], body_style)
	]))

	story.append(PageBreak())

	# Деньги и самореализация
	story.append(Paragraph("$ Деньги и самореализация", section_style))
	story.append(Spacer(1, 4*mm))
	story.append(KeepTogether([
		Paragraph(sections["money"], body_style)
	]))

	story.append(PageBreak())

	# Теневые стороны
	story.append(Paragraph("● Теневые стороны и блоки", section_style))
	story.append(Spacer(1, 4*mm))
	story.append(KeepTogether([
		Paragraph(sections["shadow"], body_style)
	]))

	story.append(PageBreak())

	# Главная задача
	story.append(Paragraph("◎ Главная жизненная задача", section_style))
	story.append(Spacer(1, 4*mm))
	story.append(KeepTogether([
		Paragraph(sections["task"], body_style)
	]))

	story.append(Spacer(1, 30*mm))

	# Заключение
	conclusion_text = (
		"Расчёт выполнен с помощью Swiss Ephemeris (Placidus).  <br/><br/>"
		"Спасибо, что позволили заглянуть в вашу карту.  <br/>"
		"Пусть этот разбор станет для вас маленьким светом на пути самопознания.<br/><br/>"
		"Помните: астрология — это инструмент для размышлений, а не руководство к действию.  <br/>"
		"Все решения и ответственность — только ваши.<br/><br/>"
		"С уважением,  <br/>"
		 f"{bot_username}"
	)
	story.append(Paragraph(conclusion_text, ParagraphStyle(
		'Conclusion',
		parent=body_style,
		fontSize=10,
		textColor=colors.HexColor("#2B51BC"),
		alignment=1,
		leading=14
	)))

	# Сборка
	doc.build(
		story,
		onFirstPage=_draw_background_first_page,
		onLaterPages=_draw_background_other_pages
	)
	return pdf_path


if __name__ == "__main__":
	# Пример тестового запуска (можно удалить или закомментировать в продакшене)
	print("Это тестовый запуск генератора PDF натальной карты")
	print("Для реального использования вызывайте функцию create_natal_pdf(...)")
	
	# Пример минимального тестового словаря chart (можно убрать)
	test_chart = {
		'positions': {
			'Sun': 125.4,
			'Moon': 278.9,
			'Mercury': 112.7,
			'Venus': 145.2,
			'Mars': 33.1,
		},
		'asc': 87.3,
		'mc': 195.6,
		'cusps': [85.0, 115.0, 145.0, 175.0, 205.0, 235.0,
				  265.0, 295.0, 325.0, 355.0, 25.0, 55.0],
		'aspects': [
			{'p1': 'Sun', 'p2': 'Moon', 'type': 'opp', 'orb': 2.3},
			{'p1': 'Venus', 'p2': 'Mars', 'type': 'trine', 'orb': 1.1},
		]
	}
	
	try:
		pdf_file = create_natal_pdf(
			chart=test_chart,
			uid="test_user_123",
			user_first_name="Тестовый Пользователь",
			bot_username="@AstroTestBot"
		)
		print(f"PDF успешно создан: {pdf_file}")
	except Exception as e:
		print("Ошибка при создании PDF:")
		print(e)