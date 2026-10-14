# -*- coding: utf-8 -*-
"""
core/playback.py - Взаимодействие с TorrServer, выбор нужной серии, отправка интента на Проектор / ПК и очистка
"""

import os
import re
import json
import time
import asyncio
import threading
import urllib.request

from androidtvremote2 import AndroidTVRemote
from core.config import (
    TORRSERVER_URL, PROJECTOR_IP, PROJECTOR_CERT, PROJECTOR_KEY,
    get_playback_target, set_pending_playback
)
from core.torrents import find_best_series_release, search_and_group_movies

def classify_torrent_videos(candidates):
    """
    Классификация файлов раздачи:
    - Одиночный фильм (is_series=False): ровно 1 основной видеофайл (>250 МБ).
    - Сериал / многосерийный фильм (is_series=True): несколько видеофайлов.
    """
    if not candidates:
        return False, []
    if len(candidates) == 1:
        return False, candidates
        
    large_files = [f for f in candidates if f.get('length', 0) > 250 * 1024 * 1024]
    if len(large_files) > 1:
        return True, large_files
    elif len(large_files) == 1:
        return False, large_files
    else:
        if len(candidates) > 1:
            return True, candidates
        return False, candidates

def find_target_video_file(video_files, target_season=None, target_episode=None):
    """Поиск нужного файла серии/сезона в списке видеофайлов торрента"""
    if not video_files:
        return None
    if not target_episode and not target_season:
        return video_files[0]
        
    # 1. Точное совпадение сезона и серии
    if target_season and target_episode:
        for f in video_files:
            full_path = f.get('path', '').lower().replace('\\', '/')
            fname = full_path.split('/')[-1]
            pats = [
                rf's0?{target_season}[._ -]*(?:e|ep)0?{target_episode}(?:\D|_|$)',
                rf'0?{target_season}[xх]0?{target_episode}(?:\D|_|$)',
                rf'0?{target_season}\s*[-–—._ ]\s*0?{target_episode}\s*сери[яи]',
                rf'(?:сезон\s*0?{target_season}|0?{target_season}\s*сезон).*(?:сери[яи]\s*0?{target_episode}|0?{target_episode}\s*сери[яи])'
            ]
            if any(re.search(pat, fname) for pat in pats) or any(re.search(pat, full_path) for pat in pats):
                return f

        # Папка содержит сезон, а файл содержит серию
        for f in video_files:
            full_path = f.get('path', '').lower().replace('\\', '/')
            fname = full_path.split('/')[-1]
            dirname = full_path[:-len(fname)] if len(full_path) > len(fname) else ""
            
            season_in_dir = (
                re.search(rf'\b(?:season|сезон)\s*0?{target_season}\b', dirname) or
                re.search(rf'\b0?{target_season}\s*(?:season|сезон)\b', dirname) or
                re.search(rf'\bs0?{target_season}\b', dirname) or
                re.search(rf'[\/\[\_\-]0?{target_season}[\/\]\_\-]', dirname)
            )
            if season_in_dir or target_season == 1:
                ep_pats = [
                    rf'(?:e|ep)0?{target_episode}(?:\D|_|$)',
                    rf'0?{target_episode}\s*сери[яи]',
                    rf'сери[яи]\s*0?{target_episode}',
                    rf'[^0-9]0?{target_episode}[._ -](?:avi|mkv|mp4|ts|m2ts)',
                    rf'\b0?{target_episode}\b'
                ]
                if any(re.search(pat, fname) for pat in ep_pats):
                    return f

    # 2. Если указан только сезон, ищем 1-ю серию этого сезона
    if target_season and not target_episode:
        for f in video_files:
            full_path = f.get('path', '').lower().replace('\\', '/')
            fname = full_path.split('/')[-1]
            pats = [
                rf's0?{target_season}[._ -]*(?:e|ep)0?1(?:\D|_|$)',
                rf'0?{target_season}[xх]0?1(?:\D|_|$)'
            ]
            if any(re.search(pat, fname) for pat in pats) or any(re.search(pat, full_path) for pat in pats):
                return f
        for f in video_files:
            full_path = f.get('path', '').lower().replace('\\', '/')
            fname = full_path.split('/')[-1]
            dirname = full_path[:-len(fname)] if len(full_path) > len(fname) else ""
            season_in_dir = (
                re.search(rf'\b(?:season|сезон)\s*0?{target_season}\b', dirname) or
                re.search(rf'\b0?{target_season}\s*(?:season|сезон)\b', dirname) or
                re.search(rf'\bs0?{target_season}\b', dirname) or
                re.search(rf'[\/\[\_\-]0?{target_season}[\/\]\_\-]', dirname)
            )
            if season_in_dir:
                if re.search(r'\b0?1\b', fname) or re.search(r'(?:e|ep)0?1(?:\D|_|$)', fname):
                    return f

    # 3. Если только номер серии без сезона
    if target_episode and not target_season:
        for f in video_files:
            fname = f.get('path', '').split('/')[-1].split('\\')[-1].lower()
            pats = [
                rf'[._ -]*(?:e|ep)0?{target_episode}(?:\D|_|$)',
                rf'0?{target_episode}\s*сери[яи]',
                rf'сери[яи]\s*0?{target_episode}',
                rf'[^0-9]0?{target_episode}[._ -](?:avi|mkv|mp4|ts|m2ts)'
            ]
            if any(re.search(pat, fname) for pat in pats):
                return f
        if 1 <= target_episode <= len(video_files):
            return video_files[target_episode - 1]

    if target_season or target_episode:
        return None
    return video_files[0] if video_files else None

def get_torrent_playback_info(t_hash, target_season=None, target_episode=None):
    video_exts = ('.mkv', '.mp4', '.avi', '.ts', '.m2ts')
    for _ in range(15):
        try:
            get_req = urllib.request.Request(
                f"{TORRSERVER_URL}/torrents",
                data=json.dumps({"action": "get", "hash": t_hash}).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(get_req, timeout=2) as resp:
                info = json.loads(resp.read().decode('utf-8'))
                files = info.get('file_stats', [])
                if not files and info.get('data'):
                    try:
                        files = json.loads(info['data']).get('TorrServer', {}).get('Files', [])
                    except Exception:
                        pass
                if files:
                    v_files = [f for f in files if any(f.get('path', '').lower().endswith(ext) for ext in video_exts)]
                    clean_v = [f for f in v_files if 'sample' not in f.get('path', '').lower() and 'trailer' not in f.get('path', '').lower()]
                    candidates = clean_v if clean_v else v_files
                    if candidates:
                        candidates.sort(key=lambda x: x.get('path', ''))
                        is_series, valid_videos = classify_torrent_videos(candidates)
                        chosen = find_target_video_file(valid_videos, target_season, target_episode)
                        tag = "Сериал" if is_series else "Фильм"
                        ch_name = chosen.get('path', '') if chosen else 'Unknown'
                        ch_size = round(chosen.get('length', 0)/(1024**2), 1) if chosen else 0
                        print(f"🎯 [{tag}] Выбран файл [ID {chosen.get('id')}]: {ch_name} ({ch_size} MB)", flush=True)
                        return is_series, valid_videos, chosen
        except Exception:
            pass
        time.sleep(0.5)
    return False, [], None

def launch_on_projector(stream_url):
    if get_playback_target() == "pc":
        print(f"💻 Режим воспроизведения: ПК. Запуск на проекторе пропущен, команда направлена на компьютер: {stream_url}", flush=True)
        return
        
    cert = PROJECTOR_CERT
    key = PROJECTOR_KEY
    
    max_attempts = 5
    retry_delay = 4.0
    
    async def _try_launch():
        for attempt in range(1, max_attempts + 1):
            remote = None
            try:
                remote = AndroidTVRemote("HomeCinema", cert, key, PROJECTOR_IP)
                await remote.async_connect()
                print(f"📡 Сервер подключился к проектору {PROJECTOR_IP} (попытка {attempt}/{max_attempts})! Отправляю поток...", flush=True)
                remote.send_launch_app_command(stream_url)
                await asyncio.sleep(2)
                try:
                    remote.disconnect()
                except Exception:
                    pass
                print("🎬 Поток успешно запущен на проекторе!", flush=True)
                return True
            except Exception as e:
                if remote:
                    try:
                        remote.disconnect()
                    except Exception:
                        pass
                if attempt < max_attempts:
                    print(f"⏳ Проектор {PROJECTOR_IP} пока не отвечает ({e}). Повтор через {int(retry_delay)}с (попытка {attempt}/{max_attempts})...", flush=True)
                    await asyncio.sleep(retry_delay)
                else:
                    print(f"⚠️ Не удалось подключиться к проектору после {max_attempts} попыток: {e}", flush=True)
                    return False
        return False

    try:
        asyncio.run(_try_launch())
    except Exception as e:
        print(f"⚠️ Ошибка выполнения launch_on_projector: {e}", flush=True)

def cleanup_inactive_torrents(exclude_hash=None):
    """
    Фоновая очистка старых неактивных раздач в TorrServer.
    Никогда не трогает раздачи, которые прямо сейчас стримятся на устройства.
    """
    try:
        req = urllib.request.Request(
            f"{TORRSERVER_URL}/torrents",
            data=json.dumps({"action": "list"}).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
        for t in data:
            h = t.get('hash')
            if not h or h == exclude_hash:
                continue
                
            stat = t.get('stat', 0)
            stat_str = (t.get('stat_string') or '').lower()
            
            # Защита просмотра: если раздача сейчас активно стримится — НЕ трогаем!
            if stat in (2, 3) or 'working' in stat_str or 'preload' in stat_str:
                print(f"🛡️ Пропуск активной раздачи {h[:8]} ({t.get('title', '')[:40]}) — сейчас воспроизводится на устройстве!", flush=True)
                continue
                
            rem_req = urllib.request.Request(
                f"{TORRSERVER_URL}/torrents",
                data=json.dumps({"action": "rem", "hash": h}).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(rem_req, timeout=5):
                    print(f"🧹 Автоочистка старой неактивной раздачи {h[:8]} ({t.get('title', '')[:40]})", flush=True)
            except Exception as e:
                print(f"⚠️ Ошибка удаления раздачи {h[:8]}: {e}", flush=True)
    except Exception as e:
        print(f"⚠️ Ошибка проверки списка раздач TorrServer: {e}", flush=True)

def play_on_torrserver(movie_name, release, target_season=None, target_episode=None, target_voiceover=None):
    print(f"⚡ Добавляю в TorrServer: {release['title'][:60]}", flush=True)
    payload = json.dumps({
        "action": "add",
        "link": release['download_url'],
        "title": release['title'],
        "save_to_db": True
    }).encode('utf-8')
    req = urllib.request.Request(f"{TORRSERVER_URL}/torrents", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            t_hash = data.get('hash')
            
            # Фоновая очистка неактивных хвостов
            threading.Thread(target=cleanup_inactive_torrents, args=(t_hash,), daemon=True).start()
            
            is_series, video_files, chosen_file = get_torrent_playback_info(t_hash, target_season, target_episode)
            if not chosen_file:
                print(f"⚠️ [TorrServer] Запрошенная серия/файл не найдены в раздаче {t_hash}", flush=True)
                return None
            
            if is_series:
                chosen_id = chosen_file.get('id', 1)
                stream_url = f"{TORRSERVER_URL}/playlist/playlist.m3u?hash={t_hash}&index={chosen_id}"
                print(f"📺 Ссылка на плейлист сериала готова ({len(video_files)} серий, старт с ID {chosen_id}): {stream_url}", flush=True)
            else:
                chosen_id = chosen_file.get('id', 1)
                stream_url = f"{TORRSERVER_URL}/stream/movie.mkv?link={t_hash}&index={chosen_id}&play"
                print(f"🎬 Ссылка на поток фильма готова: {stream_url}", flush=True)
                
            direct_url = f"{TORRSERVER_URL}/stream/movie.mkv?link={t_hash}&index={chosen_id}&play" if is_series else stream_url
            if get_playback_target() == "pc":
                set_pending_playback({
                    "action": "play",
                    "type": "series" if is_series else "movie",
                    "title": movie_name,
                    "url": stream_url,
                    "direct_url": direct_url,
                    "timestamp": time.time()
                })
            else:
                threading.Thread(target=launch_on_projector, args=(stream_url,), daemon=True).start()
            return stream_url
    except Exception as e:
        print(f"❌ Ошибка TorrServer: {e}", flush=True)
        return None

def async_search_and_play(search_query, display_name, target_year=None, orig_title=None, target_season=None, target_episode=None, target_voiceover=None):
    """Асинхронный поиск и мгновенный запуск в фоновом потоке без задержки Алисы"""
    try:
        season_str = f" сезон {target_season}" if target_season else ""
        ep_str = f" серия {target_episode}" if target_episode else ""
        print(f"⚡ Фоновый поиск торрента для «{display_name}»{season_str}{ep_str} (запрос: «{search_query}», год: {target_year})...", flush=True)
        
        best_rel = None
        # 1. Если указан конкретный сезон, запускаем умный поиск сериалов
        if target_season:
            print(f"🎬 Запуск мультипоиска для сериала (целевой сезон S{target_season:02d} + общие паки)...", flush=True)
            best_rel = find_best_series_release(search_query, orig_title=orig_title, target_season=target_season, target_year=target_year, target_voiceover=target_voiceover)

        # 2. Если это фильм (или сериал без указания сезона не найден)
        if not best_rel:
            movies = []
            if target_year:
                movies = search_and_group_movies(f"{search_query} {target_year}", target_year, orig_title, target_voiceover=target_voiceover)
            if not movies:
                movies = search_and_group_movies(search_query, target_year, orig_title, target_voiceover=target_voiceover)
            if not movies and orig_title:
                movies = search_and_group_movies(orig_title, target_year, orig_title, target_voiceover=target_voiceover)
            if not movies:
                simplified = re.sub(r'[:\(\)\d]', '', search_query).strip()
                if simplified != search_query:
                    movies = search_and_group_movies(simplified, target_year, orig_title, target_voiceover=target_voiceover)
            if movies:
                best_rel = movies[0]['best_release']

        if best_rel:
            print(f"🏆 Выбран лучший релиз ({best_rel.get('size_gb')} ГБ, {best_rel.get('seeders')} сид.): {best_rel['title'][:60]}...", flush=True)
            play_on_torrserver(display_name, best_rel, target_season, target_episode, target_voiceover=target_voiceover)
        else:
            print(f"❌ Раздач для «{display_name}» не найдено в фоне", flush=True)
    except Exception as e:
        print(f"❌ Ошибка фонового запуска: {e}", flush=True)
