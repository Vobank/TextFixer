# -*- coding: utf-8 -*-
"""Clipboard and key emulation: copying the selection, pasting the result.

Everything goes through the keyboard library (cleaner with modifiers than pynput).
"""

import time
import random
import string
import ctypes

import pyperclip
import keyboard as kblib

from .config import dbg


def release_all_modifiers():
    """Tell the OS that modifiers are released (even if physically held down)
    so that our Ctrl+C/Ctrl+V does not turn into Ctrl+Alt+...."""
    for k in ("ctrl", "alt", "shift", "left windows", "right windows",
              "right alt", "left ctrl", "right ctrl"):
        try:
            kblib.release(k)
        except Exception:
            pass
    time.sleep(0.04)


def send(combo):
    """Emulates a key combination (ctrl+c, ctrl+v, ctrl+a, ctrl+insert)."""
    try:
        kblib.send(combo)
    except Exception as e:
        dbg("send error:", repr(e))


def fg_info():
    """Title and class of the active window — for logs/diagnostics."""
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
    # no NUL character! otherwise Windows truncates the clipboard and the comparison breaks
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
    """Copies the selected text (or the whole field's text when select_all=True).
    attempts/polls — how many copy attempts and how long to wait (for a quick
    selection check use attempts=1 and fewer polls).
    Returns (selected_text|None, original_clipboard)."""
    dbg("active window:", fg_info())
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
        dbg(f"copy: attempt {attempt + 1} ({combo}) empty")

    dbg("copied:", repr(selected)[:80] if selected != sentinel else "NOTHING")

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
    clip_set(original_clipboard)             # restore the previous clipboard
