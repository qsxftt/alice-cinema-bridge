# -*- coding: utf-8 -*-
import sys
import os
import io
import time
import json
import urllib.request
import urllib.error
import subprocess

# Настройка UTF-8 для консоли Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from core.config import SERVER_LAN_IP, SERVER_PORT, SECRET_TOKEN

SERVER_URL = f"http://{SERVER_LAN_IP}:{SERVER_PORT}"
TARGET_URL = f"{SERVER_URL}/target?secret={SECRET_TOKEN}"

def get_target():
    try:
        req = urllib.request.Request(TARGET_URL)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("target", "unknown"), data.get("device_name", "")
    except Exception as e:
        return None, str(e)

def set_target(new_target):
    try:
        url = f"{TARGET_URL}&set={new_target}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return True, data.get("target", new_target), data.get("device_name", "")
    except Exception as e:
        return False, None, str(e)

def is_receiver_running():
    try:
        # Проверяем запущен ли python с laptop_receiver.py
        cmd = 'powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"Name like \'%python%\'\\" | Select-Object -ExpandProperty CommandLine"'
        res = subprocess.check_output(cmd, shell=True, text=True, errors='ignore')
        return "laptop_receiver.py" in res
    except Exception:
        return False

def start_receiver():
    receiver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start_pc_receiver.bat")
    if os.path.exists(receiver_path):
        subprocess.Popen(f'cmd /c start "" "{receiver_path}"', shell=True)
        print("[+] 🚀 PC Receiver запущен в отдельном окне!", flush=True)
    else:
        py_receiver = os.path.join(os.path.dirname(os.path.abspath(__file__)), "laptop_receiver.py")
        subprocess.Popen(f'cmd /c start "Cinema PC Receiver" python "{py_receiver}"', shell=True)
        print("[+] 🚀 PC Receiver запущен!", flush=True)

def main():
    args = [a.lower().strip() for a in sys.argv[1:]]

    # Обработка аргументов командной строки: pc, projector, toggle, status
    if args:
        action = args[0]
        if action in ["pc", "компьютер", "комп", "пк"]:
            ok, target, name = set_target("pc")
            if ok:
                print(f"[+] ✅ Успешно: Вывод переключен на КОМПЬЮТЕР ({name})!", flush=True)
                if not is_receiver_running():
                    print("[!] PC Receiver не запущен на ПК. Запускаю...", flush=True)
                    start_receiver()
            else:
                print(f"[-] ❌ Ошибка подключения к серверу: {name}", flush=True)
            return

        elif action in ["projector", "проектор"]:
            ok, target, name = set_target("projector")
            if ok:
                print(f"[+] ✅ Успешно: Вывод переключен на ПРОЕКТОР ({name})!", flush=True)
            else:
                print(f"[-] ❌ Ошибка подключения к серверу: {name}", flush=True)
            return

        elif action in ["toggle", "переключить", "смени"]:
            curr, _ = get_target()
            new_target = "projector" if curr == "pc" else "pc"
            ok, target, name = set_target(new_target)
            if ok:
                icon = "💻" if target == "pc" else "📽️"
                print(f"[+] ✅ Режим переключен на: {icon} {target.upper()} ({name})", flush=True)
                if target == "pc" and not is_receiver_running():
                    start_receiver()
            else:
                print(f"[-] ❌ Ошибка подключения к серверу: {name}", flush=True)
            return

        elif action in ["status", "статус"]:
            curr, name = get_target()
            if curr:
                icon = "💻" if curr == "pc" else "📽️"
                print(f"[*] Текущий режим: {icon} {curr.upper()} (на {name})", flush=True)
            else:
                print(f"[-] Сервер недоступен: {name}", flush=True)
            return

    # Интерактивное меню, если запущено без параметров
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 60)
        print("         🎬  CINEMA BRIDGE — ВЫБОР ЭКРАНА  🎬")
        print("=" * 60)
        
        curr, name = get_target()
        if curr == "pc":
            print(f"  Текущий режим :  💻  КОМПЬЮТЕР (воспроизведение на ПК)")
        elif curr == "projector":
            print(f"  Текущий режим :  📽️  ПРОЕКТОР (воспроизведение на проекторе)")
        else:
            print(f"  Текущий режим :  ⚠️  Сервер недоступен ({name})")
            
        receiver_status = "🟢 Запущен" if is_receiver_running() else "⚪ Не запущен"
        print(f"  PC Receiver   :  {receiver_status}")
        print("-" * 60)
        print("  [1] 📽️  Переключить на ПРОЕКТОР")
        print("  [2] 💻  Переключить на КОМПЬЮТЕР (ПК)")
        print("  [3] 🔄  Переключить режим (Toggle)")
        print("  [4] 🚀  Запустить PC Receiver (для ПК)")
        print("  [0] 🚪  Выход")
        print("-" * 60)
        
        try:
            choice = input("👉 Выберите действие [1-4, 0]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            break

        if choice == "1":
            ok, target, name = set_target("projector")
            if ok:
                print(f"\n[+] ✅ Вывод переключен на: 📽️ ПРОЕКТОР ({name})")
            else:
                print(f"\n[-] ❌ Ошибка: {name}")
            time.sleep(1.5)

        elif choice == "2":
            ok, target, name = set_target("pc")
            if ok:
                print(f"\n[+] ✅ Вывод переключен на: 💻 КОМПЬЮТЕР ({name})")
                if not is_receiver_running():
                    print("[!] Запускаю фоновый PC Receiver для ПК...")
                    start_receiver()
            else:
                print(f"\n[-] ❌ Ошибка: {name}")
            time.sleep(1.5)

        elif choice == "3":
            new_target = "projector" if curr == "pc" else "pc"
            ok, target, name = set_target(new_target)
            if ok:
                icon = "💻" if target == "pc" else "📽️"
                print(f"\n[+] ✅ Режим переключен на: {icon} {target.upper()} ({name})")
                if target == "pc" and not is_receiver_running():
                    print("[!] Запускаю фоновый PC Receiver для ПК...")
                    start_receiver()
            else:
                print(f"\n[-] ❌ Ошибка: {name}")
            time.sleep(1.5)

        elif choice == "4":
            if is_receiver_running():
                print("\n[*] PC Receiver уже запущен!")
            else:
                start_receiver()
            time.sleep(1.5)

        elif choice == "0":
            print("\nДо свидания!")
            break

if __name__ == "__main__":
    main()
