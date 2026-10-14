# -*- coding: utf-8 -*-
"""
core/kinopoisk.py - Поиск, парсинг паспорта фильма и семантическое ранжирование (Smart Confidence) через API Кинопоиска
"""

import re
import json
import datetime
import urllib.request
import urllib.parse

from core.config import KINOPOISK_API_KEY, KINOPOISK_URL

STOP_WORDS = {
    'фильм', 'фильма', 'фильму', 'фильмом', 'фильме',
    'кино', 'кинофильм', 'сериал', 'мультфильм', 'мультик', 
    'часть', 'смотреть', 'онлайн', 'включи', 'включить', 'поставь', 'поставить',
    'покажи', 'запусти', 'года', 'году', 'год', 'про', 'аниме', 'дорама', 'дораму'
}

def normalize_text(text):
    if not text:
        return ""
    text = text.lower().replace('ё', 'е').replace('э', 'е')
    text = re.sub(r'[^a-zа-я0-9\s]', ' ', text)
    return ' '.join(text.split())

def word_match(w, words_set):
    if w in words_set:
        return True
    if len(w) >= 4:
        stem = w[:len(w)-1] if len(w) <= 5 else w[:len(w)-2]
        for target in words_set:
            if target.startswith(stem) or (len(target) >= 4 and target[:len(stem)] == stem):
                return True
    return False

def resolve_via_kinopoisk(query):
    """
    Универсальный семантический поиск и ранжирование паспортов фильма по баллам через Кинопоиск (poiskkino.dev)
    """
    if not KINOPOISK_API_KEY:
        return [], False, ""
        
    q_norm = normalize_text(query)
    
    # 1. Извлекаем год из запроса, если есть
    year_match = re.search(r'\b(19\d\d|20\d\d)\b', q_norm)
    req_year = year_match.group(1) if year_match else None
    
    # 2. Извлекаем номер части
    req_part = None
    part_word_match = re.search(r'\b(перв|втор|трет|четверт|пят|[1-9])\s*(-?ая|-?ую|-?ой|-?ья|-?е)?\s+част', q_norm)
    if part_word_match:
        raw_p = part_word_match.group(1)
        dmap = {'перв': 1, 'втор': 2, 'трет': 3, 'четверт': 4, 'пят': 5}
        req_part = dmap.get(raw_p[:4], int(raw_p) if raw_p.isdigit() else None)
    else:
        part_word_rev = re.search(r'\bчаст[ьиея]\s+([1-9]|перв|втор|трет|четверт|пят)', q_norm)
        if part_word_rev:
            raw_p = part_word_rev.group(1)
            dmap = {'перв': 1, 'втор': 2, 'трет': 3, 'четверт': 4, 'пят': 5}
            req_part = dmap.get(raw_p[:4], int(raw_p) if raw_p.isdigit() else None)
        else:
            end_part_match = re.search(r'\s+([2-9]|втор(ая|ой|ую)?|трет(ий|ья|ью)?|четверт(ая|ый|ую)?|пят(ая|ый|ую)?)$', q_norm)
            if end_part_match:
                raw_p = end_part_match.group(1)
                dmap = {'втор': 2, 'трет': 3, 'четверт': 4, 'пят': 5}
                req_part = dmap.get(raw_p[:4], int(raw_p) if raw_p.isdigit() else None)
                
    skip_tokens = set(STOP_WORDS)
    if req_year:
        skip_tokens.add(req_year)
    q_words = [w for w in q_norm.split() if w not in skip_tokens]
    
    # Нормализуем фразы вроде "вторая часть" в цифру "2"
    search_term = re.sub(r'\b(перв(ая|ую|ый|ое)\s+часть|1\s*часть)\b', '1', query.lower().strip())
    search_term = re.sub(r'\b(втор(ая|ую|ой|ое)\s+часть|2\s*часть)\b', '2', search_term)
    search_term = re.sub(r'\b(трет(ья|ью|ий|ье)\s+часть|3\s*часть)\b', '3', search_term)
    search_term = re.sub(r'\b(четверт(ая|ую|ый|ое)\s+часть|4\s*часть)\b', '4', search_term)
    search_term = re.sub(r'\b(пят(ая|ую|ый|ое)\s+часть|5\s*часть)\b', '5', search_term)
    
    params = urllib.parse.urlencode({"query": search_term.strip(), "limit": 10})
    req = urllib.request.Request(f"{KINOPOISK_URL}?{params}", headers={
        "X-API-KEY": KINOPOISK_API_KEY,
        "Accept": "application/json",
        "User-Agent": "HomeCinema/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=3.2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            docs = data.get('docs', [])
            candidates = []
            current_year = datetime.date.today().year
            today_iso = datetime.date.today().isoformat()
            
            for d in docs:
                name = d.get('name')
                if not name:
                    continue
                alt = d.get('alternativeName') or d.get('enName') or ''
                year = d.get('year')
                rating = (d.get('rating') or {}).get('kp') or (d.get('rating') or {}).get('imdb')
                votes = (d.get('votes') or {}).get('kp') or 0
                m_type = d.get('type')
                status = (d.get('status') or '').lower()
                premiere = (d.get('premiere') or {}).get('world') or (d.get('premiere') or {}).get('russia')
                
                is_unreleased = False
                if status in ('announced', 'filming', 'post-production', 'pre-production'):
                    is_unreleased = True
                elif year and int(year) > current_year:
                    is_unreleased = True
                elif premiere and str(premiere)[:10] > today_iso:
                    is_unreleased = True
                elif (d.get('premiere') or {}).get('world') and not (d.get('premiere') or {}).get('bluray') and not (d.get('premiere') or {}).get('dvd') and year and int(year) >= current_year:
                    is_unreleased = True
                    
                candidates.append({
                    "name": name,
                    "alt": alt,
                    "year": str(year) if year else None,
                    "rating": round(rating, 1) if rating else None,
                    "votes": int(votes) if votes else 0,
                    "type": m_type,
                    "status": status,
                    "unreleased": is_unreleased,
                    "display": f"{name} ({year})" if year else name
                })
                
            if not candidates:
                return [], False, ""

            # Проверяем франшизу по номеру части
            franchise_part_candidate = None
            if req_part and q_words:
                root_w = q_words[0]
                franchise_movies = [
                    c for c in candidates 
                    if root_w in normalize_text(c['name']) 
                    and c.get('year') 
                    and c.get('votes', 0) > 5000 
                    and c.get('type') in ('movie', 'cartoon', 'anime')
                ]
                explicit_digit = None
                roman = {1: 'i', 2: 'ii', 3: 'iii', 4: 'iv', 5: 'v'}.get(req_part, '')
                for c in franchise_movies:
                    title_clean = normalize_text(f"{c['name']} {c.get('alt')}")
                    if re.search(rf'\b({req_part}|{roman})\b', title_clean):
                        explicit_digit = c
                        break
                        
                if explicit_digit:
                    franchise_part_candidate = explicit_digit
                else:
                    franchise_movies.sort(key=lambda x: int(x['year']))
                    if len(franchise_movies) >= req_part:
                        franchise_part_candidate = franchise_movies[req_part - 1]

            # Подсчет баллов соответствия
            for c in candidates:
                title_ru = normalize_text(c['name'])
                title_alt = normalize_text(c.get('alt', ''))
                title_all = f"{title_ru} {title_alt}"
                title_words = set(title_all.split())
                
                matched_q = [w for w in q_words if word_match(w, title_words)]
                q_cov = len(matched_q) / max(len(q_words), 1) if q_words else 1.0
                
                score = len(matched_q) * 1000
                if q_cov == 1.0 and q_words:
                    score += 5000
                elif q_cov >= 0.75:
                    score += 2000
                    
                if req_year and c.get('year') == req_year:
                    score += 4000
                    
                if franchise_part_candidate and c == franchise_part_candidate:
                    score += 5000
                    
                if q_words and set(q_words) == set(title_ru.split()) and c.get('votes', 0) > 5000:
                    score += 1500
                    
                score += min(c.get('votes', 0) / 2000.0, 500.0)
                
                c['score'] = round(score, 1)
                c['matched_count'] = len(matched_q)
                c['q_cov'] = round(q_cov, 2)

            candidates.sort(key=lambda x: x['score'], reverse=True)
            top = candidates[0]
            
            # Анализ однозначности (is_definitive)
            major_candidates = [
                c for c in candidates 
                if not c.get('unreleased') 
                and c.get('votes', 0) > 30000 
                and c.get('type') in ('movie', 'cartoon', 'anime')
            ]
            
            is_definitive = False
            reason = ""
            
            if req_year and top.get('year') == req_year:
                is_definitive = True
                reason = f"Точный год {req_year}"
            elif req_part and ((franchise_part_candidate and top == franchise_part_candidate) or (str(req_part) in normalize_text(top['name']))):
                is_definitive = True
                reason = f"Точная часть {req_part}"
            elif len(q_words) >= 2:
                major_competing = [
                    c for c in candidates[1:] 
                    if c['matched_count'] == top['matched_count']
                    and c.get('votes', 0) > 30000 
                    and c.get('votes', 0) > 0.2 * max(top.get('votes', 1), 1)
                ]
                if not major_competing and top['q_cov'] >= 0.75:
                    is_definitive = True
                    reason = f"Уникальное совпадение подзаголовка/слов ({top['matched_count']}/{len(q_words)})"
                    
            if not is_definitive:
                if len(major_candidates) == 1 and (top['q_cov'] >= 0.5 or top.get('votes', 0) > 50000):
                    is_definitive = True
                    reason = "Единственный популярный полнометражный фильм"
                elif len(major_candidates) >= 2:
                    top_m = major_candidates[0]
                    sec_m = major_candidates[1]
                    if top_m.get('votes', 0) > 5 * max(sec_m.get('votes', 0), 1) and top_m.get('votes', 0) > 100000:
                        is_definitive = True
                        reason = f"Доминирует по популярности ({top_m.get('votes')} vs {sec_m.get('votes')} голосов)"

            return candidates, is_definitive, reason
    except Exception as e:
        print(f"⚠️ Ошибка Kinopoisk API: {e}", flush=True)
        return [], False, ""

def resolve_user_choice(text, candidates):
    """
    Разрешение выбора пользователя при уточнении («первый», «второй», по году или словам названия)
    """
    t_norm = normalize_text(text)
    if re.search(r'\b(1|один|перв(ый|ую|ое|ая|ом|ой)?)\b', t_norm):
        return candidates[0] if len(candidates) >= 1 else None
    if re.search(r'\b(2|два|втор(ой|ую|ое|ая|ом|ой)?)\b', t_norm):
        return candidates[1] if len(candidates) >= 2 else None
    if re.search(r'\b(3|три|трет(ий|ью|ье|ья|ьем|ей)?)\b', t_norm):
        return candidates[2] if len(candidates) >= 3 else None
        
    for c in candidates:
        if c.get('year') and c['year'] in t_norm:
            return c
            
    for c in candidates:
        orig = normalize_text(c.get('orig_title') or c.get('alt') or '')
        ru = normalize_text(c.get('ru_title') or c.get('name') or '')
        words = [w for w in (orig + ' ' + ru).split() if len(w) >= 4]
        for w in words:
            if word_match(w, set(t_norm.split())):
                return c
    return None
