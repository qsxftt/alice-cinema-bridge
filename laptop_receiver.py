# -*- coding: utf-8 -*-
import time
import json
import urllib.request
import urllib.error
import subprocess
import os
import sys
import io
import webbrowser

# Обеспечиваем корректный вывод UTF-8 в консоли Windows с немедленным сбросом буфера
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from core.config import SERVER_LAN_IP, SERVER_PORT, SECRET_TOKEN

POLL_URL = f"http://{SERVER_LAN_IP}:{SERVER_PORT}/poll?secret={SECRET_TOKEN}"
VLC_PATH = r"C:\Program Files\VideoLAN\VLC\vlc.exe"

def main():
    if not os.path.exists(VLC_PATH):
        print(f"[-] Внимание: VLC не найден по пути {VLC_PATH}. Проверьте установку плеера.", flush=True)

    print("=" * 65, flush=True)
    print("🍿 Cinema Client (PC Receiver) активен", flush=True)
    print(f"📡 Опрос сервера: {POLL_URL}", flush=True)
    print(f"🎥 Видеоплеер: {VLC_PATH}", flush=True)
    print("🎯 Режим: Воспроизведение команд Алисы прямо на этом компьютере")
    print("Ожидаю голосовую команду от Алисы (Станция / Телефон / Диалоги)...", flush=True)
    print("=" * 65, flush=True)

    current_vlc = None

    while True:
        try:
            req = urllib.request.Request(POLL_URL)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data.get("action") == "play":
                        title = data.get("title", "Фильм / Сериал / Видео")
                        # Предпочитаем прямой стрим файла для серии, либо общий url
                        url = data.get("direct_url") or data.get("url")
                        p_type = data.get("type", "")

                        print(f"\n[+] 🚀 Получена команда на воспроизведение!", flush=True)
                        print(f"🎬 Название: {title}", flush=True)
                        print(f"🔗 Ссылка: {url}", flush=True)

                        # Если это YouTube запрос -> открываем в стандартном браузере ПК
                        if p_type == "youtube" or "youtube.com" in url.lower():
                            print(f"[+] 🌐 Открываю YouTube в браузере: {url}\n", flush=True)
                            webbrowser.open(url)
                        else:
                            # Для фильмов и сериалов -> открываем в полноэкранном VLC
                            if not os.path.exists(VLC_PATH):
                                print(f"[-] Ошибка: VLC не найден по пути {VLC_PATH}", flush=True)
                                continue

                            # Закрываем предыдущий запущенный плеер
                            if current_vlc and current_vlc.poll() is None:
                                try:
                                    current_vlc.terminate()
                                    time.sleep(0.5)
                                except Exception:
                                    pass

                            cmd = [
                                VLC_PATH,
                                "--fullscreen",
                                "--network-caching=2000",
                                "--http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                                url
                            ]
                            current_vlc = subprocess.Popen(cmd)
                            if p_type == "tv":
                                print(f"[+] 📺 Телеканал «{title}» запущен в полноэкранном VLC!\n", flush=True)
                            else:
                                print(f"[+] 🎬 VLC запущен в полноэкранном режиме!\n", flush=True)
        except urllib.error.URLError:
            pass
        except Exception as e:
            print(f"[-] Ошибка опроса: {e}", flush=True)

        time.sleep(1)

if __name__ == "__main__":
    main()
