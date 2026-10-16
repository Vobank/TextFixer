# -*- coding: utf-8 -*-
"""Автозапуск с Windows через раздел реестра HKCU\\...\\Run.
Запускает тихо (pythonw) из venv проекта, без окна консоли."""

import os
import sys

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "TextFixer"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _command():
    """Команда запуска: pythonw из venv + main.py проекта."""
    pyw = os.path.join(_PROJECT, ".venv", "Scripts", "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable.replace("python.exe", "pythonw.exe")
    main_py = os.path.join(_PROJECT, "main.py")
    return f'"{pyw}" "{main_py}"'


def is_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable():
    if winreg is None:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _command())
        return True
    except OSError as e:
        print(f"[autostart] не удалось включить: {e}")
        return False


def disable():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError as e:
        print(f"[autostart] не удалось выключить: {e}")
        return False


def toggle():
    """Переключает автозапуск. Возвращает новое состояние (True/False)."""
    if is_enabled():
        disable()
        return False
    enable()
    return is_enabled()
