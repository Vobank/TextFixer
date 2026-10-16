# -*- coding: utf-8 -*-
"""Буфер обмена и эмуляция клавиш: копирование выделения, вставка результата.

Всё через библиотеку keyboard (чище по модификаторам), чем pynput.
"""

import time
import random
import string
import ctypes

import pyperclip
import keyboard as kblib

from .config import dbg


def release_all_modifiers():
    """Сообщаем ОС, что модификаторы отпущены (даже если физически зажаты),
    чтобы наш Ctrl+C/Ctrl+V не превратился в Ctrl+Alt+...."""
    for k in ("ctrl", "alt", "shift", "left windows", "right windows",
              "right alt", "left ctrl", "right ctrl"):
        try:
            kblib.release(k)
        except Exception:
            pass
    time.sleep(0.04)


def send(combo):
    """Эмуляция сочетания (ctrl+c, ctrl+v, ctrl+a, ctrl+insert)."""
    try:
        kblib.send(combo)
    except Exception as e:
        dbg("send error:", repr(e))


def fg_info():
    """Заголовок и класс активного окна — для логов/диагностики."""
    try:
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p
        hwnd = u.GetForegroundWindow()
        n = u.GetWindowTextLengthW(hwnd)
        b = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, b, n + 1)
        cls = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(hwnd, cls, 256)
        return f"{b.value!r} [{cls.value}]"
    except Exception:
        return "?"


def _rand_token():
    # без нулевого символа! иначе Windows обрезает буфер и сравнение ломается
    return "TFmark_" + "".join(random.choices(string.ascii_letters + string.digits, k=16))


def clip_get():
    for _ in range(5):
        try:
            return pyperclip.paste()
        except Exception:
            time.sleep(0.03)
    return ""


def clip_set(text):
    for _ in range(5):
        try:
            pyperclip.copy(text)
            return
        except Exception:
            time.sleep(0.03)


def grab_selection(copy_delay, select_all=False, attempts=3, polls=30):
    """Копирует выделенный текст (или весь текст поля при select_all=True).
    attempts/polls — сколько попыток копирования и как долго ждать (для быстрой
    проверки выделения можно взять attempts=1, polls поменьше).
    Возвращает (selected_text|None, original_clipboard)."""
    dbg("активное окно:", fg_info())
    original = clip_get()

    time.sleep(copy_delay)
    release_all_modifiers()

    if select_all:
        send("ctrl+a")
        time.sleep(0.05)

    sentinel = _rand_token()
    clip_set(sentinel)
    time.sleep(0.02)

    selected = sentinel
    combos = ["ctrl+c", "ctrl+c", "ctrl+insert"][:max(1, attempts)]
    for attempt, combo in enumerate(combos):
        release_all_modifiers()
        send(combo)
        for _ in range(polls):
            time.sleep(0.02)
            cur = clip_get()
            if cur != sentinel:
                selected = cur
                break
        if selected != sentinel:
            break
        dbg(f"копирование: попытка {attempt + 1} ({combo}) пустая")

    dbg("скопировано:", repr(selected)[:80] if selected != sentinel else "НИЧЕГО")

    if selected == sentinel:
        clip_set(original)
        return None, original
    return selected, original


def paste_text(new_text, original_clipboard):
    release_all_modifiers()
    clip_set(new_text)
    time.sleep(0.04)
    send("ctrl+v")
    time.sleep(0.12)
    clip_set(original_clipboard)             # вернуть прежний буфер
