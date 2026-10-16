# -*- coding: utf-8 -*-
"""Контроллер режима T9: глобальный перехват набора, автодополнение (Tab),
автоисправление опечаток на пробел, облачные подсказки-фразы по паузе.

Работает через низкоуровневый хук pynput (win32_event_filter). Свои инъекции
игнорируются по флагу LLKHF_INJECTED. Всплывашка скрыта от записи экрана.
"""

import time
import queue
import ctypes
import threading
import tkinter as tk
from ctypes import wintypes

from pynput import keyboard, mouse

from .config import dbg
from .engine import LocalEngine

LLKHF_INJECTED = 0x10
WDA_EXCLUDEFROMCAPTURE = 0x00000011

VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
# стрелки/навигация/Enter/Delete — сбрасывают текущее слово
VK_RESET = {0x25, 0x26, 0x27, 0x28, 0x24, 0x23, 0x21, 0x22, VK_RETURN, 0x2E}

user32 = ctypes.windll.user32
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.GetKeyboardLayout.restype = ctypes.c_void_p
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


def vk_to_char(vk):
    """Символ по ТЕКУЩЕЙ раскладке активного окна (чтобы приходила 'к', а не 'r')."""
    try:
        scan = user32.MapVirtualKeyW(vk, 0)
        hwnd = user32.GetForegroundWindow()
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        hkl = user32.GetKeyboardLayout(tid)
        state = (ctypes.c_ubyte * 256)()
        if user32.GetAsyncKeyState(0x10) & 0x8000:       # Shift
            state[0x10] = 0x80
        if user32.GetKeyState(0x14) & 1:                 # Caps Lock
            state[0x14] = 0x01
        buf = ctypes.create_unicode_buffer(8)
        # wFlags=0x4 (Win10 1607+): НЕ менять состояние клавиатуры (иначе портит ввод)
        n = user32.ToUnicodeEx(vk, scan, state, buf, 8, 0x4, hkl)
        if n >= 1:
            return buf.value[:1] if buf.value else None
    except Exception:
        pass
    return None


def _mods_down():
    """True, если зажат Ctrl или Alt (это шорткат, а не набор текста)."""
    return bool(user32.GetAsyncKeyState(0x11) & 0x8000) or \
        bool(user32.GetAsyncKeyState(0x12) & 0x8000)


# --- позиция каретки (для всплывашки у курсора) ---
class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("flags", ctypes.c_uint),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", RECT)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def caret_screen_pos():
    """Экранные координаты каретки; запасной вариант — позиция мыши."""
    try:
        hwnd = user32.GetForegroundWindow()
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        gti = GUITHREADINFO()
        gti.cbSize = ctypes.sizeof(GUITHREADINFO)
        if user32.GetGUIThreadInfo(tid, ctypes.byref(gti)):
            r = gti.rcCaret
            if gti.hwndCaret and (r.left or r.bottom or r.top):
                pt = POINT(r.left, r.bottom)
                user32.ClientToScreen(gti.hwndCaret, ctypes.byref(pt))
                return pt.x, pt.y
    except Exception:
        pass
    try:
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x + 12, pt.y + 18
    except Exception:
        return None, None


# -----------------------------------------------------------------------------
# Всплывающая подсказка (скрыта от записи)
# -----------------------------------------------------------------------------
class SuggestPopup:
    def __init__(self, root):
        self.root = root
        self.win = None
        self.q = queue.Queue()
        self.root.after(60, self._poll)

    def show(self, text, x, y):
        self.q.put(("show", text, x, y))

    def hide(self):
        self.q.put(("hide", None, None, None))

    def _poll(self):
        try:
            while True:
                cmd, text, x, y = self.q.get_nowait()
                self._render(text, x, y) if cmd == "show" else self._destroy()
        except queue.Empty:
            pass
        self.root.after(60, self._poll)

    def _destroy(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None

    def _render(self, text, x, y):
        self._destroy()
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#1b1b1f")
        try:
            win.attributes("-alpha", 0.96)
        except Exception:
            pass
        frame = tk.Frame(win, bg="#1b1b1f", padx=10, pady=5,
                         highlightbackground="#3498db", highlightthickness=1)
        frame.pack()
        tk.Label(frame, text=text, bg="#1b1b1f", fg="#e8f4ff",
                 font=("Segoe UI", 11)).pack(side="left")
        tk.Label(frame, text="  Tab ⏎", bg="#1b1b1f", fg="#6aa9d6",
                 font=("Segoe UI", 9)).pack(side="left")
        win.update_idletasks()
        if x is None:
            x, y = 100, 100
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_width(), win.winfo_height()
        x = max(0, min(x, sw - w))
        y = max(0, min(y + 6, sh - h))
        win.geometry(f"+{x}+{y}")
        try:
            hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
            user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception:
            pass
        self.win = win


# -----------------------------------------------------------------------------
# Контроллер T9
# -----------------------------------------------------------------------------
class T9Controller:
    def __init__(self, root, cfg, toast_fn, phrase_fn):
        self.root = root
        self.cfg = cfg
        self.toast = toast_fn            # toast_fn(text, color, ms)
        self.phrase_fn = phrase_fn       # phrase_fn(context) -> str (облако)
        self.popup = SuggestPopup(root)

        self.enabled = False
        self.engine = None               # ленивая загрузка словарей
        self.kbd = keyboard.Controller()

        self.buffer = ""                 # текущее набираемое слово
        self.context = ""                # последние символы (для облака)
        self.suggestion = None           # {"suffix": str, "kind": "word"|"phrase"}
        self._injected = False
        self._lock = threading.Lock()
        self._phrase_timer = None

        self.listener = None
        self.mouse_listener = None

    # ---------- вкл/выкл ----------
    def toggle(self):
        self.disable() if self.enabled else self.enable()

    def enable(self):
        if self.enabled:
            return
        if self.engine is None:
            self.toast("… загружаю словари T9", "#3498db", 1500)
            dbg("загружаю словари…")
            try:
                self.engine = LocalEngine()
                dbg("словари загружены")
            except Exception as e:
                dbg("ОШИБКА загрузки словарей:", repr(e))
                self.toast(f"⚠ Не загрузить словари: {e}", "#e74c3c", 3000)
                return
        self.enabled = True
        self._reset()
        self.listener = keyboard.Listener(on_press=self._on_press,
                                          win32_event_filter=self._filter)
        self.listener.start()
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.mouse_listener.start()
        dbg("перехват клавиатуры запущен, T9 активен")
        self.toast("T9 включён ✓", "#2ecc71", 1600)

    def disable(self):
        self.enabled = False
        self._clear_suggestion()
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        self.toast("T9 выключен", "#95a5a6", 1400)

    # ---------- служебное ----------
    def _reset(self):
        self.buffer = ""
        self._clear_suggestion()

    def _on_click(self, x, y, button, pressed):
        if pressed:
            self.buffer = ""
            self._clear_suggestion()

    def _clear_suggestion(self):
        self.suggestion = None
        self.popup.hide()

    def _inject(self, fn):
        self._injected = True
        try:
            fn()
        finally:
            time.sleep(0.02)
            self._injected = False

    def _type(self, text):
        self._inject(lambda: self.kbd.type(text))

    def _backspace(self, n):
        def run():
            for _ in range(n):
                self.kbd.press(keyboard.Key.backspace)
                self.kbd.release(keyboard.Key.backspace)
                time.sleep(0.004)
        self._inject(run)

    # ---------- фильтр хука: подавляем Tab/Esc при активной подсказке ----------
    def _filter(self, msg, data):
        injected = bool(data.flags & LLKHF_INJECTED)
        self._injected = injected      # сбрасываем на КАЖДОМ событии, иначе залипает
        if injected:
            return
        vk = data.vkCode
        if self.suggestion and vk == VK_TAB:
            threading.Thread(target=self._accept, daemon=True).start()
            try:
                self.listener.suppress_event()
            except Exception:
                pass
        elif self.suggestion and vk == VK_ESCAPE:
            self._clear_suggestion()

    # ---------- логика по нажатиям ----------
    def _on_press(self, key):
        if not self.enabled or self._injected:
            return
        try:
            vk = getattr(key, "vk", None)
            if key in (keyboard.Key.tab, keyboard.Key.esc):   # обработаны в фильтре
                return
            if key == keyboard.Key.backspace:
                self.buffer = self.buffer[:-1]
                self.context = self.context[:-1]
                self._clear_suggestion()
                return
            if key == keyboard.Key.space:                     # пробел — спецклавиша
                self._on_separator(" ")
                return
            if vk in VK_RESET:
                self.buffer = ""
                self._clear_suggestion()
                return
            if _mods_down():                                  # шорткат (Ctrl+V и пр.)
                self.buffer = ""
                self._clear_suggestion()
                return

            ch = vk_to_char(vk) if vk else None               # символ по раскладке
            if not ch or ord(ch) < 32:
                return
            if ch in " \t":
                self._on_separator(" ")
                return
            if ch in ".,!?;:)(—-\"'«»":
                self._on_separator(ch)
                return

            self.buffer += ch
            self.context = (self.context + ch)[-300:]
            self._clear_suggestion()
            if self.cfg.get("t9_autocomplete", True) and len(self.buffer) >= 3:
                self._offer_completion()
        except Exception:
            pass

    def _on_separator(self, sep):
        word = self.buffer
        self.context = (self.context + sep)[-300:]
        self.buffer = ""
        self._clear_suggestion()
        dbg("разделитель; слово =", repr(word))

        if word and self.cfg.get("t9_autocorrect", True):
            threading.Thread(target=self._autocorrect, args=(word, sep),
                             daemon=True).start()
        if word:
            self.engine.learn(word)
        if sep == " " and self.cfg.get("t9_phrase", False) and self.phrase_fn:
            self._schedule_phrase()

    # ---------- автодополнение слова ----------
    def _offer_completion(self):
        if not self._lock.acquire(blocking=False):
            return
        try:
            comp = self.engine.complete(self.buffer)
        finally:
            self._lock.release()
        if not comp:
            return
        suffix = comp[len(self.buffer):]
        if not suffix:
            return
        self.suggestion = {"suffix": suffix, "kind": "word"}
        x, y = caret_screen_pos()
        dbg("подсказка:", repr(comp), "в точке", (x, y))
        self.popup.show(comp, x, y)

    # ---------- автоисправление ----------
    def _autocorrect(self, word, sep):
        try:
            fixed = self.engine.correct(word)
        except Exception:
            fixed = None
        if not fixed or fixed == word:
            dbg("исправление не нужно для", repr(word))
            return
        dbg("исправляю", repr(word), "->", repr(fixed))
        with self._lock:
            self._backspace(len(word) + 1)       # убираем слово + разделитель
            self._type(fixed + sep)              # печатаем исправление + разделитель

    # ---------- облачная фраза ----------
    def _schedule_phrase(self):
        if self._phrase_timer:
            self._phrase_timer.cancel()
        self._phrase_timer = threading.Timer(0.7, self._run_phrase)
        self._phrase_timer.daemon = True
        self._phrase_timer.start()

    def _run_phrase(self):
        if not self.enabled or self.buffer:
            return
        ctx = self.context.strip()
        if len(ctx) < 12:
            return
        try:
            cont = self.phrase_fn(ctx)
        except Exception:
            cont = None
        if not cont or self.buffer:
            return
        cont = cont.strip()
        if not cont:
            return
        self.suggestion = {"suffix": cont, "kind": "phrase"}
        x, y = caret_screen_pos()
        self.popup.show("… " + cont, x, y)

    # ---------- принять подсказку (Tab) ----------
    def _accept(self):
        sug = self.suggestion
        if not sug:
            return
        self._clear_suggestion()
        suffix = sug["suffix"]
        with self._lock:
            self._type(suffix)
        self.context = (self.context + suffix)[-300:]
        if sug["kind"] == "word":
            self.buffer += suffix
            self.engine.learn(self.buffer)
        else:
            self.buffer = ""
