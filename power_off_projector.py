import asyncio
import os
import sys

from androidtvremote2 import AndroidTVRemote
from core.config import PROJECTOR_IP, PROJECTOR_CERT, PROJECTOR_KEY

CERT = PROJECTOR_CERT
KEY = PROJECTOR_KEY
IP = PROJECTOR_IP

async def main():
    print(f"Подключаюсь к проектору по адресу {IP}...", flush=True)
    remote = AndroidTVRemote("HomeCinema", CERT, KEY, IP)
    
    try:
        await remote.async_connect()
        print(f"Успешное подключение! Текущий статус: is_on={remote.is_on}, app={remote.current_app}", flush=True)
        
        # Шаг 1: Нажимаем кнопку выключения (Power), чтобы появилось меню
        print("1. Отправляю кнопку POWER (Вызов меню выключения)...", flush=True)
        remote.send_key_command("KEYCODE_POWER")
        
        # Пауза 1.2 секунды для появления менюшки подтверждения
        print("Жду 1.2 сек для отрисовки диалога...", flush=True)
        await asyncio.sleep(1.2)
        
        # Шаг 2: Нажимаем OK / DPAD_CENTER для подтверждения "Выключить"
        print("2. Отправляю кнопку OK (DPAD_CENTER) для подтверждения выключения...", flush=True)
        remote.send_key_command("KEYCODE_DPAD_CENTER")
        
        # Также для надежности, если интерфейс ждет повторного Power:
        await asyncio.sleep(0.5)
        print("3. Отправляю ENTER...", flush=True)
        remote.send_key_command("KEYCODE_ENTER")
        
        await asyncio.sleep(2.0)
        print(f"Готово! Статус проектора: is_on={remote.is_on}", flush=True)
        
    except Exception as e:
        print(f"Ошибка при работе с проектором: {e}", flush=True)
    finally:
        try:
            remote.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
