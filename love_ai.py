"""
Генератор разделов натальной карты
с использованием локальной LLM (LM Studio / OpenAI-compatible).

Генерирует ровно 4 фиксированных раздела:
- Любовь, секс и партнёрство
- Деньги и самореализация
- Теневые стороны и блоки
- Главная жизненная задача

Работает полностью локально, без внешних API.
"""

import asyncio
from typing import Dict

import aiohttp

from calculator import deg_to_sign
from texts import get_house


MODEL_NAME = "qwen2.5-3b-instruct"
LM_API_URL = "http://127.0.0.1:1234/v1/chat/completions"

REQUEST_TIMEOUT = 360
TEMPERATURE = 0.3
MAX_TOKENS = 300


FALLBACK_TEXTS: Dict[str, str] = {
	"love": (
		"Ваша Венера в 9-м доме показывает, каких людей вы привлекаете. "
		"Луна в 11-м доме подчёркивает потребность в эмоциональной близости и принятии. "
		"Важно учиться честному диалогу и балансу между желаниями и реальными возможностями."
	),
	"money": (
		"Положение Юпитера указывает на потенциал роста через развитие навыков и настойчивость. "
		"Финансовая устойчивость приходит через осознанный выбор направления и терпение."
	),
	"shadow": (
		"Внутренние противоречия могут проявляться как стремление к контролю и страх утраты стабильности. "
		"Проработка этих тем ведёт к большей гибкости и доверию к себе."
	),
	"task": (
		"Ваша задача — соединить рациональность и интуицию, развивая уверенность в своей уникальности. "
		"Реализация приходит через глубокую и осмысленную помощь другим."
	)
}


SECTION_CONFIG: Dict[str, Dict[str, str]] = {
	"love": {
		"title": "💕 Любовь, секс и партнёрство",
		"themes": "привлекательность, тип партнёров, эмоциональные потребности, баланс, сексуальность",
		"forbidden": "предсказания, фатализм, мистика"
	},
	"money": {
		"title": "💰 Деньги и самореализация",
		"themes": "карьера, стабильность, рост, настойчивость, направление",
		"forbidden": "гарантии успеха, предсказания, фатализм"
	},
	"shadow": {
		"title": "⚫ Теневые стороны и блоки",
		"themes": "контроль, страхи, напряжение, проработка, принятие",
		"forbidden": "негативные прогнозы, мистика, фатализм"
	},
	"task": {
		"title": "🎯 Главная жизненная задача",
		"themes": "уверенность, уникальность, развитие, смысл, рост",
		"forbidden": "судьба, предназначение, предсказания"
	}
}


def _extract_chart_facts(chart: Dict, section: str) -> str:
	facts = []

	try:
		pos = chart.get("positions", {})
		cusps = chart.get("cusps", [])
		aspects = chart.get("aspects", [])

		if section == "love":
			facts.append(
				f"Венера в {get_house(cusps, pos.get('Venus', 0))}-м доме, "
				f"знак {deg_to_sign(pos.get('Venus', 0)).split('°')[-1].strip()}"
			)
			facts.append(
				f"Луна в {get_house(cusps, pos.get('Moon', 0))}-м доме, "
				f"знак {deg_to_sign(pos.get('Moon', 0)).split('°')[-1].strip()}"
			)

		elif section == "money":
			facts.append(
				f"Юпитер в {get_house(cusps, pos.get('Jupiter', 0))}-м доме, "
				f"знак {deg_to_sign(pos.get('Jupiter', 0)).split('°')[-1].strip()}"
			)

		elif section == "shadow":
			facts.append(f"Сатурн в {get_house(cusps, pos.get('Saturn', 0))}-м доме")
			facts.append(f"Плутон в {get_house(cusps, pos.get('Pluto', 0))}-м доме")
			tense = [f"{a['p1']} {a['type']} {a['p2']}" for a in aspects if a.get("type") in ("square", "opp", "conjunction")]
			if tense:
				facts.append(f"Напряжённые аспекты (max 3): {', '.join(tense[:3])}")

		elif section == "task":
			facts.append(
				f"Солнце в {get_house(cusps, pos.get('Sun', 0))}-м доме, "
				f"знак {deg_to_sign(pos.get('Sun', 0)).split('°')[-1].strip()}"
			)
			facts.append(
				f"Асцендент: {deg_to_sign(chart.get('asc', 0)).split('°')[-1].strip()}"
			)

	except Exception:
		facts.append("Базовые данные карты доступны")

	return "\n".join(f"- {f}" for f in facts)


def _build_prompt(section: str, chart: Dict) -> str:
	cfg = SECTION_CONFIG[section]
	facts = _extract_chart_facts(chart, section).strip()
	
	return f"""Опиши, как положения {section} раздела проявляются в психологии и поведении человека.

Факты из карты:
{facts if facts else "Базовые положения планет доступны"}

Основные темы для раскрытия: {cfg['themes']}

Пиши ровно 8–10 предложений.
Начинай сразу с текста.
Строго соблюдай все ограничения из системного промпта.
"""


async def generate_section(section: str, chart: Dict, session: aiohttp.ClientSession) -> str:
	"""
	Generate one section with a shared ClientSession.
	
	Note: socket timeouts count from last byte received, not request start.
	With 360s sock_read, very long responses (300+ tokens in Russian) may timeout
	between TCP packets. We add explicit total timeout to catch this.
	"""
	if section not in FALLBACK_TEXTS:
		return FALLBACK_TEXTS["love"]
	
	messages = [
		{
			"role": "system",
			"content": "Ты астролог. Пишешь тёплые интерпретации на русском, от второго лица, 8–12 предложений, позитивно, без негатива и предсказаний."
		},
		{
			"role": "user",
			"content": f"Напиши интерпретацию раздела '{section}'.\nФакты:\n{_extract_chart_facts(chart, section)}\nТемы: {SECTION_CONFIG[section]['themes']}\nЗапрещено: {SECTION_CONFIG[section]['forbidden']}\nНачать сразу с текста."
		}
	]

	payload = {
		"model": MODEL_NAME,
		"messages": messages,
		"temperature": TEMPERATURE,
		"max_tokens": MAX_TOKENS,
		"stream": False
	}
	
	try:
		async with session.post(
			LM_API_URL,
			json=payload,
			timeout=aiohttp.ClientTimeout(
				total=REQUEST_TIMEOUT,
				connect=30,
				sock_connect=30,
				sock_read=REQUEST_TIMEOUT
			)
		) as resp:
			if resp.status == 200:
				data = await resp.json()
				text = data["choices"][0]["message"]["content"].strip()
				if len(text) > 50:
					return text
			else:
				print(f"[{section}] Server returned {resp.status}")

	except asyncio.TimeoutError:
		print(f"[{section}] Request timeout (total={REQUEST_TIMEOUT}s). LM Studio may be overloaded or slow.")
	except ConnectionError as e:
		print(f"[{section}] Connection error: {e}. Check LM Studio is running at {LM_API_URL}")
	except Exception as e:
		print(f"[{section}] Ошибка генерации: {type(e).__name__}: {e}")

	return FALLBACK_TEXTS[section]


async def generate_all_sections(chart: Dict) -> Dict[str, str]:
	sections = ["love", "money", "shadow", "task"]
	results = {}
	
	async with aiohttp.ClientSession() as session:
		for section in sections:
			text = await generate_section(section, chart, session)
			results[section] = text
			# Small delay between requests to let server recover
			await asyncio.sleep(1)
	
	return results


def get_all_sections(chart: Dict) -> Dict[str, str]:
	return asyncio.run(generate_all_sections(chart))


if __name__ == "__main__":
	dummy_chart = {
		"positions": {
			"Sun": 120,
			"Moon": 45,
			"Venus": 98,
			"Mars": 180,
			"Jupiter": 200,
			"Saturn": 320
		},
		"cusps": [0, 10, 35, 65, 90, 115, 140, 190, 215, 245, 270, 295, 320],
		"asc": 10,
		"aspects": [
			{"p1": "Venus", "p2": "Mars", "type": "square"},
			{"p1": "Jupiter", "p2": "Saturn", "type": "opp"}
		]
	}

	sections = get_all_sections(dummy_chart)

	for key, text in sections.items():
		print(f"\n{SECTION_CONFIG[key]['title']}")
		print("-" * 70)
		print(text)
