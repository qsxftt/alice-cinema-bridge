import asyncio
import os
import sys
import io

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from androidtvremote2 import AndroidTVRemote
from core.config import PROJECTOR_IP, PROJECTOR_CERT, PROJECTOR_KEY, PROJECT_ROOT

IP = PROJECTOR_IP
DIR = PROJECT_ROOT
CERT = PROJECTOR_CERT
KEY = PROJECTOR_KEY
PIN_FILE = os.path.join(DIR, "pin.txt")

async def main():
    if os.path.exists(PIN_FILE):
        try:
            os.remove(PIN_FILE)
        except Exception:
            pass

    remote = AndroidTVRemote("HomeCinema", CERT, KEY, IP)
    await remote.async_generate_cert_if_missing()
    print(f"Подключаюсь к проектору {IP}:6467 для запроса PIN...", flush=True)
    try:
        await remote.async_start_pairing()
        print(">>> ЗАПРОС ОТПРАВЛЕН! Посмотри на экран проектора. <<<", flush=True)
        print("На экране должно появиться окно с 6-значным кодом (PIN).", flush=True)

        pin = None
        for _ in range(180):  # ждем 3 минуты
            if os.path.exists(PIN_FILE):
                with open(PIN_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    pin = content
                    try:
                        os.remove(PIN_FILE)
                    except Exception:
                        pass
                    break
            await asyncio.sleep(1)

        if not pin:
            print("Таймаут ожидания PIN!", flush=True)
            return

        print(f"Отправляю полученный PIN '{pin}' на проектор...", flush=True)
        await remote.async_finish_pairing(pin)
        print("🎉 УСПЕШНО СПАРЕНО! Сертификаты сохранены.", flush=True)
    except Exception as e:
        print(f"Ошибка спаривания: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
