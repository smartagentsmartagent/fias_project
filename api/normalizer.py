"""
Простой нормализатор текста для адресного поиска
"""
import re
import unicodedata
from typing import Dict, Any
from unidecode import unidecode


# Словари и регексы алиасов типов
# Каноническая форма -> варианты написания
ALIASES = {
	# === ЛИНЕЙНЫЕ/УЛИЧНЫЕ ТИПЫ ===
	"ул": ["улица", "ул.", "ул", "ул-ца", "улиц"],
	"пер": ["переулок", "пер.", "пер", "пер-к", "пер-к.", "пер-к"],
	"пр-кт": ["проспект", "просп.", "пр-т", "пр т", "пр-кт", "пр-т.", "пр-кт.", "просп"],
	"б-р": ["бульвар", "бул.", "б-р", "бул", "булв"],
	"пр-д": ["проезд", "пр-д", "прд", "пр-зд", "пр.-д", "пр. д"],
	"пл": ["площадь", "пл.", "пл"],
	"ш": ["шоссе", "ш.", "ш", "шос.", "шс"],
	"наб": ["набережная", "наб.", "наб", "набр.", "набр"],
	"туп": ["тупик", "туп.", "туп"],
	"ал": ["аллея", "ал.", "алея"],
	"дор": ["дорога", "дор.", "дор"],
	"тракт": ["тракт", "тр.", "тркт", "тр-т"],
	"мост": ["мост"],
	"эст": ["эстакада", "эст.", "эст"],
	"п/п": ["путепровод", "путепров.", "п/п", "пп"],
	"съезд": ["съезд", "с/езд"],
	"заезд": ["заезд", "з/езд"],
	"подъезд-авт": ["подъезд (авто)", "подъезд авт", "подъезд авт."],
	"просека": ["просека", "прск", "пр-ка"],
	"просёлок": ["просёлок", "проселок", "прслк", "пр-селок"],
	"линия": ["линия", "лин.", "лин", "линии"],
	"ряд": ["ряд", "ряды"],
	"кольцо": ["кольцо", "клц", "кольц."],
	"автодорога": ["автодорога", "а/д", "автод."],
	"трасса": ["трасса", "трс", "тр."],
	# === ДОРОЖНЫЕ МЕТКИ КИЛОМЕТРА ===
	"км": ["километр", "км", "км."],

	# === Ж/Д ОБЪЕКТЫ ===
	"ж/д ст": [
		"ж/д ст", "ж/д ст.", "жд ст", "жд ст.", "ж д ст", "жд-ст",
		"ж/д станция", "жд станция", "железнодорожная станция", "станция"
	],
	"ж/д пл": [
		"ж/д пл", "ж/д пл.", "жд пл", "жд пл.", "ж д пл",
		"ж/д платформа", "жд платформа", "железнодорожная платформа", "платформа", "платф.", "платф"
	],
	"ж/д рзд": [
		"ж/д рзд", "жд рзд", "ж/д разъезд", "жд разъезд", "разъезд", "рзд", "р/зд"
	],
	"ж/д к": [
		"ж/д к", "жд к", "ж/д казарма", "жд казарма", "казарма"
	],

	# === МИКРОРАЙОНЫ/КВАРТАЛЫ/ЖИЛЫЕ ЕДИНИЦЫ ===
	"мкр": ["микрорайон", "мкр.", "мкр", "мкрн", "м/р", "мкр-н"],
	"кв-л": ["квартал", "кв-л", "кв-л.", "кв.", "кв"],
	"ж/м": ["жилой массив", "жилмассив", "ж/м", "ж.м."],
	"жр": ["жилрайон", "жил. район", "ж/р"],

	# === ТЕРРИТОРИИ/САДОВОДСТВА/ПРОМЗОНЫ ===
	"тер": [
		"территория", "тер.", "тер", "тер-рия", "терр.", "тер-р.",
		"тер. снт", "территория снт", "тер. днт", "тер. днп",
		"промзона", "пром. зона", "п/з", "военный городок", "в/г", "в/городок"
	],
	"сад-во": ["садоводство", "сад-во", "сад-во.", "сад-во"],
	"снт": ["снт", "садоводческое некоммерческое товарищество"],
	"днт": ["днт", "дачное некоммерческое товарищество"],
	"днп": ["днп", "дачное некоммерческое партнёрство", "дачное партнерство"],
	"кп(коттеджный)": ["коттеджный поселок", "коттеджный посёлок", "кп"],

	# === НАСЕЛЁННЫЕ ПУНКТЫ ===
	"г": ["город", "г.", "г"],
	"пгт": ["пгт", "п.г.т.", "поселок городского типа", "посёлок городского типа"],
	"пос": ["посёлок", "поселок", "пос.", "пос", "п."],
	"рп": ["рабочий посёлок", "рабочий поселок", "рп"],
	"дп": ["дачный посёлок", "дачный поселок", "дп"],
	"кп(курортный)": ["курортный посёлок", "курортный поселок", "кп(курортный)", "кп курортный"],
	"п/ст": ["посёлок при станции", "поселок при станции", "п/ст", "ппс"],
	"д": ["деревня", "дер.", "д.", "д"],
	"с": ["село", "с.", "с"],
	"ст-ца": ["станица", "ст-ца", "станица."],
	"сл": ["слобода", "сл.", "сл"],
	"х": ["хутор", "х.", "х"],
	"аул": ["аул"],
	"аал": ["аал"],
	"арбан": ["арбан", "арб"],
	"улус": ["улус"],
	"починок": ["починок", "поч.", "пчк"],
	"кордон": ["кордон"],
	"заимка": ["заимка"],
	"зимовье": ["зимовье"],
	"кишлак": ["кишлак"],
	"юрты": ["юрты"],

	# === АДМИНИСТРАТИВНЫЕ ЕДИНИЦЫ ===
	"р-н": ["район", "р-н", "рн", "р-он"],
	"м/о": ["муниципальный округ", "м/о", "м.о."],
	"вн/тер-г": ["внутригородская территория", "вн/тер-г", "вн.тер.г", "внутригородская территория г."],
	"мр": ["муниципальный район", "м-р", "мр", "муниц. район"],
	"го": ["городской округ", "г.о.", "го", "гор. округ"],
	"с/п": ["сельское поселение", "с/п", "с.п."],
	"с/пос": ["сельское поселение", "с/пос", "с.пос."],
	"г/п": ["городское поселение", "г/п", "г.п."],
	"гп": ["городской поселок", "гп", "г.п."],
	"п/с": ["поселение", "п/с", "п.с."],
	"с/с": ["сельсовет", "с/с", "с.с.", "сельский совет"],
	"с/о": ["сельский округ", "с/о", "с.о."],
	"обл": ["область", "обл.", "обл"],
	"край": ["край", "кр.", "край."],
	"респ": ["республика", "респ.", "респ"],
	"АО": ["автономный округ", "авт. округ", "ао", "АО"],
	"Аобл": ["автономная область", "аобл", "а.обл", "Аобл"],

	# === СОКРАЩЕНИЯ НАЗВАНИЙ УЛИЦ ===  
	"большая": ["б", "больш", "большая"],
	"малая": ["м.", "м", "мал.", "мал", "малая"],
	"средняя": ["ср.", "ср", "сред.", "сред", "средняя"],
	"новая": ["н.", "н", "нов.", "нов", "новая"],
	"старая": ["ст.", "ст", "стар.", "стар", "старая"],
	"верхняя": ["в.", "в", "верх.", "верх", "верхняя"],
	"нижняя": ["ниж.", "ниж", "нижн.", "нижн", "нижняя"],
	"восточная": ["вост.", "вост", "восточн.", "восточн", "восточная"],
	"западная": ["зап.", "зап", "западн.", "западн", "западная"],
	"северная": ["сев.", "сев", "северн.", "северн", "северная"],
	"южная": ["юж.", "юж", "южн.", "южн", "южная"],
	"центральная": ["центр.", "центр", "централь.", "централь", "центральная"],
	"промышленная": ["пром.", "пром", "промышл.", "промышл", "промышленная"],
	"строительная": ["стр.", "строит.", "строит", "строительная"],
	"железнодорожная": ["жд", "ж.д.", "ж/д", "железнодор.", "железнодорожная"],
	"красная": ["кр.", "кр", "красн.", "красн", "красная"],
	"советская": ["сов.", "сов", "совет.", "совет", "советская"],
	"комсомольская": ["комс.", "комс", "комсом.", "комсом", "комсомольская"],
	"пионерская": ["пион.", "пион", "пионер.", "пионер", "пионерская"],
	"октябрьская": ["окт.", "окт", "октябр.", "октябр", "октябрьская"],
	"молодежная": ["мол.", "мол", "молод.", "молод", "молодежная"],
	"школьная": ["шк.", "шк", "школ.", "школ", "школьная"],

	# === ПРОЧЕЕ ===
	"остров": ["остров", "о-в", "о-в."],
	"полуостров": ["полуостров", "п-ов", "п-ов"],
	"берег": ["берег", "брг"],
	"мыс": ["мыс"],
	"урочище": ["урочище", "ур.", "ур."],
}

# Регекс-алиасы для нестрогих/многословных форм
ALIASES_REGEX = [
	# ж/д станция
	(r"^(?:ж[/\s]?д|железнодорожн\w*)\s*ст(анц(ия|ии|и|\.?))$", "ж/д ст"),
	(r"^станц(ия|ии|и|\.?)$", "ж/д ст"),
	# ж/д платформа
	(r"^(?:ж[/\s]?д|железнодорожн\w*)\s*платформ(а|ы|\.?)$", "ж/д пл"),
	(r"^платформ(а|ы|\.?)$", "ж/д пл"),
	# ж/д разъезд
	(r"^(?:ж[/\s]?д|железнодорожн\w*)\s*разъезд(.*)?$", "ж/д рзд"),
	(r"^разъезд(.*)?$", "ж/д рзд"),
	# ж/д казарма
	(r"^(?:ж[/\s]?д|железнодорожн\w*)\s*казарм(а|ы|\.?)$", "ж/д к"),
	# Муниципальный округ / вн.тер.г
	(r"^м\.?/?о\.?$", "м/о"),
	(r"^муниципальн(?:ый|ая)\s+округ$", "м/о"),
	(r"^вн(?:\.|/)?тер(?:\.|-)?г$", "вн/тер-г"),
	# Поселение/совет/округ (сельские)
	(r"^с\.?/?п\.?$", "с/п"),
	(r"^с\.?/?пос\.?$", "с/пос"),
	(r"с/пос", "с/пос"),
	(r"^г\.?/?п\.?$", "г/п"),
	(r"^п\.?/?с\.?$", "п/с"),
	(r"^с\.?/?с\.?$", "с/с"),
	(r"^с\.?/?о\.?$", "с/о"),
	# КП — по умолчанию коттеджный
	(r"^кп$", "кп(коттеджный)"),
	# Числительные с кварталами
	(r"^\d+\s+й\s+кв-л$", "кв-л"),
	(r"^\d+\s+й\s+кв-л-л$", "кв-л"),
	# Сокращения названий улиц
	(r"^б$", "большая"),
	(r"^м$", "малая"),
	(r"^н$", "новая"),
	(r"^ст$", "старая"),
	# Исключение для "с" в контексте "с/пос"
	(r"^с$", "средняя"),
]


def normalize_text(text: str) -> str:
	"""Базовая нормализация текста"""
	if not text:
		return ""
	
	# Unicode NFC нормализация
	text = unicodedata.normalize('NFC', text)
	
	# Приведение к нижнему регистру
	text = text.lower()
	
	# Приведение ё -> е
	text = text.replace('ё', 'е')
	
	# Специальная обработка числительных типа "1-й", "2-й", "3-й" и т.д.
	# Заменяем на "1 й", "2 й", "3 й" для правильной токенизации
	# НО НЕ разрываем окончания прилагательных типа "ая", "ой", "ий"
	text = re.sub(r'(\d+)-й\b', r'\1 й', text)
	text = re.sub(r'(\d+)-я\b(?=\s|$)', r'\1 я', text)  # Только если после "-я" идет пробел или конец строки
	text = re.sub(r'(\d+)-е\b', r'\1 е', text)
	text = re.sub(r'(\d+)-го\b', r'\1 го', text)
	text = re.sub(r'(\d+)-му\b', r'\1 му', text)
	
	# Обрабатываем запятые как разделители - заменяем на пробелы
	text = re.sub(r',\s*', ' ', text)
	
	# Обрабатываем точки в конце слов (ул., пл., пр-кт.) - заменяем на пробелы
	text = re.sub(r'\.(?=\s|$)', ' ', text)
	
	# Обрабатываем точки после сокращений (ул., пл., пр-кт. и т.д.) - заменяем на пробелы
	text = re.sub(r'\.\s+', ' ', text)
	
	# Удаление лишней пунктуации, сохраняем дефис и слэш, но не удаляем точки в середине слов
	text = re.sub(r'[^\w\s\-\/\.]', ' ', text)
	
	# Схлопывание пробелов
	text = re.sub(r'\s+', ' ', text).strip()
	
	return text


def apply_type_aliases(text: str) -> str:
	"""Нормализация типов топонимов по словарям алиасов и регексам.
	Работает по токенам: сначала точные алиасы, затем регексы для сложных форм.
	"""
	if not text:
		return text

	result = text

	# 0) Специальная обработка для "с/пос" перед обработкой "с" как "средняя"
	result = re.sub(r'\bс/пос\b', 'с/пос', result, flags=re.IGNORECASE)

	# 1) Сначала применяем регекс-замены для сложных форм
	# Применяем к фразе целиком для многословных паттернов
	for rx, canon in ALIASES_REGEX:
		if re.search(rx, result, flags=re.IGNORECASE):
			result = re.sub(rx, canon, result, flags=re.IGNORECASE)
	
	# Затем применяем к отдельным токенам для простых паттернов
	tokens = result.split()
	for i, tok in enumerate(tokens):
		# Специальная обработка: не заменяем "с" на "средняя", если за ним следует "/пос"
		if tok.lower() == "с" and i + 1 < len(tokens) and tokens[i + 1].lower() == "пос":
			continue
		for rx, canon in ALIASES_REGEX:
			if re.match(rx, tok, flags=re.IGNORECASE):
				tokens[i] = canon
				break
	result = ' '.join(tokens)

	# 2) Затем применяем точные алиасы, но избегаем повторных замен
	# Сначала применяем алиасы типов улиц (более длинные и специфичные)
	street_type_aliases = []
	other_aliases = []
	
	for canon, variants in ALIASES.items():
		for v in variants:
			# Нормализуем вариант под текущие правила normalize_text
			norm_v = normalize_text(v)
			if not norm_v:
				continue
			# Разделяем алиасы типов улиц и остальные
			if canon in ["ул", "пер", "пр-кт", "б-р", "пр-д", "пл", "ш", "наб", "туп", "ал", "дор", "тракт", "мост", "эст", "п/п", "съезд", "заезд", "подъезд-авт", "просека", "просёлок", "линия", "ряд", "кольцо", "автодорога", "трасса"]:
				street_type_aliases.append((norm_v, canon))
			else:
				other_aliases.append((norm_v, canon))
	
	# Сортировка по длине убыв.
	street_type_aliases.sort(key=lambda x: len(x[0]), reverse=True)
	other_aliases.sort(key=lambda x: len(x[0]), reverse=True)
	
	# Специальная обработка: перемещаем "бульвар" в начало списка типов улиц
	bulvar_aliases = [(pattern, canon) for pattern, canon in street_type_aliases if canon == "б-р"]
	other_street_aliases = [(pattern, canon) for pattern, canon in street_type_aliases if canon != "б-р"]
	street_type_aliases = bulvar_aliases + other_street_aliases
	
	# Специальная обработка: перемещаем "с/пос" в начало списка других алиасов (перед "средняя")
	spos_aliases = [(pattern, canon) for pattern, canon in other_aliases if canon == "с/пос"]
	other_aliases_filtered = [(pattern, canon) for pattern, canon in other_aliases if canon != "с/пос"]
	other_aliases = spos_aliases + other_aliases_filtered
	
	# Специальная обработка: перемещаем "средняя" в начало списка других алиасов
	srednaya_aliases = [(pattern, canon) for pattern, canon in other_aliases if canon == "средняя"]
	other_aliases_filtered = [(pattern, canon) for pattern, canon in other_aliases if canon != "средняя"]
	other_aliases = srednaya_aliases + other_aliases_filtered

	# Применяем замены только один раз для каждого паттерна
	applied_replacements = set()
	
	# Сначала применяем алиасы типов улиц
	for pattern_text, canon in street_type_aliases:
		if pattern_text in applied_replacements:
			continue
		# Границы слова по краям, допускаем дефис/слэш внутри
		escaped = re.escape(pattern_text)
		regex = re.compile(rf"(?<!\w){escaped}(?!\w)", flags=re.IGNORECASE)
		if regex.search(result):
			result = regex.sub(canon, result)
			applied_replacements.add(pattern_text)
	
	# Затем применяем остальные алиасы, но исключаем те, которые могут конфликтовать с уже примененными
	for pattern_text, canon in other_aliases:
		if pattern_text in applied_replacements:
			continue
		# Проверяем, не конфликтует ли этот алиас с уже примененными типами улиц
		skip_this = False
		for applied_pattern in applied_replacements:
			if applied_pattern in pattern_text or pattern_text in applied_pattern:
				skip_this = True
				break
		if skip_this:
			continue
		# Границы слова по краям, допускаем дефис/слэш внутри
		escaped = re.escape(pattern_text)
		regex = re.compile(rf"(?<!\w){escaped}(?!\w)", flags=re.IGNORECASE)
		if regex.search(result):
			result = regex.sub(canon, result)
			applied_replacements.add(pattern_text)

	# Специальная обработка для числительных с кварталами
	result = re.sub(r'\b\d+\s+й\s+кв-л-л\b', 'кв-л', result)
	result = re.sub(r'\b\d+\s+й\s+кв-л\b', 'кв-л', result)
	
	# Исправляем повторные применения алиаса "кв-л"
	result = re.sub(r'\bкв-л-л\b', 'кв-л', result)
	
	return result


def extract_house_number(text: str) -> Dict[str, Any]:
	"""Извлечение номера дома из текста"""
	# Приводим возможные латинские буквы к русским для единообразия (k->к, c->с)
	text = re.sub(r'k', 'к', text, flags=re.IGNORECASE)
	text = re.sub(r'c', 'с', text, flags=re.IGNORECASE)

	# Обрабатываем запятые как разделители - заменяем на пробелы
	text = re.sub(r',\s*', ' ', text)

	# Специальная обработка для названий улиц с числами
	# Известные названия улиц, которые содержат числа как часть названия
	street_names_with_numbers = [
		"8 марта", "1 мая", "9 января", "7 ноября", "3 декабря", "5 августа", 
		"2 апреля", "6 марта", "4 июля", "10 октября", "12 декабря", "15 марта",
		"20 лет октября", "25 лет октября", "30 лет победы", "40 лет победы",
		"50 лет октября", "60 лет октября", "70 лет октября", "100 лет октября"
	]
	
	# Специальная обработка для микрорайонов с названиями улиц
	# Если в запросе есть "1 Мая мкр", то это микрорайон, а не улица "1 мая"
	microdistrict_patterns = [
		"1 мая мкр", "1 мая мкр.", "1 мая микрорайон", "1 мая мкрн"
	]
	
	# Проверяем, содержит ли текст название улицы с числом
	# НО НЕ исключаем извлечение номера дома, если после названия улицы есть отдельное число
	text_lower = text.lower()
	
	# Сначала проверяем, есть ли микрорайоны с названиями улиц
	for microdistrict_pattern in microdistrict_patterns:
		if microdistrict_pattern.lower() in text_lower:
			# Это микрорайон, а не улица - не исключаем извлечение номера дома
			break
	else:
		# Проверяем обычные названия улиц с числами
		for street_name in street_names_with_numbers:
			if street_name.lower() in text_lower:
				# Проверяем, есть ли после названия улицы отдельное число (номер дома)
				street_name_pattern = re.escape(street_name.lower())
				# Ищем паттерн: название улицы + пробел + число (не часть названия)
				house_number_after_street = re.search(
					rf'\b{street_name_pattern}\s+(\d+)\b', 
					text_lower
				)
				if house_number_after_street:
					# Есть номер дома после названия улицы - извлекаем его
					house_number = house_number_after_street.group(1)
					# Удаляем номер дома из текста
					text_without_house = re.sub(
						rf'\b{street_name_pattern}\s+{house_number}\b', 
						street_name, 
						text_lower
					)
					return {
						"text_without_house": re.sub(r'\s+', ' ', text_without_house).strip(),
						"house_number": house_number,
						"korpus": None,
						"stroenie": None,
						"has_house": True
					}
				else:
					# Проверяем, есть ли отдельное число в конце запроса (например, "17")
					# Ищем число в конце строки, которое не является частью названия улицы
					end_number_match = re.search(r'\b(\d+)\s*$', text_lower)
					if end_number_match:
						house_number = end_number_match.group(1)
						# Удаляем номер дома из текста
						text_without_house = re.sub(r'\b\d+\s*$', '', text_lower).strip()
						return {
							"text_without_house": re.sub(r'\s+', ' ', text_without_house).strip(),
							"house_number": house_number,
							"korpus": None,
							"stroenie": None,
							"has_house": True
						}
					else:
						# Нет отдельного номера дома - не извлекаем
						return {
							"text_without_house": re.sub(r'\s+', ' ', text).strip(),
							"house_number": None,
							"korpus": None,
							"stroenie": None,
							"has_house": False
						}

	# Упрощенная логика: определяем, является ли число номером дома
	# Основной принцип: если после типа улицы идет число, то это номер дома
	street_types = ['ул', 'пер', 'пр-кт', 'б-р', 'пр-д', 'пл', 'ш', 'наб', 'туп', 'ал', 'дор', 'тракт', 'мост', 'эст', 'п/п', 'съезд', 'заезд', 'подъезд-авт', 'просека', 'просёлок', 'линия', 'ряд', 'кольцо', 'автодорога', 'трасса']
	has_street_type_before_number = False
	
	# Проверяем, не является ли это числительным с кварталом
	is_quarter_with_number = bool(re.search(r'\b\d+\s+й\s+кв-л\b', text))
	
	# Проверяем, есть ли тип улицы перед числом в середине текста (это не номер дома)
	# Но исключаем случаи, когда это компактная форма номера дома (например, "37с5")
	for st in street_types:
		# Ищем паттерн "тип_улицы число что-то_еще" (не номер дома)
		if re.search(r'\b' + re.escape(st) + r'\.?\s+\d+\s+\w+', text):
			# Проверяем, не является ли это компактной формой номера дома
			match = re.search(r'\b' + re.escape(st) + r'\.?\s+(\d+[кс]\d+)', text)
			if not match:  # Если это не компактная форма, то это не номер дома
				has_street_type_before_number = True
				break

	# Исключение порядковых числительных в названии улицы перед типом
	# Примеры: "3 й новомихалковский пр-д", "1 я тверская ул", "2 е кольцо"
	# Если перед типом улицы стоит шаблон N й/я/е <слово>, то это часть названия, а не номер дома
	ordinal_street_pattern = re.compile(r'(\b\d+\s*(?:й|я|е)\b\s+\w+\s+(?:' + '|'.join([re.escape(st) for st in street_types]) + r')\b)', re.IGNORECASE)
	if ordinal_street_pattern.search(text):
		return {
			"text_without_house": re.sub(r'\s+', ' ', text).strip(),
			"house_number": None,
			"korpus": None,
			"stroenie": None,
			"has_house": False
		}

	# Вставляем пробелы в компактных формах: 49к4 -> 49 к 4, 49с1 -> 49 с 1, 49к4с2 -> 49 к 4 с 2
	# Делаем несколько проходов, чтобы разорвать обе связки
	# НО НЕ разрываем слова, где к/с являются частью слова
	text = re.sub(r'(\d)\s*[к]\s*(\d)(?=\s|$)', r'\1 к \2', text, flags=re.IGNORECASE)
	text = re.sub(r'(\d)\s*[с]\s*(\d)(?=\s|$)', r'\1 с \2', text, flags=re.IGNORECASE)
	
	# Специальная обработка для случаев типа "33/19с1" - разрываем "с1" на "с 1"
	# НО НЕ разрываем окончания прилагательных типа "ая", "ой", "ий"
	# Исключаем случаи, когда после буквы идет цифра, но это не окончание прилагательного
	text = re.sub(r'([а-я])\s*(\d)(?=\s|$)', r'\1 \2', text, flags=re.IGNORECASE)
	
	# Специальная обработка для сложных номеров домов типа "16А/1", "25К1/2"
	# Сохраняем оригинальный номер дома с дробью как единое целое
	text = re.sub(r'(\d+[а-я]?)\s*/\s*(\d+)', r'\1/\2', text, flags=re.IGNORECASE)
	
	# Специальная обработка для числительных с кварталами - не считать их номером дома
	text = re.sub(r'\b(\d+)-й\s+кв-л\b', r'\1 й кв-л', text)

	# Маскируем километраж, чтобы не принять его за номер дома: "65-й километр", "65 км", "километр 65"
	text_km_safe = text
	text_km_safe = re.sub(r'\b(\d+)[\-–—‑]?й?\s*(?:км|километр)\b', ' километр ', text_km_safe, flags=re.IGNORECASE)
	text_km_safe = re.sub(r'\b(?:км|километр)\s*(\d+)\b', ' километр ', text_km_safe, flags=re.IGNORECASE)

	# Алиасы
	corp_alias = r'(?:корпус|корп|кор\.?|к)'
	bldg_alias = r'(?:строение|стр\.?|с)'
	house_alias = r'(?:дом|д)'
	# Также поддержим «владение» как синоним строения для фильтрации
	own_alias = r'(?:владение|влад\.?|вл)'

	# Шаблоны для поиска номера дома в любом месте строки. Поддерживаются разные порядки (корп/стр меняются местами)
	base_num = r'(?:' + house_alias + r'\.?\s*)?(\d+[абвгдежзийклмнопрстуфхцчшщъыьэюя]?)'
	corp_num = r'(?:\s*(?:' + corp_alias + r')\.?\s*(\d+[абвгдежзийклмнопрстуфхцчшщъыьэюя]?))'
	bldg_num = r'(?:\s*(?:' + bldg_alias + r'|' + own_alias + r')\.?\s*(\d+[абвгдежзийклмнопрстуфхцчшщъыьэюя]?))'

	pattern1 = re.compile(r'\b' + base_num + r'(?:' + corp_num + r')?(?:' + bldg_num + r')?', re.IGNORECASE)
	pattern2 = re.compile(r'\b' + base_num + r'(?:' + bldg_num + r')?(?:' + corp_num + r')?', re.IGNORECASE)

	# Если обнаружен тип улицы перед числом, не ищем номер дома
	if has_street_type_before_number:
		return {
			"text_without_house": text,
			"house_number": None,
			"korpus": None,
			"stroenie": None,
			"has_house": False
		}
	
	# Специальная обработка для сложных номеров домов с дробью типа "16А/1", "25К1/2"
	complex_house_pattern = re.compile(r'\b(\d+[а-я]?/\d+)\b', re.IGNORECASE)
	complex_match = complex_house_pattern.search(text_km_safe)
	if complex_match:
		house_num = complex_match.group(1)
		matched_fragment = complex_match.group(0)
		low = text.lower()
		mf_low = matched_fragment.lower()
		start_idx = low.find(mf_low)
		end_idx = start_idx + len(matched_fragment) if start_idx >= 0 else None
		if start_idx >= 0 and end_idx is not None:
			text_without_house = (text[:start_idx] + ' ' + text[end_idx:]).strip()
		else:
			text_without_house = text
		text_without_house = re.sub(r'\s+', ' ', text_without_house)
		
		# Дополнительно ищем строение в оставшемся тексте
		stroenie_match = re.search(r'\bс\s+(\d+[a-zа-я]?)\b', text_without_house, flags=re.IGNORECASE)
		stroenie = None
		if stroenie_match:
			stroenie = stroenie_match.group(1)
			# Удаляем строение из текста
			s, e = stroenie_match.span()
			text_without_house = (text_without_house[:s] + ' ' + text_without_house[e:]).strip()
			text_without_house = re.sub(r'\s+', ' ', text_without_house)
		
		return {
			"text_without_house": text_without_house,
			"house_number": house_num,
			"korpus": None,
			"stroenie": stroenie,
			"has_house": True
		}
	
	# Находим все совпадения и берем самое правое
	match = None
	last_end = -1
	for m in pattern1.finditer(text_km_safe):
		if m.end() > last_end:
			match = m
			last_end = m.end()
	for m in pattern2.finditer(text_km_safe):
		if m.end() > last_end:
			match = m
			last_end = m.end()
	
	if match:
		house_num = match.group(1)
		# Группы 2 и 3 соответствуют corp и bldg, но порядок может меняться в зависимости от сработавшего паттерна
		grp2 = match.group(2) if len(match.groups()) >= 2 else None
		grp3 = match.group(3) if len(match.groups()) >= 3 else None
		korpus = grp2
		stroenie = grp3
		
		# Удаляем найденный фрагмент (дом/корп/стр) из текста. Позиции находим по исходному тексту
		matched_fragment = match.group(0)
		low = text.lower()
		mf_low = matched_fragment.lower()
		start_idx = low.find(mf_low)
		end_idx = start_idx + len(matched_fragment) if start_idx >= 0 else None
		if start_idx >= 0 and end_idx is not None:
			text_without_house = (text[:start_idx] + ' ' + text[end_idx:]).strip()
		else:
			text_without_house = text
		text_without_house = re.sub(r'\s+', ' ', text_without_house)
		
		return {
			"text_without_house": text_without_house,
			"house_number": house_num,
			"korpus": korpus,
			"stroenie": stroenie,
			"has_house": True
		}
	
	# Фоллбек: если дом не найден, но указано владение (вл/влад/владение N) — интерпретируем как строение
	own_only = re.search(r'\b(?:владение|влад\.?|вл)\s*(\d+[a-zа-я]?)\b', text, flags=re.IGNORECASE)
	if own_only:
		s, e = own_only.span()
		text_wo = (text[:s] + ' ' + text[e:]).strip()
		text_wo = re.sub(r'\s+', ' ', text_wo)
		return {
			"text_without_house": text_wo,
			"house_number": None,
			"korpus": None,
			"stroenie": own_only.group(1),
			"has_house": True
		}
	
	# Специальная обработка для компактных форм владения типа "вл10"
	own_compact = re.search(r'\bвл(\d+[a-zа-я]?)\b', text, flags=re.IGNORECASE)
	if own_compact:
		s, e = own_compact.span()
		text_wo = (text[:s] + ' ' + text[e:]).strip()
		text_wo = re.sub(r'\s+', ' ', text_wo)
		return {
			"text_without_house": text_wo,
			"house_number": None,
			"korpus": None,
			"stroenie": own_compact.group(1),
			"has_house": True
		}
	
	# Специальная обработка для случаев типа "33/19с1" - если в тексте осталось "с N", интерпретируем как строение
	stroenie_match = re.search(r'\bс\s+(\d+[a-zа-я]?)\b', text, flags=re.IGNORECASE)
	if stroenie_match:
		s, e = stroenie_match.span()
		text_wo = (text[:s] + ' ' + text[e:]).strip()
		text_wo = re.sub(r'\s+', ' ', text_wo)
		return {
			"text_without_house": text_wo,
			"house_number": None,
			"korpus": None,
			"stroenie": stroenie_match.group(1),
			"has_house": True
		}

	return {
		"text_without_house": text,
		"house_number": None,
		"korpus": None,
		"stroenie": None,
		"has_house": False
	}


def normalize_query(query: str) -> Dict[str, Any]:
	"""Полная нормализация поискового запроса"""
	if not query:
		return {
			"original": "",
			"normalized": "",
			"text_without_house": "",
			"house_number": None,
			"korpus": None,
			"stroenie": None,
			"has_house": False,
			"has_moscow": False
		}
	
	# Базовая нормализация
	normalized = normalize_text(query)
	
	# Проверяем, есть ли "москва" в исходном запросе
	has_moscow = bool(re.search(r'\bмосква\b', query, flags=re.IGNORECASE))
	
	# Проверяем, есть ли "московская область" в исходном запросе
	has_moscow_region = bool(re.search(r'\bмосковская\s+область\b', query, flags=re.IGNORECASE))
	
	# Проверяем, есть ли "балашиха" в исходном запросе
	has_balashikha = bool(re.search(r'\bбалашиха\b', query, flags=re.IGNORECASE))
	
	# Проверяем, есть ли "ленинградская область" в исходном запросе
	has_leningrad_region = bool(re.search(r'\bленинградская\s+область\b', query, flags=re.IGNORECASE))
	
	# Удаляем "москва" из запроса для поиска (но сохраняем в оригинале для фильтрации)
	normalized_for_search = re.sub(r'\bмосква\b', '', normalized, flags=re.IGNORECASE).strip()
	normalized_for_search = re.sub(r'\s+', ' ', normalized_for_search).strip(' ,')
	
	# Если после удаления "москва" строка стала пустой, вернем оригинал
	if not normalized_for_search:
		normalized_for_search = normalized
	
	# Извлечение номера дома (из текста без "москва")
	house_info = extract_house_number(normalized_for_search)
	
	# Применяем алиасы типов к полному тексту
	normalized = apply_type_aliases(normalized)
	
	# Нормализация текста без дома (также без "москва")
	text_normalized = normalize_text(house_info["text_without_house"])
	# Применяем алиасы типов к тексту без дома
	text_normalized = apply_type_aliases(text_normalized)
	
	# Специальная обработка для запросов с типом улицы в начале и алиасами
	# Например, "ул большая дмитровка" -> "дмитровка большая ул"
	tokens = text_normalized.split()
	if len(tokens) >= 3 and tokens[0] in ["ул", "пер", "пр-кт", "б-р", "пр-д", "пл", "ш", "наб", "туп", "ал", "дор", "тракт", "мост", "эст", "п/п", "линия", "ряд", "кольцо", "автодорога", "трасса"]:
		street_type = tokens[0]
		street_name_tokens = tokens[1:]
		
		# Проверяем, есть ли алиасы в названии улицы
		alias_keywords = {"большая", "малая", "средняя", "новая", "старая", "верхняя", "нижняя", "восточная", "западная", "северная", "южная", "центральная", "промышленная", "строительная", "железнодорожная", "красная", "советская", "комсомольская", "пионерская", "октябрьская", "молодежная", "школьная"}
		
		# Проверяем, есть ли числительные в названии улицы
		numerical_keywords = {"первой", "второй", "третьей", "четвертой", "пятой", "шестой", "седьмой", "восьмой", "девятой", "десятой", "одиннадцатой", "двенадцатой", "тринадцатой", "четырнадцатой", "пятнадцатой", "шестнадцатой", "семнадцатой", "восемнадцатой", "девятнадцатой", "двадцатой", "первого", "второго", "третьего", "четвертого", "пятого", "шестого", "седьмого", "восьмого", "девятого", "десятого", "одиннадцатого", "двенадцатого", "тринадцатого", "четырнадцатого", "пятнадцатого", "шестнадцатого", "семнадцатого", "восемнадцатого", "девятнадцатого", "двадцатого"}
		
		if len(street_name_tokens) == 2 and street_name_tokens[0] in alias_keywords:
			# Переставляем слова: "ул большая дмитровка" -> "дмитровка большая" (без типа улицы)
			text_normalized = f"{street_name_tokens[1]} {street_name_tokens[0]}"
		elif len(street_name_tokens) == 2 and street_name_tokens[0] in numerical_keywords:
			# Переставляем слова: "ал первой маевки" -> "маевки первой" (без типа улицы)
			text_normalized = f"{street_name_tokens[1]} {street_name_tokens[0]}"
	# Специальная обработка для числительных с кварталами в тексте без дома
	text_normalized = re.sub(r'\b\d+\s+й\s+кв-л-л\b', 'кв-л', text_normalized)
	text_normalized = re.sub(r'\b\d+\s+й\s+кв-л\b', 'кв-л', text_normalized)
	# Дополнительная очистка от остатков "й кв-л-л"
	text_normalized = re.sub(r'\bй\s+кв-л-л\b', 'кв-л', text_normalized)
	# Исправляем повторные применения алиаса "кв-л"
	text_normalized = re.sub(r'\bкв-л-л\b', 'кв-л', text_normalized)
	
	return {
		"original": query,
		"normalized": normalized,
		"text_without_house": text_normalized,
		"house_number": house_info["house_number"],
		"korpus": house_info["korpus"],
		"stroenie": house_info["stroenie"],
		"has_house": house_info["has_house"],
		"has_moscow": has_moscow,
		"has_moscow_region": has_moscow_region,
		"has_balashikha": has_balashikha,
		"has_leningrad_region": has_leningrad_region
	}
