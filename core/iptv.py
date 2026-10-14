# -*- coding: utf-8 -*-
"""
core/iptv.py - 20 федеральных каналов РФ, авто-Failover, HLS прокси и синхронизация с GitHub
"""

import os
import re
import json
import time
import threading
import urllib.request
import urllib.parse

from core.config import SERVER_LAN_IP, SERVER_PORT, SECRET_TOKEN, PROXY_CHANNELS, TV_CACHE_FILE
from core.nlu import clean_movie_query

TV_CHANNELS = {
    # =========================================================================
    # 1-Й МУЛЬТИПЛЕКС (1 - 10 общедоступные федеральные каналы РФ)
    # =========================================================================
    '1tv': {
        'display_name': 'Первый канал',
        'streams': [
            'http://5.164.24.83/tula/1tv_hi/index.m3u8',
            'http://gtrk-volga.ru/media/hr1/stream1.m3u8',
            'https://stream8.cinerama.uz/1020/index.m3u8',
            'https://serv30.vintera.tv/restream/1_old/playlist.m3u8'
        ],
        'active_stream': 'http://5.164.24.83/tula/1tv_hi/index.m3u8',
        'aliases': ['первый', 'первый канал', '1tv', '1 канал', 'первого']
    },
    'rossiya1': {
        'display_name': 'Россия 1',
        'streams': [
            'https://stream.smotrim.ru/hls2/russia_hd/playlist_6.m3u8',
            'https://live.smotrim.ru/vgtrk/0/russia1-hd/index.m3u8'
        ],
        'active_stream': 'https://stream.smotrim.ru/hls2/russia_hd/playlist_6.m3u8',
        'aliases': ['россия 1', 'россия-1', 'россия один', 'россия', 'россию', 'россию 1']
    },
    'match': {
        'display_name': 'Матч ТВ',
        'streams': [
            'http://stream.mcquack.net/169/index.m3u8',
            'http://stream.mcquack.net/142/index.m3u8',
            'https://fs.uplink.kz/match_planeta/mono.m3u8?token=onlinetv'
        ],
        'active_stream': 'http://stream.mcquack.net/169/index.m3u8',
        'aliases': ['матч', 'матч тв', 'матч-тв', 'матчтв', 'спорт']
    },
    'ntv': {
        'display_name': 'НТВ',
        'streams': [
            'https://cdn.ntv.ru/ntv-msk_hd/index.m3u8',
            'https://bl.rutube.ru/livestream/c37cd74192c6bc3d6cd6077c0c4fd686/index.m3u8?e=2077050299&s=HSWg81JrQ3OqmwuWkEIDAQ&scheme=https',
            'http://cdn.ntv.ru/ntv0_hd/tracks-v1a1/rewind-7150.m3u8'
        ],
        'active_stream': 'https://cdn.ntv.ru/ntv-msk_hd/index.m3u8',
        'aliases': ['нтв', 'ntv']
    },
    '5tv': {
        'display_name': 'Пятый канал',
        'streams': [
            'http://178.134.1.158:8081/5channel/index.m3u8',
            'https://fs.uplink.kz/5_kanal/mono.m3u8?token=onlinetv'
        ],
        'active_stream': 'http://178.134.1.158:8081/5channel/index.m3u8',
        'aliases': ['пятый', 'пятый канал', '5 канал', 'пятерка', 'пятерку']
    },
    'kultura': {
        'display_name': 'Россия-Культура',
        'streams': [
            'https://stream.smotrim.ru/hls2/russia_k/playlist_5.m3u8',
            'https://live.smotrim.ru/vgtrk/0/kultura-hd/index.m3u8',
            'http://stream.mcquack.net/229/index.m3u8'
        ],
        'active_stream': 'https://stream.smotrim.ru/hls2/russia_k/playlist_5.m3u8',
        'aliases': ['культура', 'россия культура', 'россия-к', 'россия к', 'культуру']
    },
    'rossiya24': {
        'display_name': 'Россия 24',
        'streams': [
            'https://live.smotrim.ru/vgtrk/0/russia24-hd/index.m3u8',
            'https://stream.smotrim.ru/hls2/russia24nl_smotrim/playlist_5.m3u8'
        ],
        'active_stream': 'https://live.smotrim.ru/vgtrk/0/russia24-hd/index.m3u8',
        'aliases': ['россия 24', 'россия-24', 'вести 24', 'россия двадцать четыре']
    },
    'karusel': {
        'display_name': 'Карусель',
        'streams': [
            f"http://{SERVER_LAN_IP}:{SERVER_PORT}/iptv/karusel.m3u8?secret={SECRET_TOKEN}",
            'http://flussonic.linkintel.ru/Karusel/index.m3u8',
            'https://stream.smotrim.ru/hls2/karusel/playlist_3.m3u8',
            'http://185.37.150.46/Karusel/index.m3u8'
        ],
        'active_stream': f"http://{SERVER_LAN_IP}:{SERVER_PORT}/iptv/karusel.m3u8?secret={SECRET_TOKEN}",
        'aliases': ['карусель', 'детский', 'каруселька', 'карусельку']
    },
    'otr': {
        'display_name': 'ОТР',
        'streams': [
            'http://flussonic.linkintel.ru/otr/index.m3u8',
            'https://flussonic.mkpnet.ru/tv-22ed9087cd194d2b/video.m3u8'
        ],
        'active_stream': 'http://flussonic.linkintel.ru/otr/index.m3u8',
        'aliases': ['отр']
    },
    'tvc': {
        'display_name': 'ТВ Центр',
        'streams': [
            'http://flussonic.linkintel.ru/tvc/index.m3u8',
            'http://tvc-hls.cdnvideo.ru/tvc-res/smil:vd9221_2.smil/playlist.m3u8',
            'https://tvc-hls.cdnvideo.ru/tvc-res/smil:vd9221.smil/playlist.m3u8'
        ],
        'active_stream': 'http://flussonic.linkintel.ru/tvc/index.m3u8',
        'aliases': ['твц', 'тв центр', 'тв-центр', 'твцентр']
    },

    # =========================================================================
    # 2-Й МУЛЬТИПЛЕКС (11 - 20 общедоступные федеральные каналы РФ)
    # =========================================================================
    'ren': {
        'display_name': 'РЕН ТВ',
        'streams': [
            f"http://{SERVER_LAN_IP}:{SERVER_PORT}/iptv/ren.m3u8?secret={SECRET_TOKEN}",
            'http://flussonic.linkintel.ru/ren_tv/index.m3u8',
            'http://185.23.80.23:8080/REN/index.m3u8',
            'http://194.152.35.17/ren_tv/index.m3u8'
        ],
        'active_stream': f"http://{SERVER_LAN_IP}:{SERVER_PORT}/iptv/ren.m3u8?secret={SECRET_TOKEN}",
        'aliases': ['рен', 'рен тв', 'рен-тв', 'рентв']
    },
    'spas': {
        'display_name': 'Спас',
        'streams': [
            'https://tvspas.mediacdn.ru/cdn/spas/playlist.m3u8',
            'https://bonusspas.mediacdn.ru/cdn/spas/playlist.m3u8'
        ],
        'active_stream': 'https://tvspas.mediacdn.ru/cdn/spas/playlist.m3u8',
        'aliases': ['спас', 'спаса', 'тв спас', 'канал спас']
    },
    'sts': {
        'display_name': 'СТС',
        'streams': [
            'http://stream.mcquack.net/138/index.m3u8',
            'http://flussonic.linkintel.ru/sts/index.m3u8',
            'http://178.134.1.158:8081/CTC/index.m3u8'
        ],
        'active_stream': 'http://stream.mcquack.net/138/index.m3u8',
        'aliases': ['стс', 'sts', 'стс hd', 'sts hd']
    },
    'domashniy': {
        'display_name': 'Домашний',
        'streams': [
            'http://stream.mcquack.net/227/index.m3u8',
            'https://fs.uplink.kz/domashniy/mono.m3u8?token=onlinetv'
        ],
        'active_stream': 'http://stream.mcquack.net/227/index.m3u8',
        'aliases': ['домашний', 'домашнего']
    },
    'tv3': {
        'display_name': 'ТВ-3',
        'streams': [
            'http://stream.mcquack.net/136/index.m3u8',
            'http://flussonic.linkintel.ru/tv-3/index.m3u8'
        ],
        'active_stream': 'http://stream.mcquack.net/136/index.m3u8',
        'aliases': ['тв3', 'тв 3', 'тв-3', 'tv3', 'tv 3', 'tv-3']
    },
    'friday': {
        'display_name': 'Пятница!',
        'streams': [
            'http://stream.mcquack.net/181/index.m3u8',
            'http://flussonic.linkintel.ru/Pyatnica/index.m3u8'
        ],
        'active_stream': 'http://stream.mcquack.net/181/index.m3u8',
        'aliases': ['пятница', 'пятницу', 'friday']
    },
    'zvezda': {
        'display_name': 'Звезда',
        'streams': [
            'http://tvchannelstream1.tvzvezda.ru/cdn/tvzvezda/playlist_hdhigh.m3u8',
            'https://tvchannelstream1.tvzvezda.ru/cdn/tvzvezda/playlist.m3u8',
            'https://tvzvezda.bonus-tv.ru/cdn/tvzvezda/playlist.m3u8'
        ],
        'active_stream': 'http://tvchannelstream1.tvzvezda.ru/cdn/tvzvezda/playlist_hdhigh.m3u8',
        'aliases': ['звезда', 'звезду']
    },
    'mir': {
        'display_name': 'МИР',
        'streams': [
            'http://hls.mirtv.cdnvideo.ru/mirtv-parampublish/mirtv_2500/playlist.m3u8',
            'http://hls.mirtv.cdnvideo.ru/mirtv-parampublish/mir24_2500/playlist.m3u8'
        ],
        'active_stream': 'http://hls.mirtv.cdnvideo.ru/mirtv-parampublish/mirtv_2500/playlist.m3u8',
        'aliases': ['мир', 'мир 24', 'mir']
    },
    'tnt': {
        'display_name': 'ТНТ',
        'streams': [
            'http://stream.mcquack.net/135/index.m3u8',
            'https://bl.rutube.ru/livestream/546602986e6a424d74d594876ddb3f04/index.m3u8?s=K-z3nz49R1oGQ-5yPSd8pg&e=2082157024&scheme=https',
            'http://flussonic.linkintel.ru/tnt/index.m3u8'
        ],
        'active_stream': 'http://stream.mcquack.net/135/index.m3u8',
        'aliases': ['тнт', 'tnt']
    },
    'muztv': {
        'display_name': 'Муз-ТВ',
        'streams': [
            'http://stream.mcquack.net/86/index.m3u8',
            'https://streaming102.interskytech.com/live/618.m3u8',
            'http://46.32.176.50/muztv/index.m3u8',
            'https://stream8.cinerama.uz/1200/tracks-v1a1/mono.m3u8'
        ],
        'active_stream': 'http://stream.mcquack.net/86/index.m3u8',
        'aliases': ['муз тв', 'муз-тв', 'музтв']
    }
}

CHANNEL_M3U_CANONICAL = {
    '1tv': ['первый', 'первый канал', '1tv', '1 канал', 'первый канал hd'],
    'rossiya1': ['россия 1', 'россия-1', 'россия 1 hd', 'россия-1 hd'],
    'match': ['матч', 'матч тв', 'матч-тв', 'матч!'],
    'ntv': ['нтв', 'ntv', 'нтв hd', 'ntv hd'],
    '5tv': ['пятый', 'пятый канал', '5 канал', 'пятый канал hd'],
    'kultura': ['россия-культура', 'россия культура', 'россия-к', 'россия к'],
    'rossiya24': ['россия 24', 'россия-24', 'вести 24'],
    'karusel': ['карусель', 'карусель hd'],
    'otr': ['отр', 'отр hd'],
    'tvc': ['твц', 'тв центр', 'тв-центр', 'тв центр hd'],
    'ren': ['рен', 'рен тв', 'рен-тв', 'рентв'],
    'spas': ['спас', 'спас hd'],
    'sts': ['стс', 'sts', 'стс hd', 'sts hd'],
    'domashniy': ['домашний', 'домашний hd'],
    'tv3': ['тв3', 'тв 3', 'тв-3', 'tv3', 'tv 3', 'tv-3'],
    'friday': ['пятница', 'пятница!', 'friday'],
    'zvezda': ['звезда', 'звезда hd'],
    'mir': ['мир', 'мир hd'],
    'tnt': ['тнт', 'tnt', 'тнт hd', 'tnt hd'],
    'muztv': ['муз тв', 'муз-тв', 'музтв']
}

def check_stream_alive(url, timeout=1.5, referer=None):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        probe_url = url
        if referer:
            headers['Referer'] = referer
        elif 'skygo.mn' in url:
            headers['Referer'] = 'http://skygo.mn/'
        elif '/iptv/ren' in url:
            probe_url = PROXY_CHANNELS['ren']['url']
            headers['Referer'] = PROXY_CHANNELS['ren']['referer']
        elif '/iptv/karusel' in url:
            probe_url = PROXY_CHANNELS['karusel']['url']
            headers['Referer'] = PROXY_CHANNELS['karusel']['referer']
        req = urllib.request.Request(probe_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                content = r.read(1024).decode('utf-8', errors='ignore')
                if 'block' not in content.lower():
                    return True
    except Exception:
        pass
    return False

def save_tv_cache():
    try:
        cache_data = {}
        for ch_id, ch in TV_CHANNELS.items():
            cache_data[ch_id] = {
                'active_stream': ch.get('active_stream'),
                'streams': ch.get('streams', [])
            }
        with open(TV_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[-] Ошибка сохранения кэша ТВ: {e}", flush=True)

def load_tv_cache():
    if os.path.exists(TV_CACHE_FILE):
        try:
            with open(TV_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            for ch_id, data in cache_data.items():
                if ch_id in TV_CHANNELS:
                    cached_streams = data.get('streams', [])
                    for s in cached_streams:
                        if s not in TV_CHANNELS[ch_id]['streams']:
                            TV_CHANNELS[ch_id]['streams'].append(s)
                    cached_active = data.get('active_stream')
                    if cached_active and cached_active in TV_CHANNELS[ch_id]['streams']:
                        TV_CHANNELS[ch_id]['active_stream'] = cached_active
            print(f"💾 Загружен кэш ТВ каналов из {TV_CACHE_FILE}", flush=True)
        except Exception as e:
            print(f"[-] Ошибка загрузки кэша ТВ: {e}", flush=True)

def get_channel_stream(ch_dict):
    """
    Получение рабочего потока с мгновенным Failover (самовосстановлением).
    Если текущий активный поток недоступен, автоматически переключается на первый работающий резерв.
    """
    streams = ch_dict.get('streams', [])
    if not streams:
        return ch_dict.get('active_stream', '')

    active = ch_dict.get('active_stream')
    if active and check_stream_alive(active, timeout=1.0):
        return active

    print(f"⚠️ Поток {active} недоступен. Запуск поиска резервного потока для «{ch_dict['display_name']}»...", flush=True)
    for s in streams:
        if s == active:
            continue
        if check_stream_alive(s, timeout=1.5):
            ch_dict['active_stream'] = s
            print(f"🔄 [Failover] Успешно переключено на резерв: «{ch_dict['display_name']}» -> {s}", flush=True)
            save_tv_cache()
            return s

    print(f"❌ Ни один резервный поток для «{ch_dict['display_name']}» не отвечает.", flush=True)
    return None

def update_tv_from_github():
    """
    Фоновое автообновление и валидация потоков из проверенных GitHub репозиториев
    (ngrch/iptv, iptv-org/iptv).
    """
    github_sources = [
        'https://ngrch.github.io/iptv/ru.m3u',
        'https://iptv-org.github.io/iptv/countries/ru.m3u'
    ]
    print("🛰️ [IPTV Auto-Update] Проверка новых и резервных потоков с GitHub...", flush=True)
    updated = False
    
    # 1. Валидация текущих каналов
    for ch_id, ch in TV_CHANNELS.items():
        curr = ch.get('active_stream')
        if curr and not check_stream_alive(curr, timeout=1.5):
            print(f"⚠️ [HealthCheck] Канал {ch['display_name']} не отвечает по основному потоку. Переключение...", flush=True)
            get_channel_stream(ch)
            updated = True

    # 2. Опрос GitHub плейлистов со строгим каноническим сопоставлением
    for src in github_sources:
        try:
            req = urllib.request.Request(src, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                content = r.read().decode('utf-8', errors='ignore')
            lines = content.splitlines()
            for idx, line in enumerate(lines):
                if line.startswith('#EXTINF') and idx + 1 < len(lines):
                    url = lines[idx + 1].strip()
                    if not url.startswith('http') or 'zabava' in url or 'ngenix' in url:
                        continue
                    ch_title = line.split(',')[-1].strip().lower()
                    
                    # Нормализация
                    norm = re.sub(r'\(\d+\)', '', ch_title)
                    norm = re.sub(r'\(\d+p\)', '', norm)
                    norm = re.sub(r'\+[1-9]', '', norm)
                    norm = re.sub(r'[\(\)\[\]]', '', norm)
                    norm = re.sub(r'\s+', ' ', norm).strip()

                    for ch_id, names in CHANNEL_M3U_CANONICAL.items():
                        if norm in names and ch_id in TV_CHANNELS:
                            ch = TV_CHANNELS[ch_id]
                            if url not in ch['streams']:
                                if check_stream_alive(url, timeout=2.0):
                                    ch['streams'].append(url)
                                    print(f"➕ [GitHub Sync] Добавлен проверенный резервный поток для {ch['display_name']}: {url}", flush=True)
                                    updated = True
                            break
        except Exception as e:
            print(f"⚠️ [IPTV Auto-Update] Ошибка загрузки {src}: {e}", flush=True)

    if updated:
        save_tv_cache()
    print("✅ [IPTV Auto-Update] Синхронизация завершена", flush=True)

def start_tv_background_service():
    def _loop():
        time.sleep(10)
        while True:
            try:
                update_tv_from_github()
            except Exception as e:
                print(f"[-] Ошибка в фоновом обновлении ТВ: {e}", flush=True)
            time.sleep(12 * 3600)
    threading.Thread(target=_loop, daemon=True).start()

def extract_tv_channel(text):
    """
    Распознавание запроса на просмотр телеканала.
    Возвращает: (is_tv: bool, channel_dict: dict|None)
    """
    t_lower = text.lower().strip()
    
    if re.search(r'\b(фильм[а-я]*|сериал[а-я]*|кино|мульт[а-я]*|аниме)\b', t_lower):
        return False, None
        
    has_tv_marker = bool(re.search(r'\b(телеканал[а-я]*|канал[а-я]*|прям(ой|ом)\s+эфир[а-я]*|эфир)\b', t_lower))
    
    cleaned = clean_movie_query(t_lower)
    cleaned_no_tv = re.sub(r'\b(телеканал[а-я]*|канал[а-я]*|прям(ой|ом)\s+эфир[а-я]*|эфир)\b', '', cleaned).strip()
    cleaned_no_tv = re.sub(r'\s+', ' ', cleaned_no_tv).strip()
    
    for ch_id, ch in TV_CHANNELS.items():
        for alias in ch['aliases']:
            if has_tv_marker:
                if alias == cleaned_no_tv or f" {alias} " in f" {cleaned_no_tv} " or cleaned_no_tv.startswith(alias):
                    return True, ch
            if cleaned == alias or cleaned_no_tv == alias:
                return True, ch
                
    return False, None

def resolve_upstream_url(base_url, rel_url):
    if rel_url.startswith('http://') or rel_url.startswith('https://'):
        return rel_url
    if rel_url.startswith('/'):
        p = urllib.parse.urlparse(base_url)
        return f"{p.scheme}://{p.netloc}{rel_url}"
    return base_url.rsplit('/', 1)[0] + '/' + rel_url

def rewrite_m3u8(base_url, m3u8_text, ref_url, server_host):
    lines = []
    for line in m3u8_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            def replace_tag_uri(m):
                u = m.group(1)
                abs_u = resolve_upstream_url(base_url, u)
                proxied = f"http://{server_host}/iptv/proxy?url={urllib.parse.quote(abs_u)}&ref={urllib.parse.quote(ref_url)}&secret={SECRET_TOKEN}"
                return f'URI="{proxied}"'
            line = re.sub(r'URI="([^"]+)"', replace_tag_uri, line)
            lines.append(line)
        else:
            abs_u = resolve_upstream_url(base_url, line)
            proxied = f"http://{server_host}/iptv/proxy?url={urllib.parse.quote(abs_u)}&ref={urllib.parse.quote(ref_url)}&secret={SECRET_TOKEN}"
            lines.append(proxied)
    return "\n".join(lines)
