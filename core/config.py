# -*- coding: utf-8 -*-
"""
core/config.py - Конфигурация, пути, переменные окружения и глобальное состояние
"""

import os
import threading

# Автозагрузка .env если python-dotenv установлен
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Корневая директория проекта
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Сетевые настройки сервера
SERVER_LAN_IP = os.getenv("SERVER_LAN_IP", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8888"))

# Интеграции и токены
PROWLARR_URL = os.getenv("PROWLARR_URL", "http://127.0.0.1:9696")
PROWLARR_API_KEY = os.getenv("PROWLARR_API_KEY", "")
TORRSERVER_URL = os.getenv("TORRSERVER_URL", "http://127.0.0.1:8090")
SECRET_TOKEN = os.getenv("SECRET_TOKEN", "cinema_secret_token_change_me")
KINOPOISK_API_KEY = os.getenv("KINOPOISK_API_KEY", "")
KINOPOISK_URL = os.getenv("KINOPOISK_URL", "https://api.poiskkino.dev/v1.4/movie/search")

# Режим подтверждения: если True - всегда переспрашивает "Включить X Y года?", если False - Smart Confidence
ALWAYS_CONFIRM = os.getenv("ALWAYS_CONFIRM", "false").lower() in ("true", "1", "yes")

# Настройки проектора
PROJECTOR_IP = os.getenv("PROJECTOR_IP", "192.168.1.116")
PROJECTOR_CERT = os.getenv("PROJECTOR_CERT", os.path.join(PROJECT_ROOT, "projector_cert.pem"))
PROJECTOR_KEY = os.getenv("PROJECTOR_KEY", os.path.join(PROJECT_ROOT, "projector_key.pem"))

# Публичный домен Funnel
TAILSCALE_FUNNEL_DOMAIN = os.getenv("TAILSCALE_FUNNEL_DOMAIN", "")

# HLS прокси для каналов с защитой по Referer (РЕН ТВ, Карусель)
PROXY_CHANNELS = {
    'ren': {
        'url': 'http://cdn4.skygo.mn/live/disk1/RenTV/HLSv3-FTA/RenTV.m3u8',
        'referer': 'http://skygo.mn/'
    },
    'karusel': {
        'url': 'http://cdn4.skygo.mn/live/disk1/Karusel/HLSv3-FTA/Karusel.m3u8',
        'referer': 'http://skygo.mn/'
    }
}

# Кэш ТВ-каналов
TV_CACHE_FILE = os.path.join(PROJECT_ROOT, "tv_cache.json")

# Целевое устройство для воспроизведения: "projector" (проектор) или "pc" (компьютер)
TARGET_FILE = os.path.join(PROJECT_ROOT, "playback_target.txt")
PLAYBACK_TARGET = "projector"
TARGET_DEVICE_NAME = "проекторе"

def get_playback_target():
    global PLAYBACK_TARGET, TARGET_DEVICE_NAME
    if os.path.exists(TARGET_FILE):
        try:
            with open(TARGET_FILE, "r", encoding="utf-8") as f:
                val = f.read().strip().lower()
                if val in ["pc", "projector"]:
                    PLAYBACK_TARGET = val
        except Exception:
            pass
    TARGET_DEVICE_NAME = "компьютере" if PLAYBACK_TARGET == "pc" else "проекторе"
    return PLAYBACK_TARGET

def set_playback_target(val):
    global PLAYBACK_TARGET, TARGET_DEVICE_NAME
    val = val.strip().lower()
    if val in ["pc", "projector"]:
        PLAYBACK_TARGET = val
        TARGET_DEVICE_NAME = "компьютере" if PLAYBACK_TARGET == "pc" else "проекторе"
        try:
            with open(TARGET_FILE, "w", encoding="utf-8") as f:
                f.write(val)
            print(f"🔄 Режим воспроизведения изменен на: {PLAYBACK_TARGET} ({TARGET_DEVICE_NAME})", flush=True)
        except Exception as e:
            print(f"[-] Не удалось сохранить {TARGET_FILE}: {e}", flush=True)
    return PLAYBACK_TARGET

# Инициализация целевого устройства при старте
get_playback_target()

# Очередь команд для воспроизведения (опрос клиентом ПК через /poll)
pending_playback = None
playback_lock = threading.Lock()

def get_pending_playback():
    global pending_playback
    with playback_lock:
        return pending_playback

def set_pending_playback(val):
    global pending_playback
    with playback_lock:
        pending_playback = val

def pop_pending_playback():
    global pending_playback
    with playback_lock:
        res = pending_playback
        pending_playback = None
        return res

# Хранилище активных диалогов уточнения сессий Алисы: session_id -> { "candidates": [...], "timestamp": float }
active_disambiguations = {}
disambiguation_lock = threading.Lock()
