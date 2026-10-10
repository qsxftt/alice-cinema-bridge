# -*- coding: utf-8 -*-
"""
core/torrents.py - Поиск торрентов через Prowlarr API, ранжирование раздач (1080p, сиды, озвучки) и умный поиск сериалов
"""

import re
import json
import urllib.request
import urllib.parse

from core.config import PROWLARR_URL, PROWLARR_API_KEY
from core.nlu import VOICEOVER_STUDIOS
from core.kinopoisk import normalize_text

def extract_seasons_from_title(title):
    """
    Извлекает множество номеров сезонов из названия релиза.
    Возвращает set(int), например {7} или {1, 2, 3, 4, 5, 6, 7, 8}.
    Если сезоны не обнаружены, возвращает None.
    """
    seasons = set()
    t_clean = title.lower()

    # 1. Диапазоны S01-S08, S1-8, S01-08, S1-S8, S1-8E1-96
    s_range_matches = re.findall(r'\bs(\d{1,2})\s*[-–—]\s*s?(\d{1,2})(?:e\d+|[^\w]|$)', t_clean)
    for start, end in s_range_matches:
        s_val, e_val = int(start), int(end)
        if 1 <= s_val <= e_val <= 50:
            seasons.update(range(s_val, e_val + 1))

    # 2. Русские диапазоны: "Сезоны 1-8", "Сезон 1-7", "1-8 сезоны", "1-8 сезон"
    ru_range_matches = re.findall(r'(?:сезон(?:ы|а)?\s*[:\(\[]?\s*(\d{1,2})\s*[-–—]\s*(\d{1,2})|(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*сезон)', t_clean)
    for m in ru_range_matches:
        if m[0] and m[1]:
            s_val, e_val = int(m[0]), int(m[1])
        else:
            s_val, e_val = int(m[2]), int(m[3])
        if 1 <= s_val <= e_val <= 50:
            seasons.update(range(s_val, e_val + 1))

    # 3. Диапазоны вида "01-08 из 08", "[01-08 из 8]"
    iz_matches = re.findall(r'(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+из\s+\d{1,2}', t_clean)
    for start, end in iz_matches:
        s_val, e_val = int(start), int(end)
        if 1 <= s_val <= e_val <= 50:
            seasons.update(range(s_val, e_val + 1))

    # 4. Фразы типа "все сезоны", "полный сериал", "все серии"
    if re.search(r'\b(все\s+сезоны|полный\s+сериал|все\s+серии)\b', t_clean):
        seasons.update(range(1, 50))

    # 5. Одиночные сезоны: S07, [S7], S07E05, S7E1-12
    single_s = re.findall(r'\bs(\d{1,2})(?:e\d+|[\s\]\)\,\.\_\-]|$)', t_clean)
    for s in single_s:
        val = int(s)
        if 1 <= val <= 50:
            seasons.add(val)

    ru_single = re.findall(r'(?:сезон(?:а)?\s*[:\(\[]?\s*0?(\d{1,2})\b|\b0?(\d{1,2})\s*сезон)', t_clean)
    for m in ru_single:
        val = int(m[0] if m[0] else m[1])
        if 1 <= val <= 50:
            seasons.add(val)

    return seasons if seasons else None

def score_release(item, is_series=False, target_voiceover=None):
    title = item.get('title', '')
    t_lower = title.lower()
    seeders = item.get('seeders', 0)
    size_gb = round(item.get('size', 0) / (1024**3), 2)
    
    # 0. Мертвые раздачи без сидеров сразу исключаем
    if seeders == 0:
        return -9999
        
    score = 0
    # 1. Вес сидеров
    if seeders < 3:
        score -= 150
    elif seeders >= 25:
        score += 150
    elif seeders >= 10:
        score += 100
    elif seeders >= 5:
        score += 50
    score += min(seeders, 80) * 2

    # 2. Качество видео (1080p - абсолютный фаворит для Full HD проектора)
    if "1080p" in t_lower or "1080i" in t_lower:
        score += 150
    elif "web-dl" in t_lower or "bdrip" in t_lower:
        score += 100
    elif "720p" in t_lower:
        score += 50
        
    if "2160p" in t_lower or "4k" in t_lower:
        score -= 500  # 4K не нужен на проекторе
        
    # 3. Штраф за тяжелые кодеки
    if "av1" in t_lower:
        score -= 300  # Проектор не поддерживает аппаратный AV1
        
    # 4. Градации размера видео
    if is_series:
        if 2.0 <= size_gb <= 350.0:
            score += 100
        elif size_gb < 1.0:
            score -= 300
    else:
        if 2.0 <= size_gb <= 26.0:
            score += 100
        elif 26.0 < size_gb <= 32.0:
            score += 30
        elif size_gb > 45.0:
            score -= 800
        elif size_gb > 35.0:
            score -= 500
        elif size_gb < 1.0:
            score -= 300
        
    # 5. Штраф за BDRemux
    if "remux" in t_lower or "bdremux" in t_lower:
        score -= 300

    # 6. Умный скоринг озвучки
    if target_voiceover:
        keywords = target_voiceover.get('tracker_keywords', [])
        has_target = any(kw in t_lower for kw in keywords)
        if has_target:
            score += 600
        else:
            score -= 300
    else:
        is_multi = False
        multi_markers = ['multi', '| d |', '| d,', ' d, ', ' p, ', ' p2, ', 'лицензия', 'дубляж']
        if any(m in t_lower for m in multi_markers):
            is_multi = True
        else:
            studios_cnt = 0
            for s_data in VOICEOVER_STUDIOS.values():
                if any(kw in t_lower for kw in s_data['tracker_keywords']):
                    studios_cnt += 1
            if studios_cnt >= 2:
                is_multi = True
                
        if is_multi:
            score += 80
        
    return score

def extract_movie_identity(raw_title, user_query):
    year_match = re.search(r'(?:[\(\[\s]|^)(19\d\d|20\d\d)(?:[\)\]\s]|$)', raw_title)
    year = year_match.group(1) if year_match else None
    
    main_part = re.split(r'[\(\[]', raw_title)[0].strip()
    ru_title = main_part
    orig_title = None
    if ' / ' in main_part:
        parts = [p.strip() for p in main_part.split(' / ') if p.strip()]
        latin_parts = [p for p in parts if re.search(r'[a-zA-Z]', p)]
        cyr_parts = [p for p in parts if not re.search(r'[a-zA-Z]', p)]
        
        ru_title = cyr_parts[0] if cyr_parts else parts[0]
        if cyr_parts and user_query:
            q_set = set(normalize_text(user_query).split())
            for cp in cyr_parts:
                if q_set.issubset(set(normalize_text(cp).split())):
                    ru_title = cp
                    break
        orig_title = latin_parts[0] if latin_parts else (parts[1] if len(parts) >= 2 else None)
            
    if not ru_title:
        ru_title = user_query.capitalize()
        
    return ru_title, orig_title, year

def search_prowlarr_releases(query_term, is_series=False, target_voiceover=None):
    """Поиск в Prowlarr без categories=2000 (разблокирует RuTor!)"""
    url = f"{PROWLARR_URL}/api/v1/search?query={urllib.parse.quote(query_term)}&indexerIds=1&indexerIds=2&type=search"
    req = urllib.request.Request(url, headers={"X-Api-Key": PROWLARR_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"❌ Ошибка Prowlarr: {e}", flush=True)
        return []

    trash = ['camrip', 'telesync', ' ts ', ' hdts ', 'звук с ts']
    valid_items = []
    for item in data:
        t_lower = item.get('title', '').lower()
        if any(b in t_lower for b in trash):
            continue
        download_url = item.get('downloadUrl') or item.get('magnetUrl') or item.get('guid')
        if not download_url:
            continue
        item['download_url'] = download_url
        item['score'] = score_release(item, is_series=is_series, target_voiceover=target_voiceover)
        item['size_gb'] = round(item.get('size', 0) / (1024**3), 2)
        valid_items.append(item)
        
    return valid_items

def search_and_group_movies(query, target_year=None, orig_title=None, target_voiceover=None):
    print(f"🔍 Поиск раздач на трекерах: «{query}» (целевой год: {target_year})", flush=True)
    valid_items = search_prowlarr_releases(query, target_voiceover=target_voiceover)
    if target_voiceover and target_voiceover.get('tracker_keywords'):
        vo_tag = target_voiceover['tracker_keywords'][0]
        extra_items = search_prowlarr_releases(f"{query} {vo_tag}", target_voiceover=target_voiceover)
        existing_guids = {it.get('guid') or it.get('download_url') or it.get('title') for it in valid_items}
        for it in extra_items:
            g = it.get('guid') or it.get('download_url') or it.get('title')
            if g not in existing_guids:
                existing_guids.add(g)
                valid_items.append(it)
    if not valid_items:
        return []

    clean_q = query.lower()
    if target_year:
        clean_q = re.sub(rf'\b{target_year}\b', '', clean_q).strip()
    clean_q = re.sub(r'\s+', ' ', clean_q).strip()

    if clean_q:
        q_escaped = re.escape(clean_q)
        exact_pattern = re.compile(rf'^{q_escaped}\s*([/|\(\[\-\:\.,]|$)', re.IGNORECASE)
        strict_matches = [it for it in valid_items if exact_pattern.match(it.get('title', '').strip())]
        pool = strict_matches if strict_matches else valid_items
    else:
        pool = valid_items

    groups = {}
    for item in pool:
        ru_title, orig_title_found, year = extract_movie_identity(item['title'], query)
        key = (ru_title.lower(), year or 'unknown')
        if key not in groups:
            groups[key] = {
                "ru_title": ru_title,
                "orig_title": orig_title_found,
                "year": year,
                "display": f"{ru_title} ({year})" if year else ru_title,
                "releases": [],
                "total_seeds": 0,
                "max_score": -999
            }
        groups[key]["releases"].append(item)
        groups[key]["total_seeds"] += item.get('seeders', 0)
        if item['score'] > groups[key]["max_score"]:
            groups[key]["max_score"] = item['score']

    for g in groups.values():
        g["releases"].sort(key=lambda x: x['score'], reverse=True)
        g["best_release"] = g["releases"][0]

    def group_rank(g):
        rank = g["max_score"]
        if target_year and g.get('year') == str(target_year):
            rank += 500
        if orig_title and g.get('orig_title') and orig_title.lower() in g['orig_title'].lower():
            rank += 200
        return rank

    sorted_movies = sorted(groups.values(), key=group_rank, reverse=True)
    return sorted_movies

def find_best_series_release(search_query, orig_title=None, target_season=None, target_year=None, target_voiceover=None):
    """
    Умный поиск релизов сериала:
    1. Ищет по целевому сезону (напр. 'Декстер S07', 'Dexter S07').
    2. Ищет по общему названию сериала (напр. 'Декстер', 'Dexter') для захвата многосезонных паков.
    3. Отсекает спин-оффы и нерелевантные релизы.
    4. Проверяет вхождение target_season в диапазон сезонов раздачи (напр. Сезоны 1-8).
    5. Ранжирует раздачи по сидерам, 1080p и качеству.
    """
    queries = []
    vo_tag = target_voiceover['tracker_keywords'][0] if target_voiceover and target_voiceover.get('tracker_keywords') else None

    if target_season:
        s_tag = f"S{target_season:02d}"
        if vo_tag:
            queries.append(f"{search_query} {s_tag} {vo_tag}")
        queries.append(f"{search_query} {s_tag}")
        if orig_title and orig_title.lower() != search_query.lower():
            if vo_tag:
                queries.append(f"{orig_title} {s_tag} {vo_tag}")
            queries.append(f"{orig_title} {s_tag}")

    if vo_tag:
        queries.append(f"{search_query} {vo_tag}")
    queries.append(search_query)
    if orig_title and orig_title.lower() != search_query.lower():
        if vo_tag:
            queries.append(f"{orig_title} {vo_tag}")
        queries.append(orig_title)

    raw_items = []
    seen = set()

    for q in queries:
        items = search_prowlarr_releases(q, is_series=True, target_voiceover=target_voiceover)
        for it in items:
            guid = it.get('guid') or it.get('download_url') or it.get('title')
            if guid in seen:
                continue
            seen.add(guid)
            raw_items.append(it)

    valid_candidates = []
    q_words = set(normalize_text(search_query).split())
    orig_words = set(normalize_text(orig_title).split()) if orig_title else set()

    for it in raw_items:
        title = it.get('title', '')
        ru_title, orig_title_found, year = extract_movie_identity(title, search_query)
        
        ru_t_words = set(normalize_text(ru_title).split())
        orig_t_words = set(normalize_text(orig_title_found).split()) if orig_title_found else set()
        
        diff_ru = ru_t_words - q_words
        ignored_title_words = {'сериал', 'сезон', 'серии', 'минисериал', 'сериалы', 'новый', 'все', 'полный', 'the'}
        real_diff_ru = {w for w in diff_ru if w not in ignored_title_words and len(w) > 1}
        orig_matched = bool(orig_words and orig_words.issubset(orig_t_words))
        
        if real_diff_ru and not orig_matched:
            continue

        if target_season:
            seasons = extract_seasons_from_title(title)
            if seasons is not None:
                if target_season not in seasons:
                    continue
            else:
                if not re.search(r'\b(все\s+серии|полный\s+сериал)\b', title.lower()):
                    continue

        valid_candidates.append(it)

    valid_candidates.sort(key=lambda x: x['score'], reverse=True)
    return valid_candidates[0] if valid_candidates else None
