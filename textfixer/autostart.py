# -*- coding: utf-8 -*-
"""Start with Windows via the HKCU\\...\\Run registry key.
Launches silently (pythonw) from the project's venv, without a console window."""

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
    """Launch command: pythonw from the venv + the project's main.py."""
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
        print(f"[autostart] failed to enable: {e}")
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
        print(f"[autostart] failed to disable: {e}")
        return False


def toggle():
    """Toggles autostart. Returns the new state (True/False)."""
    if is_enabled():
        disable()
        return False
    enable()
    return is_enabled()
