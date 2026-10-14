#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HomeServer & Alice Cinema Bridge - Главная точка входа вебхука
Слушает запросы Яндекс Диалогов (Алиса), маршрутизирует интенты и управляет воспроизведением.
"""

import io
import os
import sys
import json
import time
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Корректный вывод UTF-8 в консоли
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Импорты модулей ядра
from core.config import (
    SERVER_LAN_IP, SERVER_PORT, SECRET_TOKEN, ALWAYS_CONFIRM, PROXY_CHANNELS,
    get_playback_target, set_playback_target,
    get_pending_playback, set_pending_playback, pop_pending_playback,
    active_disambiguations, disambiguation_lock
)
from core.nlu import (
    is_exit_command, extract_youtube_query, extract_voiceover,
    extract_season_and_episode, clean_movie_query
)
from core.iptv import (
    load_tv_cache, start_tv_background_service, extract_tv_channel,
    get_channel_stream, rewrite_m3u8
)
from core.kinopoisk import resolve_via_kinopoisk, resolve_user_choice
from core.playback import launch_on_projector, async_search_and_play


class YandexDialogsHandler(BaseHTTPRequestHandler):
    def check_auth(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        token = qs.get('secret', [''])[0]
        return token == SECRET_TOKEN

    def serve_iptv_channel(self, ch_id, host):
        info = PROXY_CHANNELS.get(ch_id)
        if not info:
            self.send_response(404)
            self.end_headers()
            return
        self.serve_iptv_upstream(info['url'], info['referer'], host)

    def serve_iptv_upstream(self, target_url, ref, host):
        p_url = urllib.parse.urlparse(target_url)
        if p_url.scheme not in ('http', 'https'):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid URL scheme"}')
            return
        hostname = (p_url.hostname or '').lower()
        if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1') or hostname.startswith('192.168.') or hostname.startswith('10.'):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"error": "Access to local network prohibited"}')
            return

        headers = {'User-Agent': 'Mozilla/5.0'}
        if ref:
            headers['Referer'] = ref
        try:
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                content_type = resp.headers.get('Content-Type', '')
                if 'mpegurl' in content_type or target_url.endswith('.m3u8'):
                    body = resp.read().decode('utf-8', errors='ignore')
                    body_rewritten = rewrite_m3u8(target_url, body, ref, host).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                    self.send_header('Content-Length', str(len(body_rewritten)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(body_rewritten)
                else:
                    self.send_response(200)
                    self.send_header('Content-Type', content_type or 'video/MP2T')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    if 'Content-Length' in resp.headers:
                        self.send_header('Content-Length', resp.headers['Content-Length'])
                    self.end_headers()
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            break
        except Exception as e:
            print(f"❌ [IPTV Proxy Error] {target_url[:80]}: {e}", flush=True)
            try:
                self.send_response(502)
                self.end_headers()
                self.wfile.write(f"Proxy error: {e}".encode('utf-8'))
            except Exception:
                pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        host = self.headers.get('Host', f"{SERVER_LAN_IP}:{SERVER_PORT}")

        if not self.check_auth():
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"error": "Forbidden"}')
            return

        # IPTV Stream Proxy (для локальных плееров)
        if parsed.path == '/iptv/ren.m3u8':
            self.serve_iptv_channel('ren', host)
            return
        elif parsed.path == '/iptv/karusel.m3u8':
            self.serve_iptv_channel('karusel', host)
            return
        elif parsed.path == '/iptv/proxy':
            target_url = qs.get('url', [''])[0]
            ref = qs.get('ref', [''])[0]
            if not target_url:
                self.send_response(400)
                self.end_headers()
                return
            self.serve_iptv_upstream(target_url, ref, host)
            return

        # Переключение целевого экрана (проектор / пк)
        if parsed.path == '/target':
            set_val = qs.get('set', [None])[0]
            if set_val in ['pc', 'projector']:
                set_playback_target(set_val)
            elif set_val == 'toggle':
                curr = get_playback_target()
                set_playback_target('projector' if curr == 'pc' else 'pc')
            curr = get_playback_target()
            target_name = "компьютере" if curr == "pc" else "проекторе"
            payload = json.dumps({
                'status': 'ok',
                'target': curr,
                'device_name': target_name
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(payload)
            return

        # Опрос команд воспроизведения клиентом ПК
        if parsed.path == '/poll':
            item = pop_pending_playback()
            if item:
                payload = json.dumps(item, ensure_ascii=False).encode('utf-8')
            else:
                payload = json.dumps({"status": "idle"}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(payload)
            return

        # Healthcheck для сторожа и внешнего мониторинга
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'ok', 'service': 'alice-cinema-bridge'}).encode('utf-8'))

    def do_POST(self):
        t0 = time.time()
        if not self.check_auth():
            print("⛔ Отклонен неавторизованный запрос!", flush=True)
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"error": "Forbidden"}')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 65536:
            self.send_response(413)
            self.end_headers()
            self.wfile.write(b'{"error": "Payload Too Large"}')
            return
        raw_body = self.rfile.read(content_length).decode('utf-8', errors='ignore')
        
        try:
            req_data = json.loads(raw_body)
        except Exception:
            req_data = {}

        request_obj = req_data.get('request', {})
        command = request_obj.get('command', '').strip()
        session_obj = req_data.get('session', {})
        session_id = session_obj.get('session_id', 'default')
        is_new_session = session_obj.get('new', False)
        print(f"📥 Запрос от Алисы: «{command}» (сессия: {session_id[:8]}...)", flush=True)
        
        curr_target = get_playback_target()
        target_device_name = "компьютере" if curr_target == "pc" else "проекторе"

        # 0. Команда выхода из навыка на любом этапе диалога
        if is_exit_command(command):
            with disambiguation_lock:
                active_disambiguations.pop(session_id, None)
            
            cmd_clean = command.lower().strip()
            if any(w in cmd_clean for w in ['хуй', 'жоп', 'пизд', 'нахер', 'заткнись']):
                response_text = "Поняла, ухожу."
            else:
                response_text = "Хорошо, выхожу из кинозала."
            
            resp_payload = {
                "response": {
                    "text": response_text,
                    "end_session": True
                },
                "version": "1.0"
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(resp_payload, ensure_ascii=False).encode('utf-8'))
            print(f"🚪 Выход из навыка по команде: «{command}» (сессия закрыта)", flush=True)
            return

        # Проверка активного диалога уточнения
        pending_data = None
        with disambiguation_lock:
            now = time.time()
            expired = [sid for sid, data in active_disambiguations.items() if now - data.get('timestamp', 0) > 600]
            for sid in expired:
                del active_disambiguations[sid]

            if not is_new_session and session_id in active_disambiguations:
                pending_data = active_disambiguations[session_id]

        response_text = ""
        end_session = False
        new_pending_data = None

        # Если в активном диалоге пришла новая команда на включение — сбрасываем старый контекст
        if pending_data and bool(re.search(r'\b(включ[а-я]*|постав[а-я]*|запуст[а-я]*|покаж[а-я]*|найд[а-я]*|попроси[а-я]*|вруб[а-я]*|ютуб|youtube|ютюб)\b', command.lower())):
            with disambiguation_lock:
                active_disambiguations.pop(session_id, None)
            pending_data = None

        if is_new_session and not command:
            response_text = "Привет! Какой фильм включить на экране?"
            end_session = False
        elif not command:
            response_text = "Я не расслышала название. Скажи, например: включи Интерстеллар."
            end_session = False
        elif pending_data:
            cmd_lower = command.lower()
            if any(w in cmd_lower for w in ['отмена', 'не надо', 'стоп', 'хватит', 'назад', 'нет', 'не то']):
                with disambiguation_lock:
                    active_disambiguations.pop(session_id, None)
                response_text = "Хорошо, отменила. Какой фильм включить?"
                end_session = False
            elif pending_data.get('action') == 'confirm':
                chosen = pending_data.get('candidate')
                if any(w in cmd_lower for w in ['да', 'давай', 'включай', 'ага', 'конечно', 'верно', 'запускай', 'ок']):
                    with disambiguation_lock:
                        active_disambiguations.pop(session_id, None)
                    t_season = pending_data.get('target_season')
                    t_episode = pending_data.get('target_episode')
                    t_voiceover = pending_data.get('target_voiceover')
                    vo_phrase = f" в озвучке {t_voiceover['display_name']}" if t_voiceover else ""
                    ep_phrase = ""
                    if t_season and t_episode:
                        ep_phrase = f", {t_season} сезон, {t_episode} серия"
                    elif t_episode:
                        ep_phrase = f", {t_episode} серия"
                    elif t_season:
                        ep_phrase = f", {t_season} сезон"
                    rating_str = f" Рейтинг Кинопоиска: {chosen['rating']}." if chosen.get('rating') else ""
                    response_text = f"Включаю {chosen['display']}{ep_phrase}{vo_phrase} на {target_device_name}.{rating_str} Приятного просмотра!"
                    end_session = True
                    threading.Thread(target=async_search_and_play, args=(
                        chosen['name'], chosen['display'], chosen.get('year'), chosen.get('alt'),
                        t_season, t_episode, t_voiceover
                    ), daemon=True).start()
                else:
                    with disambiguation_lock:
                        active_disambiguations.pop(session_id, None)
                    response_text = "Хорошо, не включаю. Какой фильм или сериал включить?"
                    end_session = False
            elif pending_data.get('action') == 'disambiguate':
                candidates = pending_data.get('candidates', [])
                chosen = resolve_user_choice(command, candidates)
                if chosen:
                    with disambiguation_lock:
                        active_disambiguations.pop(session_id, None)
                    if chosen.get('unreleased'):
                        response_text = f"Фильм {chosen['name']} ещё не вышел в прокат (премьера в {chosen['year']} году). Какой фильм включить?"
                        end_session = False
                    else:
                        t_season = pending_data.get('target_season')
                        t_episode = pending_data.get('target_episode')
                        t_voiceover = pending_data.get('target_voiceover')
                        vo_phrase = f" в озвучке {t_voiceover['display_name']}" if t_voiceover else ""
                        ep_phrase = ""
                        if t_season and t_episode:
                            ep_phrase = f", {t_season} сезон, {t_episode} серия"
                        elif t_episode:
                            ep_phrase = f", {t_episode} серия"
                        elif t_season:
                            ep_phrase = f", {t_season} сезон"
                        rating_str = f" Рейтинг Кинопоиска: {chosen['rating']}." if chosen.get('rating') else ""
                        response_text = f"Включаю {chosen['display']}{ep_phrase}{vo_phrase} на {target_device_name}.{rating_str} Приятного просмотра!"
                        end_session = True
                        threading.Thread(target=async_search_and_play, args=(
                            chosen['name'], chosen['display'], chosen.get('year'), chosen.get('alt'),
                            t_season, t_episode, t_voiceover
                        ), daemon=True).start()
                else:
                    response_text = "Скажи «первый» или «второй», либо скажи «выход»."
                    end_session = False
                    new_pending_data = pending_data
        else:
            # 1. Проверяем YouTube
            is_yt, yt_query = extract_youtube_query(command)
            # 2. Проверяем ТВ-канал
            is_tv, tv_ch = extract_tv_channel(command)
            
            if is_yt:
                if yt_query:
                    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(yt_query)}"
                    print(f"📺 Запрос YouTube: «{yt_query}» -> {search_url}", flush=True)
                    response_text = f"Ищу «{yt_query}» на YouTube на {target_device_name}. Выбирай!"
                    end_session = True
                    if curr_target == 'pc':
                        set_pending_playback({
                            "action": "play",
                            "type": "youtube",
                            "title": f"YouTube: {yt_query}",
                            "url": search_url,
                            "timestamp": time.time()
                        })
                    else:
                        threading.Thread(target=launch_on_projector, args=(search_url,), daemon=True).start()
                else:
                    print("📺 Запуск главного экрана YouTube", flush=True)
                    response_text = f"Открываю YouTube на {target_device_name}."
                    end_session = True
                    if curr_target == 'pc':
                        set_pending_playback({
                            "action": "play",
                            "type": "youtube",
                            "title": "YouTube",
                            "url": "https://www.youtube.com",
                            "timestamp": time.time()
                        })
                    else:
                        threading.Thread(target=launch_on_projector, args=("https://www.youtube.com",), daemon=True).start()
            elif is_tv:
                stream_url = get_channel_stream(tv_ch)
                if not stream_url:
                    response_text = f"К сожалению, прямой эфир канала {tv_ch['display_name']} сейчас недоступен."
                    end_session = True
                else:
                    print(f"📺 Запрос ТВ-канала: «{tv_ch['display_name']}» -> {stream_url}", flush=True)
                    response_text = f"Включаю телеканал {tv_ch['display_name']} на {target_device_name}."
                    end_session = True
                    if curr_target == 'pc':
                        set_pending_playback({
                            "action": "play",
                            "type": "tv",
                            "title": tv_ch['display_name'],
                            "url": stream_url,
                            "direct_url": stream_url,
                            "timestamp": time.time()
                        })
                    else:
                        threading.Thread(target=launch_on_projector, args=(stream_url,), daemon=True).start()
            else:
                # 3. Фильм или сериал
                target_voiceover, cleaned_cmd = extract_voiceover(command)
                target_season, target_episode, cleaned_cmd = extract_season_and_episode(cleaned_cmd)
                raw_query = clean_movie_query(cleaned_cmd)
                vo_phrase = f" в озвучке {target_voiceover['display_name']}" if target_voiceover else ""
                
                ep_phrase = ""
                if target_season and target_episode:
                    ep_phrase = f", {target_season} сезон, {target_episode} серия"
                elif target_episode:
                    ep_phrase = f", {target_episode} серия"
                elif target_season:
                    ep_phrase = f", {target_season} сезон"

                if not raw_query:
                    response_text = "Я не расслышала название фильма или сериала. Скажи, например: включи Интерстеллар."
                    end_session = False
                else:
                    # Поиск и ранжирование Кинопоиска
                    kp_list, is_definitive, reason = resolve_via_kinopoisk(raw_query)
                    
                    if kp_list and kp_list[0].get('unreleased'):
                        top_unrel = kp_list[0]
                        other_released = [k for k in kp_list[1:] if not k.get('unreleased')]
                        alt_hint = f" Включить {other_released[0]['display']}?" if other_released else ""
                        response_text = f"Фильм {top_unrel['name']} ещё не вышел в прокат (премьера в {top_unrel['year']} году).{alt_hint}"
                        end_session = False
                        if other_released:
                            new_pending_data = {
                                "action": "disambiguate",
                                "candidates": other_released[:2],
                                "target_season": target_season,
                                "target_episode": target_episode,
                                "target_voiceover": target_voiceover
                            }
                    elif kp_list:
                        top_kp = kp_list[0]
                        print(f"🎯 Кинопоиск ({len(kp_list)} канд.) для «{raw_query}»:", flush=True)
                        for idx, c in enumerate(kp_list[:3]):
                            print(f"   [{idx+1}] {c['display']} | Баллы: {c.get('score', 0)} | Совпало слов: {c.get('matched_count', 0)} | Голосов: {c.get('votes', 0)}", flush=True)
                        print(f"   👉 Решение: {'Мгновенный запуск' if is_definitive else 'Уточнение вариантов'} ({reason})", flush=True)
                        
                        if ALWAYS_CONFIRM:
                            rating_str = f" с рейтингом {top_kp['rating']}" if top_kp.get('rating') else ""
                            response_text = f"Включить «{top_kp['name']}» {top_kp.get('year', '')} года{ep_phrase}{vo_phrase}{rating_str} на {target_device_name}?"
                            end_session = False
                            new_pending_data = {
                                "action": "confirm",
                                "candidate": top_kp,
                                "target_season": target_season,
                                "target_episode": target_episode,
                                "target_voiceover": target_voiceover
                            }
                        else:
                            if not is_definitive:
                                major_parts = [
                                    k for k in kp_list 
                                    if not k.get('unreleased') 
                                    and k.get('votes', 0) > 30000 
                                    and k.get('type') in ('movie', 'cartoon', 'anime', 'tv-series', 'animated-series')
                                ]
                                distinct_parts = []
                                seen_keys = set()
                                for p in major_parts:
                                    pkey = (p['name'].lower(), p.get('year'))
                                    if pkey not in seen_keys:
                                        seen_keys.add(pkey)
                                        distinct_parts.append(p)
                                        
                                candidates = distinct_parts[:3] if len(distinct_parts) >= 2 else kp_list[:3]
                                cand_str = ", ".join([f"{idx} — {c['display']}" for idx, c in enumerate(candidates, 1)])
                                response_text = f"Я нашла варианты: {cand_str}. Какой включить?"
                                end_session = False
                                new_pending_data = {
                                    "action": "disambiguate",
                                    "candidates": candidates,
                                    "target_season": target_season,
                                    "target_episode": target_episode,
                                    "target_voiceover": target_voiceover
                                }
                            else:
                                rating_str = f" Рейтинг Кинопоиска: {top_kp['rating']}." if top_kp.get('rating') else ""
                                response_text = f"Включаю {top_kp['display']}{ep_phrase}{vo_phrase} на {target_device_name}.{rating_str} Приятного просмотра!"
                                end_session = True
                                threading.Thread(target=async_search_and_play, args=(
                                    top_kp['name'], top_kp['display'], top_kp.get('year'), top_kp.get('alt'),
                                    target_season, target_episode, target_voiceover
                                ), daemon=True).start()
                    else:
                        response_text = f"Включаю «{raw_query}»{ep_phrase}{vo_phrase} на {target_device_name}. Приятного просмотра!"
                        end_session = True
                        threading.Thread(target=async_search_and_play, args=(
                            raw_query, raw_query.capitalize(), None, None,
                            target_season, target_episode, target_voiceover
                        ), daemon=True).start()

        if new_pending_data:
            with disambiguation_lock:
                new_pending_data["timestamp"] = time.time()
                active_disambiguations[session_id] = new_pending_data

        resp_payload = {
            "response": {
                "text": response_text,
                "end_session": end_session
            },
            "version": "1.0"
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(resp_payload, ensure_ascii=False).encode('utf-8'))
        elapsed = round(time.time() - t0, 3)
        print(f"⚡ Ответ Алисе отправлен за {elapsed} сек! (текст: «{response_text[:60]}...»)", flush=True)


if __name__ == '__main__':
    load_tv_cache()
    start_tv_background_service()
    server = ThreadingHTTPServer(('0.0.0.0', SERVER_PORT), YandexDialogsHandler)
    print(f"🚀 Cinema Webhook Server v3.0 (Modular Core) запущен на порту {SERVER_PORT}...", flush=True)
    server.serve_forever()
