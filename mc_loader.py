import os
import json
from typing import Optional


_SIGN_TO_FILE = {
	'aries': 'aries.json', 'овен': 'aries.json', 'овен': 'aries.json', 'овен': 'aries.json',
	'taurus': 'taurus.json', 'телец': 'taurus.json',
	'gemini': 'gemini.json', 'близнецы': 'gemini.json',
	'cancer': 'cancer.json', 'рак': 'cancer.json',
	'leo': 'leo.json', 'лев': 'leo.json',
	'virgo': 'virgo.json', 'дева': 'virgo.json',
	'libra': 'libra.json', 'весы': 'libra.json',
	'scorpio': 'scorpio.json', 'скорпион': 'scorpio.json',
	'sagittarius': 'sagittarius.json', 'стрелец': 'sagittarius.json',
	'capricorn': 'capricorn.json', 'козерог': 'capricorn.json',
	'aquarius': 'aquarius.json', 'водолей': 'aquarius.json',
	'pisces': 'pisces.json', 'рыбы': 'pisces.json'
}

_DEF_MSG = "Интерпретация для данного знака недоступна."


def get_mc_interpretation(sign_name: str) -> str:
	"""Возвращает текст интерпретации MC для переданного имени знака.

	sign_name может быть на русском или английском языке, в любом регистре.
	Если файл не найден или чтение не удалось — возвращается дефолтное сообщение.
	"""
	if not sign_name:
		return _DEF_MSG

	key = sign_name.strip().lower()
	filename = _SIGN_TO_FILE.get(key)
	if not filename:
		return _DEF_MSG

	path = os.path.join(os.path.dirname(__file__), 'source', 'mc', filename)
	try:
		with open(path, 'r', encoding='utf-8') as f:
			data = json.load(f)
			return data.get('interpretation', _DEF_MSG)
	except Exception:
		return _DEF_MSG
