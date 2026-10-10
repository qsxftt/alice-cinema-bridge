# -*- coding: utf-8 -*-
"""
core/nlu.py - Распознавание естественной речи: студии озвучек, сезоны, серии, очистка названий, команды выхода, YouTube
"""

import re

VOICEOVER_STUDIOS = {
    'kubik': {
        'display_name': 'Кубик в кубе',
        'speech_patterns': [r'кубик[а-я]*\s+в\s+кубе', r'кубик[еауом]*', r'кубика', r'кубики', r'кубиком', r'kubik'],
        'tracker_keywords': ['кубик в кубе', 'kubik', 'кубик']
    },
    'lostfilm': {
        'display_name': 'LostFilm',
        'speech_patterns': [r'лост\s*фильм[а-я]*', r'лостфильм[а-я]*', r'лост[еауом]*', r'lostfilm'],
        'tracker_keywords': ['lostfilm', 'лостфильм', 'лост фильм']
    },
    'syenduk': {
        'display_name': 'Сыендук',
        'speech_patterns': [r'сыендук[а-я]*', r'sndk'],
        'tracker_keywords': ['сыендук', 'sndk', 'сыендука']
    },
    'novafilm': {
        'display_name': 'NovaFilm',
        'speech_patterns': [
            r'нов[а-я]*\s+фильм[а-я]*', 
            r'нова\s*фильм[а-я]*', 
            r'новафильм[а-я]*', 
            r'нов[еау]', 
            r'novafilm', 
            r'nova\s*film',
            r'nova\s*fin[nm]*',
            r'нова\s*фин[н]*',
            r'новафин[н]*'
        ],
        'tracker_keywords': ['novafilm', 'новафильм', 'нова фильм', 'nova film']
    },
    'redheadsound': {
        'display_name': 'Red Head Sound',
        'speech_patterns': [r'ред\s+хед\s+саунд[а-я]*', r'рэд\s+хэд\s+саунд[а-я]*', r'редхед\s*саунд[а-я]*', r'ред\s+хед', r'рэд\s+хэд', r'рхс', r'rhs', r'red\s*head\s*sound'],
        'tracker_keywords': ['red head sound', 'rhs', 'ред хед саунд']
    },
    'hdrezka': {
        'display_name': 'HDRezka',
        'speech_patterns': [r'(?:хд|эйч\s*ди|hd)\s*резк[а-я]*', r'хдрезк[а-я]*', r'резк[еауой]*', r'hdrezka'],
        'tracker_keywords': ['hdrezka', 'резка', 'hd резка']
    },
    'newstudio': {
        'display_name': 'NewStudio',
        'speech_patterns': [r'нью\s*студи[яеюий]*', r'ньюстуди[яеюий]*', r'нью\s*студио', r'ньюстудио', r'newstudio', r'new\s*studio'],
        'tracker_keywords': ['newstudio', 'ньюстудио', 'new studio']
    },
    'kuraj': {
        'display_name': 'Кураж-Бамбей',
        'speech_patterns': [r'кураж[а-я]*\s*бамбе[яеюий]*', r'кураж[а-я]*\s*бомбе[яеюий]*', r'кураж[еауом]*', r'kuraj'],
        'tracker_keywords': ['кураж', 'кураж-бамбей', 'kuraj']
    },
    'alexfilm': {
        'display_name': 'AlexFilm',
        'speech_patterns': [r'алекс\s*фильм[а-я]*', r'алексфильм[а-я]*', r'alexfilm'],
        'tracker_keywords': ['alexfilm', 'алексфильм', 'алекс фильм']
    },
    'tvshows': {
        'display_name': 'TVShows',
        'speech_patterns': [r'тв\s*шоу[а-я]*', r'твшоус', r'ти\s*ви\s*шоу[а-я]*', r'tvshows', r'tv\s*shows'],
        'tracker_keywords': ['tvshows', 'твшоус', 'tv shows']
    },
    'flarrow': {
        'display_name': 'Flarrow Films',
        'speech_patterns': [r'фларроу[а-я]*', r'флароу[а-я]*', r'флероу[а-я]*', r'флярроу[а-я]*', r'flarrow\s*films?'],
        'tracker_keywords': ['flarrow films', 'flarrow', 'фларроу']
    },
    'studioband': {
        'display_name': 'Студийная Банда',
        'speech_patterns': [r'студийн[а-я]+\s+банд[а-я]*', r'студия\s+банда', r'studio\s*band'],
        'tracker_keywords': ['студийная банда', 'studioband', 'studio band']
    },
    'anilibria': {
        'display_name': 'AniLibria',
        'speech_patterns': [r'анилибри[яеюий]*', r'ани\s*либри[яеюий]*', r'anilibria'],
        'tracker_keywords': ['anilibria', 'анилибрия']
    },
    'anidub': {
        'display_name': 'AniDUB',
        'speech_patterns': [r'анидаб[а-я]*', r'ани\s*даб[а-я]*', r'anidub'],
        'tracker_keywords': ['anidub', 'анидаб']
    },
    'shiza': {
        'display_name': 'SHIZA Project',
        'speech_patterns': [r'шиз[а-я]*\s*проджект[а-я]*', r'шиз[а-я]*', r'shiza\s*project'],
        'tracker_keywords': ['shiza project', 'шиза проджект', 'shiza']
    },
    'jaskier': {
        'display_name': 'Jaskier',
        'speech_patterns': [r'яскьер[а-я]*', r'яскеер[а-я]*', r'яскиер[а-я]*', r'яскер[а-я]*', r'jaskier'],
        'tracker_keywords': ['jaskier', 'яскьер']
    },
    'goblin': {
        'display_name': 'Гоблин (Д. Пучков)',
        'speech_patterns': [r'гоблин[а-я]*', r'гоблине', r'пучков[а-я]*', r'goblin'],
        'tracker_keywords': ['гоблин', 'goblin', 'пучков']
    },
    'serbin': {
        'display_name': 'Юрий Сербин',
        'speech_patterns': [r'сербин[а-я]*', r'сербина', r'сербине', r'юри[яй]*\s+сербин[а-я]*', r'serbin'],
        'tracker_keywords': ['сербин', 'serbin']
    },
    'gavrilov': {
        'display_name': 'Андрей Гаврилов',
        'speech_patterns': [r'гаврилов[а-я]*', r'гаврилова', r'андре[яй]*\s+гаврилов[а-я]*', r'gavrilov'],
        'tracker_keywords': ['гаврилов', 'gavrilov']
    },
    'volodarskiy': {
        'display_name': 'Леонид Володарский',
        'speech_patterns': [r'володарск[а-я]*', r'леонид[а-я]*\s+володарск[а-я]*', r'volodarskiy'],
        'tracker_keywords': ['володарский', 'volodarskiy']
    },
    'dub': {
        'display_name': 'Дубляж',
        'speech_patterns': [r'полн[а-я]*\s+дубляж[а-я]*', r'дубляж[а-я]*', r'дублированн[а-я]*', r'чист[а-я]*\s+дубляж[а-я]*', r'в\s+дубляже'],
        'tracker_keywords': ['дубляж', 'дублированный', '| d |', ' d,', '| d']
    }
}

def extract_voiceover(text):
    """
    Выделение желаемой студии озвучки из фразы:
    1. По словарю студий с триггерами ('в озвучке X', 'в переводе X', 'от X') и сленгу ('в кубике', 'в лосте')
    2. По универсальному шаблону 'в озвучке / переводе <ЛюбаяСтудия>'
    Безопасно: никогда не удаляет предлоги фильмов типа 'В диких условиях', 'Властелин колец'.
    Возвращает: (target_voiceover: dict|None, cleaned_text: str)
    """
    clean = text.replace('ё', 'е').replace('Ё', 'е')
    found_key = None
    matched_span = None

    for key, data in VOICEOVER_STUDIOS.items():
        for pat in data['speech_patterns']:
            # Вариант 1а: явный триггер
            p1 = rf'(?:\b(?:в|на)\s+(?:озвучке|переводе|дубляже|аудиодорожке)\s+|\b(?:от\s+студии|от|голосом)\s+)(?:{pat})\b'
            m = re.search(p1, clean, re.IGNORECASE)
            if m:
                found_key = key
                matched_span = (m.start(), m.end())
                break

            # Вариант 1б: сленговый предлог строго перед известной студией
            p2 = rf'\b(?:в|от)\s+(?:{pat})\b'
            m = re.search(p2, clean, re.IGNORECASE)
            if m:
                found_key = key
                matched_span = (m.start(), m.end())
                break
        if found_key:
            break

    # 2. Универсальный fallback для неизвестных студий после 'в озвучке'
    if not found_key:
        m = re.search(r'\b(?:в|на)\s+(?:озвучке|переводе|дубляже)\s+([а-яa-z0-9\s\-]+?)(?=\s+(?:\d|сезон|сери)|$)', clean, re.IGNORECASE)
        if m:
            custom_name = m.group(1).strip()
            if custom_name and len(custom_name) >= 3 and custom_name not in ('сезон', 'серия', 'фильм'):
                matched_span = (m.start(), m.end())
                clean = clean[:matched_span[0]] + ' ' + clean[matched_span[1]:]
                clean = re.sub(r'\s+', ' ', clean).strip()
                return {
                    'key': 'custom',
                    'display_name': custom_name.title(),
                    'tracker_keywords': [custom_name.lower()]
                }, clean

    if found_key and matched_span:
        clean = clean[:matched_span[0]] + ' ' + clean[matched_span[1]:]
        clean = re.sub(r'\s+', ' ', clean).strip()
        data = VOICEOVER_STUDIOS[found_key]
        return {
            'key': found_key,
            'display_name': data['display_name'],
            'tracker_keywords': data['tracker_keywords']
        }, clean

    return None, clean

NUM_WORDS = {
    # 11 - 20 сначала
    'одиннадцат': 11, 'двенадцат': 12, 'тринадцат': 13, 'четырнадцат': 14,
    'пятнадцат': 15, 'шестнадцат': 16, 'семнадцат': 17, 'восемнадцат': 18,
    'девятнадцат': 19, 'двадцат': 20,
    # 1 - 10 порядковые и количественные
    'перв': 1, 'один': 1, 'одн': 1,
    'втор': 2, 'две': 2, 'два': 2,
    'трет': 3, 'три': 3,
    'четверт': 4, 'четыр': 4,
    'пят': 5,
    'шест': 6,
    'седьм': 7, 'сем': 7,
    'восьм': 8, 'восем': 8,
    'девят': 9,
    'десят': 10
}

def extract_one_season(clean):
    season = None
    # 1a. Префиксная цифра: 'в 3 сезоне', '3-й сезон'
    m = re.search(r'(?:\b(?:в|на)\s+)?(\d+)\s*(?:-?[а-я]{1,3})?\s*сезон[а-я]*', clean, re.IGNORECASE)
    if m:
        season = int(m.group(1))
        clean = clean[:m.start()] + ' ' + clean[m.end():]
    else:
        # 1b. Префиксное слово: 'в пятом сезоне', 'третий сезон', 'седьмой сезон'
        for prefix, val in NUM_WORDS.items():
            m = re.search(rf'(?:\b(?:в|на)\s+)?\b{prefix}[а-я]*\s+сезон[а-я]*', clean, re.IGNORECASE)
            if m:
                season = val
                clean = clean[:m.start()] + ' ' + clean[m.end():]
                break
        
        # 1c. Постфиксная цифра: 'сезон 3'
        if season is None:
            m = re.search(r'(?:\b(?:в|на)\s+)?сезон[а-я]*\s*(\d+)', clean, re.IGNORECASE)
            if m:
                season = int(m.group(1))
                clean = clean[:m.start()] + ' ' + clean[m.end():]
            else:
                # 1d. Постфиксное слово: 'сезон третий', 'сезон четыре'
                for prefix, val in NUM_WORDS.items():
                    m = re.search(rf'(?:\b(?:в|на)\s+)?сезон[а-я]*\s+{prefix}[а-я]*', clean, re.IGNORECASE)
                    if m:
                        season = val
                        clean = clean[:m.start()] + ' ' + clean[m.end():]
                        break
    return season, clean

def extract_one_episode(clean):
    episode = None
    # 2a. Префиксная цифра: '5 серия', '5-я серия'
    m = re.search(r'(?:\b(?:в|на)\s+)?(\d+)\s*(?:-?[а-я]{1,3})?\s*сери(?!ал)[а-я]*', clean, re.IGNORECASE)
    if m:
        episode = int(m.group(1))
        clean = clean[:m.start()] + ' ' + clean[m.end():]
    else:
        # 2b. Префиксное слово: 'пятая серия'
        for prefix, val in NUM_WORDS.items():
            m = re.search(rf'(?:\b(?:в|на)\s+)?\b{prefix}[а-я]*\s+сери(?!ал)[а-я]*', clean, re.IGNORECASE)
            if m:
                episode = val
                clean = clean[:m.start()] + ' ' + clean[m.end():]
                break
        
        # 2c. Постфиксная цифра: 'серия 5'
        if episode is None:
            m = re.search(r'(?:\b(?:в|на)\s+)?сери(?!ал)[а-я]*\s*(\d+)', clean, re.IGNORECASE)
            if m:
                episode = int(m.group(1))
                clean = clean[:m.start()] + ' ' + clean[m.end():]
            else:
                # 2d. Постфиксное слово: 'серия пятая', 'серия три'
                for prefix, val in NUM_WORDS.items():
                    m = re.search(rf'(?:\b(?:в|на)\s+)?сери(?!ал)[а-я]*\s+{prefix}[а-я]*', clean, re.IGNORECASE)
                    if m:
                        episode = val
                        clean = clean[:m.start()] + ' ' + clean[m.end():]
                        break
    return episode, clean

def extract_season_and_episode(text):
    """
    Строгий парсинг сезона и серии:
    Срабатывает ТОЛЬКО если в тексте явно присутствуют слова «сезон» или «серия».
    Обычные фильмы с цифрами («Терминатор 3», «Такси 4», «1+1») НЕ затрагиваются.
    """
    season = None
    episode = None
    clean = text.replace('ё', 'е').replace('Ё', 'е')

    has_season = bool(re.search(r'\bсезон', clean, re.IGNORECASE))
    has_episode = bool(re.search(r'\bсери(?!ал)', clean, re.IGNORECASE))

    pos_s = re.search(r'\bсезон', clean, re.IGNORECASE).start() if has_season else 999999
    pos_ep = re.search(r'\bсери(?!ал)', clean, re.IGNORECASE).start() if has_episode else 999999

    if pos_ep < pos_s:
        # Если первой названа серия
        episode, clean = extract_one_episode(clean)
        if has_season:
            season, clean = extract_one_season(clean)
    else:
        # Если первым назван сезон
        if has_season:
            season, clean = extract_one_season(clean)
        if has_episode:
            episode, clean = extract_one_episode(clean)

    clean = re.sub(r'\s+', ' ', clean).strip()
    return season, episode, clean

def is_exit_command(text: str) -> bool:
    """
    Проверяет, хочет ли пользователь выйти/закрыть навык на любом этапе диалога.
    """
    if not text:
        return False
    t = text.lower().strip()
    t = re.sub(r'^(алиса|яндекс|пожалуйста|плиз|слушай)\s+', '', t).strip()
    t = re.sub(r'\s+(пожалуйста|плиз)$', '', t).strip()
    t = re.sub(r'[«\"\'\.\,\?!]+', '', t).strip()
    
    exact_exit = {
        'выход', 'выйти', 'выйди', 'выходи', 'выходим',
        'стоп', 'хватит', 'отмена', 'отбой', 'назад',
        'закрой', 'закройся', 'закрыть', 'выключи', 'выключись',
        'пока', 'до свидания', 'досвидания', 'прощай',
        'не надо', 'не нужно', 'не хочу', 'ничего', 'ничего не надо',
        'никакой', 'ни один', 'ни то ни другое', 'ни то', 'не то',
        'отвали', 'отстань', 'замолчи', 'заткнись', 'молчи',
        'отвяжись', 'отвалите'
    }
    if t in exact_exit:
        return True
        
    if re.search(r'^(выйди|закрой|закройся|выключи|выйти)\s+(из\s+)?(навык[а-я]*|кинозал[а-я]*|приложени[а-я]*|диалог[а-я]*)$', t):
        return True
        
    profanity_exit = r'\b(иди|пошла|пошел|пошли|идите|пошлите)\s+(на\s*хуй|в\s*жопу|в\s*пизду|нахер|к\s*черту|лесом)\b'
    if re.search(profanity_exit, t):
        return True
        
    if re.search(r'^(на\s*хуй|нахуй|нахер|в\s*жопу|в\s*пизду|да\s*пошла\s*ты|да\s*пошел\s*ты)$', t):
        return True
        
    if re.search(r'^(все\s+пока|ладно\s+пока|ну\s+пока|давай\s+пока|все\s+стоп|все\s+отмена)$', t):
        return True
        
    return False

def clean_movie_query(text):
    """
    Очистка поисковой фразы от префиксов Алисы, команд включения, категорий и экранов.
    """
    text = text.lower().strip()
    text = re.sub(r'^[«\"\'\s\.\,\?!]+|[»\"\'\s\.\,\?!]+$', '', text)
    
    prefix_pat = (
        r'^(алиса|яндекс)?[\,\s]*'
        r'(попроси|скажи|передай|открой|запусти)?[\,\s]*'
        r'(навык(у)?[\,\s]+)?'
        r'(мой|моему|моем|наш|нашему|в|домашний|домашнему|домашнем)?[\,\s]*'
        r'(кинозал|кинотеатр)[а-я]*[\,\s]*'
        r'(и\s+|чтобы\s+)?'
    )
    text = re.sub(prefix_pat, '', text).strip()
    
    for _ in range(5):
        text = re.sub(r'^[«\"\'\s\.\,\?!]+', '', text).strip()
        intro_pat = r'^(и|а|чтобы|пожалуйста|плиз|алиса|яндекс|давай|давай-ка|хочу|хотим|хотелось\s+бы|дай|дайте|нам|мне|быстро|срочно)[\,\s]+'
        text = re.sub(intro_pat, '', text).strip()
        text = re.sub(r'^(мой\s+|домашний\s+|наш\s+)?(кинозал|кинотеатр)[а-я]*[\,\s]*(и\s+)?', '', text).strip()
        
        verb_pat = (
            r'^(включ(ить|и|ите|ай|айте|ишь|у)?|'
            r'откро(й|йте|ем|ет|ют)?|откры(ть|вай|вайте)?|'
            r'постав(ить|ь|ьте|ишь|лю)?|'
            r'запуст(ить|и|ите|ишь|им|я)?|запуск(ай|айте)?|'
            r'покаж(и|ите|ем|у)?|показ(ать|ывай)?|'
            r'найд(и|ите|ем|у)?|найти|ищ(и|ите)?|'
            r'вруб(ить|и|ите|ай|айте|им)?|'
            r'воспроизве(сти|ди|дите)?|'
            r'(по)?смотр(еть|и|ите|им)?|'
            r'(по)?гля(нуть|нем|ди|дите|дим|деть)?)\s+'
        )
        text = re.sub(verb_pat, '', text).strip()
        cat_pat = r'^(фильм[а-я]*|кин(о|чик|ошку|цо|а[а-я]*)|сериал[а-я]*|мульт[а-я]*|аниме|дорам[а-я]*)\s+'
        text = re.sub(cat_pat, '', text).strip()
        screen_prefix = r'^(на\s+(экране|проекторе|телевизоре|телеке|тв|ноутбуке|ноуте|компе|пк))\s+'
        text = re.sub(screen_prefix, '', text).strip()

    for _ in range(3):
        text = re.sub(r'\s+(на\s+(экране|проекторе|телевизоре|телеке|тв|ноутбуке|ноуте|компе|пк))$', '', text).strip()
        text = re.sub(r'\s+(пожалуйста|плиз)$', '', text).strip()
        text = re.sub(r'^(пожалуйста|плиз|быстро|срочно)$', '', text).strip()
        text = re.sub(r'\s+(в\s+(хорошем|отличном|высоком|лучшем)?\s*качестве)$', '', text).strip()
        text = re.sub(r'\s+(онлайн|смотреть\s+онлайн)$', '', text).strip()
    
    # Точечные алиасы для фильмов со знаками в названии (устная речь Алисы)
    aliases = {
        '1 плюс 1': '1+1',
        'один плюс один': '1+1',
        '2 плюс 1': '2+1',
        'два плюс один': '2+1',
        'м плюс ж': 'м+ж',
        'клинок рассекающий демонов': 'истребитель демонов',
    }
    for phrase, mapped in aliases.items():
        if phrase in text:
            text = text.replace(phrase, mapped)
            
    return text.strip()

def extract_youtube_query(text):
    """
    Проверяет наличие маркеров YouTube в запросе.
    Возвращает: (is_yt: bool, search_term: str)
    Если это просто открытие YouTube (например "включи ютуб") -> (True, "")
    Если это поиск видео -> (True, "обзор iphone 16")
    Если маркер YouTube отсутствует -> (False, "")
    """
    t_lower = text.lower().strip()
    yt_match = re.search(r'\b(на\s+|в\s+)?(ютуб|youtube|ютюб)[а-я]*\b', t_lower)
    if not yt_match:
        return False, ""
        
    cleaned = t_lower[:yt_match.start()] + ' ' + t_lower[yt_match.end():]
    cleaned = clean_movie_query(cleaned)
    cleaned = re.sub(r'^поиск\s+', '', cleaned).strip()
    cleaned = re.sub(r'^(пожалуйста|плиз|быстро|срочно)$', '', cleaned).strip()
    cleaned = re.sub(r'\s+(пожалуйста|плиз|быстро|срочно)$', '', cleaned).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    verbs_and_general = {
        'включи', 'включить', 'открой', 'открыть', 'запусти', 'запустить', 
        'покажи', 'показать', 'найди', 'найти', 'вруби', 'врубить',
        'видео', 'ролик', 'ролики', 'видос', 'видосы'
    }
    if cleaned in verbs_and_general:
        cleaned = ""
        
    return True, cleaned
