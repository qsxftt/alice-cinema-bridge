# -*- coding: utf-8 -*-
"""
test_modular_core.py - Локальное тестирование и верификация модулей ядра Cinema Bridge
"""

import os
import sys

# Настройка UTF-8 вывода
sys.stdout.reconfigure(encoding='utf-8')

print("🧪 Запуск верификации модулей Cinema Bridge...\n")

passed = 0
failed = 0

def check(name, condition, details=""):
    global passed, failed
    if condition:
        print(f"  ✅ [PASS] {name}")
        passed += 1
    else:
        print(f"  ❌ [FAIL] {name} - {details}")
        failed += 1

# ==============================================================================
# 1. Тест core.config
# ==============================================================================
print("1. Тестирование core.config:")
from core.config import (
    SERVER_LAN_IP, SERVER_PORT, SECRET_TOKEN, PROXY_CHANNELS,
    get_playback_target, set_playback_target,
    get_pending_playback, set_pending_playback, pop_pending_playback
)

check("Константы сервера", SERVER_PORT == 8888 and bool(SECRET_TOKEN))
check("Каналы прокси HLS", 'ren' in PROXY_CHANNELS and 'karusel' in PROXY_CHANNELS)

initial_target = get_playback_target()
set_playback_target("pc")
check("Переключение target на pc", get_playback_target() == "pc")
set_playback_target("projector")
check("Переключение target на projector", get_playback_target() == "projector")
set_playback_target(initial_target)

set_pending_playback({"action": "test", "val": 42})
popped = pop_pending_playback()
check("Очередь pending_playback", popped and popped.get("val") == 42 and get_pending_playback() is None)

# ==============================================================================
# 2. Тест core.nlu
# ==============================================================================
print("\n2. Тестирование core.nlu:")
from core.nlu import (
    extract_voiceover, extract_season_and_episode, is_exit_command,
    extract_youtube_query, clean_movie_query
)

# Озвучки
vo1, q1 = extract_voiceover("включи во все тяжкие в озвучке кубик в кубе")
check("Озвучка: Кубик в кубе явная", vo1 and vo1['key'] == 'kubik' and "во все тяжкие" in q1)

vo2, q2 = extract_voiceover("поставь рик и морти от сыендука")
check("Озвучка: Сыендук", vo2 and vo2['key'] == 'syenduk' and "рик и морти" in q2)

vo3, q3 = extract_voiceover("фильм в диких условиях")
check("Озвучка: Сохранение предлога 'В' в названии", vo3 is None and "в диких условиях" in q3)

vo4, q4 = extract_voiceover("пацаны в переводе кравец")
check("Озвучка: Кастомная студия 'Кравец'", vo4 and vo4['display_name'] == 'Кравец')

# Сезоны и серии
s1, ep1, c1 = extract_season_and_episode("сериал декстер 7 сезон 5 серия")
check("Сезон/серия: цифры (7/5)", s1 == 7 and ep1 == 5 and "декстер" in c1)

s2, ep2, c2 = extract_season_and_episode("игра престолов четвертый сезон пятая серия")
check("Сезон/серия: порядковые слова (4/5)", s2 == 4 and ep2 == 5 and "игра престолов" in c2)

s3, ep3, c3 = extract_season_and_episode("терминатор 2")
check("Сезон/серия: фильм с цифрой не ломается", s3 is None and ep3 is None and "терминатор 2" in c3)

# Очистка запросов
clean_q = clean_movie_query("Алиса, пожалуйста включи фильм Интерстеллар на проекторе в хорошем качестве")
check("Очистка фильма от префиксов и суффиксов", clean_q == "интерстеллар", f"получено: '{clean_q}'")

# YouTube
is_yt1, yt_q1 = extract_youtube_query("включи ютуб")
check("YouTube: открытие главной", is_yt1 and yt_q1 == "")

is_yt2, yt_q2 = extract_youtube_query("найди на ютубе котиков")
check("YouTube: поиск видео", is_yt2 and "котиков" in yt_q2)

# Стоп-слова
check("Exit: 'выход'", is_exit_command("выход"))
check("Exit: 'стоп'", is_exit_command("стоп"))
check("Exit: 'закрой навык'", is_exit_command("закрой навык"))
check("Exit: обычная фраза не выход", not is_exit_command("включи матрицу"))

# ==============================================================================
# 3. Тест core.iptv
# ==============================================================================
print("\n3. Тестирование core.iptv:")
from core.iptv import TV_CHANNELS, extract_tv_channel, rewrite_m3u8, resolve_upstream_url

check("20 Федеральных каналов в базе", len(TV_CHANNELS) == 20)

is_tv1, ch1 = extract_tv_channel("включи стс")
check("Распознавание ТВ: СТС", is_tv1 and ch1['display_name'] == "СТС")

is_tv2, ch2 = extract_tv_channel("телеканал матч тв")
check("Распознавание ТВ: Матч ТВ", is_tv2 and ch1 is not None)

is_tv3, ch3 = extract_tv_channel("включи фильм стс")
check("Исключение ТВ, если запрошен фильм", not is_tv3)

# URL resolve
resolved = resolve_upstream_url("http://example.com/live/index.m3u8", "chunk1.ts")
check("HLS resolve upstream URL", resolved == "http://example.com/live/chunk1.ts")

# ==============================================================================
# 4. Тест core.kinopoisk
# ==============================================================================
print("\n4. Тестирование core.kinopoisk:")
from core.kinopoisk import normalize_text, resolve_user_choice

check("Нормализация текста", normalize_text("ФИЛЬМ, 1+1! (2011)") == "фильм 1 1 2011")

candidates = [
    {"name": "Матрица", "year": "1999", "display": "Матрица (1999)"},
    {"name": "Матрица: Перезагрузка", "year": "2003", "display": "Матрица: Перезагрузка (2003)"}
]
choice1 = resolve_user_choice("первый", candidates)
check("Выбор пользователя 'первый'", choice1 and choice1['year'] == "1999")
choice2 = resolve_user_choice("2003", candidates)
check("Выбор пользователя по году '2003'", choice2 and choice2['year'] == "2003")

# ==============================================================================
# 5. Тест core.torrents
# ==============================================================================
print("\n5. Тестирование core.torrents:")
from core.torrents import extract_seasons_from_title, score_release

seasons1 = extract_seasons_from_title("Игра престолов / Game of Thrones (Сезоны 1-8) BDRip 1080p")
check("Парсинг диапазона сезонов 1-8", seasons1 == set(range(1, 9)))

seasons2 = extract_seasons_from_title("Декстер / Dexter (S07) WEB-DL 1080p")
check("Парсинг одиночного сезона S07", seasons2 == {7})

# Скоринг
mock_item_1080 = {'title': 'Movie (2020) 1080p BDRip', 'seeders': 25, 'size': 12 * (1024**3)}
mock_item_4k = {'title': 'Movie (2020) 2160p 4K Remux AV1', 'seeders': 25, 'size': 60 * (1024**3)}

score_1080 = score_release(mock_item_1080)
score_4k = score_release(mock_item_4k)
check("Скоринг: 1080p получает преимущество над 4K/AV1 для проектора", score_1080 > score_4k)

# ==============================================================================
# 6. Тест core.playback
# ==============================================================================
print("\n6. Тестирование core.playback:")
from core.playback import classify_torrent_videos, find_target_video_file

files = [
    {'path': 'Dexter.S07E01.mkv', 'length': 1500 * 1024 * 1024, 'id': 1},
    {'path': 'Dexter.S07E02.mkv', 'length': 1500 * 1024 * 1024, 'id': 2},
    {'path': 'sample.mkv', 'length': 20 * 1024 * 1024, 'id': 3}
]
is_ser, valid_v = classify_torrent_videos(files)
check("Классификация файлов как сериал", is_ser and len(valid_v) == 2)

target_f = find_target_video_file(valid_v, target_season=7, target_episode=2)
check("Выбор точного файла S07E02", target_f and target_f['id'] == 2)

# ==============================================================================
# 7. Тест 25 серий из бенчмарка test_25_series_results.json
# ==============================================================================
print("\n7. Тестирование 25 серий из эталонного бенчмарка:")
import json
if os.path.exists("test_25_series_results.json"):
    with open("test_25_series_results.json", "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    bm_ok = 0
    for item in bench_data:
        p = item["phrase"]
        exp = item["nlu"]
        vo, c = extract_voiceover(p)
        s, ep, c = extract_season_and_episode(c)
        vo_name = vo["display_name"] if vo else None
        if s == exp["season"] and ep == exp["episode"] and vo_name == exp["studio"]:
            bm_ok += 1
        else:
            print(f"    Mismatch in #{item['index']}: '{p}' -> got s={s}, ep={ep}, vo={vo_name} vs exp={exp}")
    check(f"Бенчмарк 25 запросов сериалов: {bm_ok}/25 совпало", bm_ok == len(bench_data))
print(f"\n{'='*50}")
print(f"📊 Результаты: Пройдено: {passed}, Провалено: {failed}")
print(f"{'='*50}")

if failed > 0:
    sys.exit(1)
else:
    print("🎉 Все тесты модулей ядра пройдены успешно!")
    sys.exit(0)
