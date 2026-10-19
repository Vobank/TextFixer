# -*- coding: utf-8 -*-
"""iPhone-keyboard-style T9 mode that works in any Windows window.

  * a bar of 3 suggestions next to the caret (context-aware, using the previous words);
    Tab inserts the selected one, Shift+Tab selects the next, Esc hides / skips the correction;
  * after a space, the next word is predicted;
  * typos are autocorrected on space/punctuation/Enter; Backspace right after
    a correction reverts it (and remembers the word);
  * wrong keyboard layout (ghbdtn → привет), switching the window's input language;
  * automatic commas before conjunctions, capital letter at sentence start,
    double space → ". ", a stray space before punctuation after a suggestion is removed;
  * optional cloud phrase suggestions after a pause (Gemini).

All logic runs synchronously in the low-level hook (pynput's win32_event_filter):
this way we see the layout/Shift state at the moment of the keypress and can replace
the key before the target program receives it. Our own injected input (SendInput) is
tagged with dwExtraInfo=_MAGIC and ignored. The suggestion window is hidden from screen capture.
"""

import re
import time
import queue
import ctypes
import threading
import tkinter as tk
from ctypes import wintypes

from pynput import keyboard, mouse

from .config import dbg, APP_DIR
from .engine import LocalEngine, BOS
from .languages import lang_by_langid, word_script
from .i18n import t as _t

WDA_EXCLUDEFROMCAPTURE = 0x00000011
_MAGIC = 0x7E9F0A11                      # tag for our own injected input

WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
VK_BACK, VK_TAB, VK_RETURN, VK_SHIFT, VK_CONTROL, VK_MENU = 0x08, 0x09, 0x0D, 0x10, 0x11, 0x12
VK_CAPITAL, VK_ESCAPE, VK_SPACE, VK_PACKET = 0x14, 0x1B, 0x20, 0xE7
VK_LWIN, VK_RWIN = 0x5B, 0x5C
SHIFT_VKS = {0x10, 0xA0, 0xA1}
CTRL_VKS = {0x11, 0xA2, 0xA3}
ALT_VKS = {0x12, 0xA4, 0xA5}
WIN_VKS = {VK_LWIN, VK_RWIN}
IGNORE_VKS = {VK_CAPITAL, 0x90, 0x91, 0x13, 0x2C, 0x5D, 0xAD, 0xAE, 0xAF, 0xB0, 0xB1,
              0xB2, 0xB3} | set(range(0x70, 0x88))          # F1–F24, media keys, etc.
# arrows/navigation/Delete/Insert — the caret moved, context is unknown
VK_NAV = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E}

CORRECT_ON = set(" ,.!?;:)\"»…")
# abbreviations — written in caps on purpose, left untouched when undoing Caps Lock
ABBR = {
    "сша", "рф", "ес", "ооо", "оао", "зао", "пао", "ип", "мвд", "фсб", "ссср", "вуз", "гост",
    "ндс", "ии", "мгу", "спб", "мск", "нато", "оон", "пк", "тв", "смс", "жкх", "гибдд", "дтп",
    "егэ", "огэ", "вв", "сми", "цб", "рж", "it", "usa", "uk", "eu", "id", "pc", "tv", "ai",
    "sms", "dj", "vip", "faq", "ceo", "hr", "pr", "seo", "api", "url", "pdf", "usb", "gps",
    "dvd", "cd", "ui", "ux", "fps", "pvp", "pve", "gg", "wtf", "omg", "lol", "nasa", "fbi",
    "cia", "nba", "nhl", "fifa", "bmw", "hp", "ibm", "amd", "ssd", "hdd", "cpu", "gpu", "ram",
}
WORD_TAIL = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*[-']?$")
WORD_ANY = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*")
SENT_END = re.compile(r"[.!?…]+[\"»)]*\s+$")

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.GetKeyboardLayout.restype = ctypes.c_void_p
user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.ToUnicodeEx.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                               ctypes.c_wchar_p, ctypes.c_int, wintypes.UINT, ctypes.c_void_p]
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.c_void_p]
user32.PostMessageW.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetKeyState.restype = ctypes.c_short
user32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.GetAncestor.argtypes = [ctypes.c_void_p, wintypes.UINT]
user32.GetAncestor.restype = ctypes.c_void_p
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, wintypes.DWORD]
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = ctypes.c_void_p
user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


# -----------------------------------------------------------------------------
# Input: SendInput (Unicode — independent of both our layout and the target's)
# -----------------------------------------------------------------------------
ULONG_PTR = ctypes.c_size_t
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x2, 0x4


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]


def _vk_pair(vk):
    scan = user32.MapVirtualKeyW(vk, 0)
    return [(vk, scan, 0), (vk, scan, KEYEVENTF_KEYUP)]


def send_keys(backspaces=0, text="", vk_after=None):
    """In a single batch: N×Backspace, then the text, then (optionally) the vk_after key."""
    events = []
    for _ in range(backspaces):
        events += _vk_pair(VK_BACK)
    for ch in text:
        if ch == " ":
            events += _vk_pair(VK_SPACE)
            continue
        data = ch.encode("utf-16-le")
        for k in range(0, len(data), 2):
            unit = int.from_bytes(data[k:k + 2], "little")
            events.append((0, unit, KEYEVENTF_UNICODE))
            events.append((0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    if vk_after:
        events += _vk_pair(vk_after)
    if not events:
        return
    arr = (INPUT * len(events))()
    for n, (vk, scan, flags) in enumerate(events):
        arr[n].type = 1                                   # INPUT_KEYBOARD
        arr[n].u.ki = KEYBDINPUT(vk, scan, flags, 0, _MAGIC)
    user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


# -----------------------------------------------------------------------------
# Window / keyboard layout / caret
# -----------------------------------------------------------------------------
class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", RECT)]


user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]


def _gui_info(hwnd):
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    gti = GUITHREADINFO()
    gti.cbSize = ctypes.sizeof(GUITHREADINFO)
    if tid and user32.GetGUIThreadInfo(tid, ctypes.byref(gti)):
        return tid, gti
    return tid, None


def focus_layout(hwnd):
    """Keyboard layout of the window that has input focus (for UWP/Terminal it is not the main window)."""
    tid, gti = _gui_info(hwnd)
    if gti is not None and gti.hwndFocus:
        ftid = user32.GetWindowThreadProcessId(gti.hwndFocus, None)
        if ftid:
            tid = ftid
    return user32.GetKeyboardLayout(tid)


def vk_to_char(vk, scan, shift, caps, hkl):
    """Character for the key in the active window's layout at the moment of the keypress."""
    state = (ctypes.c_ubyte * 256)()
    if shift:
        state[VK_SHIFT] = 0x80
    if caps:
        state[VK_CAPITAL] = 0x01
    buf = ctypes.create_unicode_buffer(8)
    # 0x4 (Win10 1607+): don't modify keyboard state (dead keys, etc.)
    n = user32.ToUnicodeEx(vk, scan, state, buf, 8, 0x4, hkl)
    if n >= 1 and buf.value:
        return buf.value[0]
    return None


_kernel32 = ctypes.WinDLL("kernel32")
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]


def real_caps():
    """Actual Caps Lock state, as seen by the active window."""
    fg = user32.GetForegroundWindow()
    ftid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    me = _kernel32.GetCurrentThreadId()
    attached = bool(ftid and ftid != me and user32.AttachThreadInput(me, ftid, True))
    try:
        return bool(user32.GetKeyState(VK_CAPITAL) & 1)
    finally:
        if attached:
            user32.AttachThreadInput(me, ftid, False)


def installed_layouts():
    """HKLs of all installed keyboard layouts."""
    n = user32.GetKeyboardLayoutList(0, None)
    arr = (ctypes.c_void_p * max(n, 1))()
    user32.GetKeyboardLayoutList(n, arr)
    return [h for h in arr if h]


def layout_for_lang(lang):
    """HKL of an installed layout for the language ('ru', 'de'…), or None."""
    from .languages import langid
    want = langid(lang)
    for h in installed_layouts():
        if want is not None and (h & 0x3FF) == want:
            return h
    return None


# --- caret position via MSAA (Chrome, Electron, Office…) ---
class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


_IID_IACCESSIBLE = _GUID(0x618736E0, 0x3C3D, 0x11CF,
                         (ctypes.c_ubyte * 8)(0x81, 0x0C, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71))


class _VARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort),
                ("r3", ctypes.c_ushort), ("lVal", ctypes.c_long), ("pad", ctypes.c_long),
                ("pad2", ctypes.c_longlong)]


_ACC_LOCATION = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                   ctypes.POINTER(ctypes.c_long), ctypes.POINTER(ctypes.c_long),
                                   ctypes.POINTER(ctypes.c_long), ctypes.POINTER(ctypes.c_long),
                                   _VARIANT)
_RELEASE = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
try:
    _oleacc = ctypes.WinDLL("oleacc")
    _oleacc.AccessibleObjectFromWindow.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                   ctypes.POINTER(_GUID), ctypes.c_void_p]
except OSError:
    _oleacc = None


def _msaa_caret(hwnd):
    if not _oleacc or not hwnd:
        return None
    ptr = ctypes.c_void_p()
    hr = _oleacc.AccessibleObjectFromWindow(hwnd, 0xFFFFFFF8, ctypes.byref(_IID_IACCESSIBLE),
                                            ctypes.byref(ptr))      # OBJID_CARET
    if hr != 0 or not ptr.value:
        return None
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    try:
        l, t, w, h = ctypes.c_long(), ctypes.c_long(), ctypes.c_long(), ctypes.c_long()
        var = _VARIANT()
        var.vt = 3                                                  # VT_I4, CHILDID_SELF
        hr = _ACC_LOCATION(vtbl[22])(ptr, ctypes.byref(l), ctypes.byref(t),
                                     ctypes.byref(w), ctypes.byref(h), var)
        if hr == 0 and (l.value or t.value) and h.value > 0:
            return l.value, t.value + h.value
    finally:
        _RELEASE(vtbl[2])(ptr)
    return None


def caret_screen_pos():
    """Screen coordinates just below the caret; falls back to the mouse position."""
    try:
        hwnd = user32.GetForegroundWindow()
        _, gti = _gui_info(hwnd)
        if gti is not None:
            r = gti.rcCaret
            if gti.hwndCaret and (r.left or r.bottom or r.top):
                pt = wintypes.POINT(r.left, r.bottom)
                user32.ClientToScreen(gti.hwndCaret, ctypes.byref(pt))
                return pt.x, pt.y
            pos = _msaa_caret(gti.hwndFocus or hwnd)
            if pos:
                return pos
    except Exception:
        pass
    try:
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x + 12, pt.y + 18
    except Exception:
        return None, None


# -----------------------------------------------------------------------------
# Suggestion bar (like the strip above the iPhone keyboard), hidden from capture
# -----------------------------------------------------------------------------
class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD)]


BG, FG, SEL_BG, DIM, FIX_FG, BORDER = "#1c1c1e", "#f2f2f7", "#2f5f8f", "#8e8e93", "#7fd88f", "#3a3a3c"


class SuggestPopup:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.win = None
        self.hwnd = None
        self.visible = False
        self.root.after(20, self._poll)

    def show(self, items, sel, x, y):
        self.q.put(("show", items, sel, x, y))

    def hide(self):
        # always go through the queue: a pending show may not be rendered yet (visible still False)
        self.q.put(("hide", None, None, None, None))

    def _poll(self):
        try:
            last = None
            while True:
                last = self.q.get_nowait()           # keep only the latest state
        except queue.Empty:
            pass
        if last:
            try:
                if last[0] == "show":
                    self._render(*last[1:])
                else:
                    self._hide_now()
            except Exception as e:
                dbg("popup:", repr(e))
        self.root.after(15, self._poll)

    def _ensure(self):
        if self.win is not None:
            return
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BORDER)
        win.geometry("+-10000+-10000")
        self.frame = tk.Frame(win, bg=BG)
        self.frame.pack(padx=1, pady=1)
        win.update_idletasks()
        hwnd = user32.GetAncestor(win.winfo_id(), 2) or win.winfo_id()   # GA_ROOT
        GWL_EXSTYLE = -20
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST — never steal focus
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | 0x08000000 | 0x00000080 | 0x00000008)
        try:
            user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception:
            pass
        user32.ShowWindow(hwnd, 0)
        self.win, self.hwnd = win, hwnd

    def _render(self, items, sel, x, y):
        self._ensure()
        for ch in self.frame.winfo_children():
            ch.destroy()
        for n, it in enumerate(items):
            if n:
                tk.Frame(self.frame, bg=BORDER, width=1).pack(side="left", fill="y", pady=4)
            kind, text = it["kind"], it["text"]
            label = ("✓ " + text) if kind == "fix" else ("… " + text) if kind == "phrase" else text
            tk.Label(self.frame, text=label, bg=SEL_BG if n == sel else BG,
                     fg=FIX_FG if kind == "fix" and n != sel else FG,
                     font=("Segoe UI", 11), padx=10, pady=3).pack(side="left")
        hint = "Tab" + ("  ⇧Tab" if len(items) > 1 else "")
        tk.Label(self.frame, text=hint, bg=BG, fg=DIM, font=("Segoe UI", 8),
                 padx=6).pack(side="left")
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        if x is None:
            x, y = 100, 100
        x, y = int(x), int(y) + 4
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        mon = user32.MonitorFromPoint(wintypes.POINT(x, y), 2)       # NEAREST
        if mon and user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
            r = mi.rcWork
            x = max(r.left, min(x, r.right - w))
            if y + h > r.bottom:
                y = max(r.top, y - h - 28)                             # above the text line
        # HWND_TOPMOST, SWP_NOACTIVATE | SWP_SHOWWINDOW
        user32.SetWindowPos(self.hwnd, ctypes.c_void_p(-1), x, y, w, h, 0x0010 | 0x0040)
        self.visible = True

    def _hide_now(self):
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 0)
        self.visible = False


class _Suppress(Exception):
    pass


# -----------------------------------------------------------------------------
# T9 controller
# -----------------------------------------------------------------------------
class T9Controller:
    def __init__(self, root, cfg, toast_fn, phrase_fn):
        self.root = root
        self.cfg = cfg
        self.toast = toast_fn            # toast_fn(text, color, ms)
        self.phrase_fn = phrase_fn       # phrase_fn(context) -> str (cloud)
        self.popup = SuggestPopup(root)

        self.enabled = False
        self.loading = False
        self.engine = None
        self.listener = None
        self.mouse_listener = None

        # what we believe is in front of the caret
        self.tail = ""
        self.ctx_known = False           # whether we know the start (after Enter / from field start)
        self.hwnd = None
        self.shift = self.ctrl = self.alt = self.win = False
        self.caps = False

        self.items = []                  # current suggestions [{"text", "kind"}]
        self.sel = 0
        self.ver = 0                     # state version (incremented on every keypress)
        self.items_ver = -1
        self.last_fix = None             # for undo via Backspace
        self.auto_space = None           # "accept" | "punct" | None
        self.no_fix = None               # word not to correct (Esc / undo)
        self.last_space_t = 0.0
        self.hkl = None                  # active window's keyboard layout
        self.wkeys = []                  # keys of the current word (vk, scan, shift)
        self._alt_hkl = {}               # word in another layout → that layout's HKL
        self.sep_keys = []               # keys of the word that was just finished
        self._layouts = ([], 0.0)        # (installed layouts, time of the query)

        self._req = queue.Queue()
        self._phrase_timer = None
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._autosave, daemon=True).start()

    # ---------- on/off ----------
    def toggle(self):
        self.disable() if self.enabled else self.enable()

    def enable(self):
        if self.enabled or self.loading:
            return
        if self.engine is None:
            self.loading = True
            self.toast(_t("t9_loading"), "#3498db", 2500)
            threading.Thread(target=self._load_and_start, daemon=True).start()
            return
        self._start()

    def _load_and_start(self):
        try:
            import os
            langs = self.cfg.get("languages") or None
            self.engine = LocalEngine(os.path.join(APP_DIR, "user_dict.json"), langs=langs)
        except Exception as e:
            dbg("ERROR loading dictionaries:", repr(e))
            self.toast(_t("t9_load_failed", err=e), "#e74c3c", 3500)
            return
        finally:
            self.loading = False
        if not self.engine.models:
            self.engine = None
            self.toast(_t("t9_no_dicts"), "#e67e22", 4000)
            return
        self.root.after(0, self._start)

    def reload(self):
        """Languages changed — reload the dictionaries (T9 stays enabled)."""
        was = self.enabled
        if was:
            self.disable(quiet=True)
        if self.engine:
            self.engine.user.save()
        self.engine = None
        if was or self.cfg.get("t9_start"):
            self.enable()

    def _start(self):
        if self.enabled:
            return
        self.enabled = True
        self.caps = bool(user32.GetKeyState(VK_CAPITAL) & 1)
        self._reset(False)
        self.listener = keyboard.Listener(win32_event_filter=self._filter)
        self.listener.start()
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.mouse_listener.start()
        dbg("keyboard hook started, T9 active")
        self.toast(_t("t9_on"), "#2ecc71", 2000)

    def disable(self, quiet=False):
        if not self.enabled:
            return
        self.enabled = False
        self._hide()
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        self.save()
        if not quiet:
            self.toast(_t("t9_off"), "#95a5a6", 1400)

    def save(self):
        if self.engine:
            self.engine.user.save()

    def _autosave(self):
        while True:
            time.sleep(60)
            try:
                self.save()
            except Exception:
                pass

    # ---------- state ----------
    def _reset(self, known):
        self.tail = ""
        self.wkeys = []
        self.ctx_known = known
        self.last_fix = None
        self.auto_space = None
        self.no_fix = None
        self._hide()

    def _hide(self):
        self.ver += 1
        self.items = []
        self.popup.hide()

    def _on_click(self, x, y, button, pressed):
        if pressed and self.enabled:
            self._reset(False)

    def _split(self):
        """(current word, [up to 2 previous words, BOS = start of phrase], text before the word)."""
        t = self.tail
        m = WORD_TAIL.search(t)
        word = m.group() if m else ""
        before = t[:len(t) - len(word)]
        cut = max(before.rfind("."), before.rfind("!"), before.rfind("?"),
                  before.rfind("…"))
        seg = before[cut + 1:] if cut >= 0 else before
        words = WORD_ANY.findall(seg)
        bos = cut >= 0 or self.ctx_known
        prev = ([BOS] if bos else []) + words
        return word, prev[-2:], before

    def _sentence_start(self, before):
        if not before.strip():
            return self.ctx_known
        return bool(SENT_END.search(before))

    def _set_tail(self, t):
        if len(t) > 400:
            t = t[-300:]
            self.ctx_known = False
        self.tail = t

    def _type(self, backspaces, text, vk_after=None):
        """Inject our input and update tail synchronously."""
        send_keys(backspaces, text, vk_after)
        t = self.tail[:len(self.tail) - backspaces] if backspaces else self.tail
        self._set_tail(t + text)

    # ---------- hook ----------
    def _filter(self, msg, data):
        """Called by pynput on the hook thread BEFORE the window receives the key.
        Any exception here would stop pynput, so catch everything."""
        try:
            self._handle(msg, data)
        except _Suppress:
            self.listener.suppress_event()       # raises its own exception — that's intended
        except Exception as e:
            dbg("hook error:", repr(e))
        return False                             # we don't need on_press

    def _handle(self, msg, data):
        if not self.enabled:
            return
        vk = data.vkCode
        down = msg in (WM_KEYDOWN, WM_SYSKEYDOWN)
        # track modifiers ourselves (including input injected by others)
        if vk in SHIFT_VKS:
            self.shift = down
            return
        if vk in CTRL_VKS:
            self.ctrl = down
            return
        if vk in ALT_VKS:
            self.alt = down
            return
        if vk in WIN_VKS:
            self.win = down
            return
        if not down:
            return
        if vk == VK_CAPITAL:
            self.caps = not self.caps
            return
        if (data.dwExtraInfo or 0) == _MAGIC:    # our own injected input
            return
        if vk in IGNORE_VKS:
            return

        hwnd = user32.GetForegroundWindow()
        if hwnd != self.hwnd:
            self.hwnd = hwnd
            self.caps = real_caps()
            self._reset(False)

        # safety net: in case a modifier key-up was lost
        if self.ctrl and not user32.GetAsyncKeyState(VK_CONTROL) & 0x8000:
            self.ctrl = False
        if self.alt and not user32.GetAsyncKeyState(VK_MENU) & 0x8000:
            self.alt = False
        if self.ctrl or self.alt or self.win:    # shortcut (Ctrl+V, Ctrl+Z…)
            self._reset(False)
            return

        if vk == VK_TAB:
            return self._on_tab()
        if vk == VK_ESCAPE:
            if self.popup.visible or self.items:
                word, _, _ = self._split()
                self.no_fix = word.lower() or None
                self._hide()
                raise _Suppress
            return
        if vk == VK_BACK:
            return self._on_backspace()
        if vk == VK_RETURN:
            return self._on_enter()
        if vk in VK_NAV:
            self._reset(False)
            return

        if vk == VK_PACKET:                      # Unicode from the on-screen keyboard / emoji panel
            ch = chr(data.scanCode)
            key = None
        else:
            hkl = focus_layout(hwnd)
            if hkl != self.hkl:                  # layout changed — so did the language
                self.hkl = hkl
                if self.engine:
                    self.engine.set_pref(lang_by_langid((hkl or 0) & 0x3FF, self.engine.models))
            ch = vk_to_char(vk, data.scanCode, self.shift, self.caps, hkl)
            key = (vk, data.scanCode, self.shift)
        if not ch or ord(ch) < 32:
            return
        self.ver += 1
        if ch.isalpha() or (ch in "-'" and WORD_TAIL.search(self.tail)):
            if not WORD_TAIL.search(self.tail):
                self.wkeys = []
            self.wkeys.append(key)
            return self._on_letter(ch)
        self.sep_keys, self.wkeys = self.wkeys, []      # the word has ended
        if ch.isdigit():
            self.last_fix = self.auto_space = None
            self._set_tail(self.tail + ch)
            self._hide()
            return
        return self._on_separator(ch)

    # ---------- the same word in other layouts (ghbdtn → привет) ----------
    def _alts(self, word, keys):
        """[(language, word)] — what the same keys would produce in other layouts."""
        if not self.engine or not keys or len(keys) != len(word) or None in keys:
            return None
        lays, t = self._layouts
        if time.time() - t > 30:
            lays = installed_layouts()
            self._layouts = (lays, time.time())
        out = []
        for h in lays:
            if h == self.hkl:
                continue
            langs = lang_by_langid(h & 0x3FF, self.engine.models)
            if not langs:
                continue
            text = "".join(vk_to_char(vk, sc, sh, False, h) or "?" for vk, sc, sh in keys)
            if text.replace("'", "").isalpha():
                out.extend((lang, text) for lang in langs)
                self._alt_hkl[text.lower()] = h
        return out

    # ---------- letters ----------
    def _on_letter(self, ch):
        self.last_fix = None
        self.auto_space = None
        word, _, before = self._split()
        # Caps Lock is on, yet you press Shift for a capital — so Caps was accidental:
        # turn it off and type the letter the way you meant it
        if (self.caps and self.shift and ch.islower()
                and self.cfg.get("t9_caps_off", True)):
            if not real_caps():                  # we had the Caps state wrong —
                self.caps = False                # the window gets a capital anyway
                ch = ch.upper()
            else:
                self._type(0, ch.upper())
                self._caps_off()
                self._request()
                raise _Suppress
        if (not word and ch.islower() and self.cfg.get("t9_autocap", True)
                and self._sentence_start(before) and ch.isalpha()):
            self._type(0, ch.upper())            # capital letter at sentence start
            self._request()
            raise _Suppress
        self._set_tail(self.tail + ch)
        if self.no_fix and not (word + ch).lower().startswith(self.no_fix):
            self.no_fix = None
        self._request()

    # ---------- Backspace ----------
    def _on_backspace(self):
        self.ver += 1
        lf = self.last_fix
        self.last_fix = None
        self.auto_space = None
        if lf and self.tail.endswith(lf["after"]):
            # undo autocorrection: restore the original and remember the word
            self._type(len(lf["after"]), lf["before"])
            if lf.get("word"):
                self.engine.remember(lf["word"])
                self.no_fix = lf["word"].lower()
            dbg("correction undone ->", repr(lf["before"]))
            self._hide()
            raise _Suppress
        if self.wkeys:
            self.wkeys.pop()
        if self.tail:
            self._set_tail(self.tail[:-1])
            self._request()
        else:
            self.ctx_known = False
            self._hide()

    # ---------- Tab: accept a suggestion ----------
    def _on_tab(self):
        if self.shift:
            if len(self.items) > 1 and self.items_ver == self.ver:
                self.sel = (self.sel + 1) % len(self.items)
                self.popup.show(self.items, self.sel, *caret_screen_pos())
                raise _Suppress
            self._reset(False)
            return
        if not self.items or self.items_ver != self.ver:
            if not self.popup.visible:
                self._reset(False)               # regular Tab — move between fields
                return
            self._compute(self.ver)              # suggestions are stale — recompute
        if not self.items:
            self._hide()
            raise _Suppress
        it = self.items[min(self.sel, len(self.items) - 1)]
        word, prev, before = self._split()
        text = it["text"]
        self.ver += 1
        if it["kind"] in ("phrase", "next") or not word:
            sep = "" if (not before or before.endswith(" ") or word) else " "
            self._type(len(word), sep + text + " ")
        elif text.startswith(word):
            self._type(0, text[len(word):] + " ")
        else:
            self._type(len(word), text + " ")
        self.auto_space = "accept"
        self.last_fix = None
        self._learn_text(text, prev)
        self._hide()
        self._request(predict=True)
        raise _Suppress

    # ---------- Enter ----------
    def _on_enter(self):
        word, prev, before = self._split()
        ct = self._caps_text(word)
        if ct:
            n, new = ct
            send_keys(n, new, VK_RETURN)
            self._caps_off()
            self._reset(True)
            raise _Suppress
        cased, caps_accident = self._caps_case(word) if word else (word, False)
        fixed = (self._fix(cased, prev, before, self.wkeys) or cased) if word else None
        if fixed and fixed != word:
            dbg("Enter: correcting", repr(word), "->", repr(fixed))
            self._maybe_switch_layout(word, fixed)
            send_keys(len(word), fixed, VK_RETURN)
            if caps_accident:
                self._caps_off()
            self._learn_text(fixed, prev)
            self._reset(True)
            raise _Suppress
        if word:
            self._learn_text(word, prev)
        self._reset(True)                        # new line/message — start of a phrase

    # ---------- Caps Lock ----------
    def _caps_off(self):
        """Turn Caps Lock off (our injection; the hook itself toggles self.caps)."""
        if real_caps():
            dbg("turning Caps Lock off")
            self.caps = True
            send_keys(vk_after=VK_CAPITAL)
        else:
            self.caps = False

    def _caps_run(self):
        """Tail of text typed in ALL CAPS in a row (from the start of the word where caps began):
        «вот я ПРОСТО В ШОКЕ» → index of the start of «ПРОСТО»."""
        t = self.tail
        i = len(t)
        while i > 0 and not t[i - 1].islower() and len(t) - i < 300:
            i -= 1
        while i < len(t) and not t[i].isalpha():
            i += 1
        return i

    def _decaps(self, seg, before):
        """ALL CAPS → normal case; abbreviations are kept, sentence starts get a capital."""
        out = []
        start = self._sentence_start(before)
        for tok in re.split(r"([^\W\d_]+(?:[-'][^\W\d_]+)*)", seg):
            if tok and tok[0].isalpha():
                w = tok if tok.lower() in ABBR else tok.lower()
                if start and w == tok.lower():
                    w = w[:1].upper() + w[1:]
                start = False
                out.append(w)
            else:
                out.append(tok)
                if re.search(r"[.!?…]\s*$", tok):
                    start = True
        return "".join(out)

    def _caps_text(self, word):
        """If the word was typed with Caps Lock on (no Shift) — (how many chars to erase,
        replacement text) for the whole ALL-CAPS tail, otherwise None."""
        if not (self.cfg.get("t9_caps_off", True) and self.caps and word
                and len(word) >= 2 and word.isupper() and word.lower() not in ABBR
                and self.engine.is_known(word.lower())):
            return None
        if not real_caps():
            self.caps = False
            return None
        start = self._caps_run()
        seg = self.tail[start:]
        new = self._decaps(seg, self.tail[:start])
        return (len(seg), new) if new != seg else None

    def _caps_case(self, word):
        """Fix letter case broken by Caps Lock: «пРИВЕТ» → «Привет»,
        «ПРивет» → «Привет». Returns (word, whether_caps_was_accidental)."""
        if not self.cfg.get("t9_caps_off", True) or len(word) < 2 or not word.isalpha():
            return word, False
        if word[0].islower() and word[1:].isupper():
            return word[0].upper() + word[1:].lower(), True
        # «ПРивет» — Shift released one letter too late; for English only long
        # words, so that «URLs», «IDs» are left alone
        min_len = 4 if word_script(word) == "cyr" else 6
        if (len(word) >= min_len and word[:2].isupper() and word[2:].islower()
                and self.engine.is_known(word.lower())):
            return word[0] + word[1:].lower(), False
        return word, False

    # ---------- separators ----------
    def _fix(self, word, prev, before, keys=None):
        if not self.cfg.get("t9_autocorrect", True) or not word:
            return None
        if self.no_fix and word.lower() == self.no_fix:
            return None
        t = time.perf_counter()
        alts = self._alts(word, keys) if self.cfg.get("t9_layout_switch", True) else None
        fixed = self.engine.fix(word, prev, self._sentence_start(before), alts)
        dbg(f"fix {word!r} -> {fixed!r} in {1000 * (time.perf_counter() - t):.0f} ms")
        return fixed

    def _on_separator(self, ch):
        word, prev, before = self._split()
        now = time.time()

        # a space right after "punctuation + auto-space" — don't duplicate it
        if ch == " " and not word and self.auto_space == "punct" and self.tail.endswith(" "):
            self.auto_space = None
            raise _Suppress
        # double space → period
        if (ch == " " and not word and self.cfg.get("t9_double_space", True)
                and self.tail.endswith(" ") and len(self.tail) >= 2
                and self.tail[-2].isalnum() and now - self.last_space_t < 1.5):
            self._type(1, ". ")
            self.auto_space = None
            self.last_space_t = 0
            self._hide()
            raise _Suppress
        # punctuation after a suggestion: "word ," → "word, "
        if ch in ",.!?:;" and not word and self.auto_space == "accept" and self.tail.endswith(" "):
            self._type(1, ch + " ")
            self.auto_space = "punct"
            self._hide()
            raise _Suppress

        self.auto_space = None
        if ch == " ":
            self.last_space_t = now
        if not word:
            self.last_fix = None
            self._set_tail(self.tail + ch)
            self._hide()
            if ch == " ":
                self._request(predict=True)
            return

        # typed with Caps Lock on: «ПРОСТО В ШОКЕ» → «просто в шоке», and turn Caps off
        ct = self._caps_text(word)
        if ct:
            n, new = ct
            last = WORD_TAIL.search(new)
            low_word = last.group() if last else ""
            fixed = self._fix(low_word, prev, before) if low_word else None
            if fixed:
                new = new[:len(new) - len(low_word)] + fixed
            old = self.tail[len(self.tail) - n:]
            self._type(n, new + ch)
            self._caps_off()
            self.last_fix = {"before": old, "after": new + ch, "word": None}
            dbg("caps → normal case:", repr(old), "->", repr(new))
            self._learn_text(fixed or low_word, prev)
            self._after_sep(ch)
            raise _Suppress

        final = word
        cased, caps_accident = self._caps_case(word)
        fixed = self._fix(cased, prev, before, self.sep_keys) if ch in CORRECT_ON else None
        if not fixed and cased != word:
            fixed = cased
        if fixed:
            final = fixed
        # automatic comma before a conjunction
        comma = None
        if (ch == " " and self.cfg.get("t9_autocomma", True) and before.endswith(" ")
                and len(before) >= 2 and before[-2].isalpha()):
            comma = self.engine.comma_before(final.split(" ")[0], prev)

        if fixed or comma is not None:
            if comma == 1:
                # «…дом в котором» → «…дом, в котором»
                pw = prev[-1]
                start = len(before) - 2 - len(pw)       # index of the space before the preposition
                old = self.tail[start:]
                new_text = ", " + pw + " " + final + ch
                if self.tail[start:start + 1] != " ":
                    old, new_text = word, final + ch
            elif comma == 0:
                old = " " + word
                new_text = ", " + final + ch
            else:
                old = word
                new_text = final + ch
            if new_text == old + ch:
                self._set_tail(self.tail + ch)
            else:
                self._type(len(old), new_text)
                if caps_accident:
                    self._caps_off()
                self.last_fix = {"before": old, "after": new_text,
                                 "word": word if fixed and fixed.lower() != word.lower() else None}
                dbg("replace", repr(old), "->", repr(new_text))
                if fixed:
                    self._maybe_switch_layout(word, fixed)
                self._learn_text(final, prev)
                self._after_sep(ch)
                raise _Suppress
        else:
            self.last_fix = None
            self._set_tail(self.tail + ch)
        self._learn_text(final, prev)
        self._after_sep(ch)

    def _after_sep(self, ch):
        self._hide()
        if ch == " ":
            self._request(predict=True)
            if self.cfg.get("t9_phrase", False) and self.phrase_fn:
                self._schedule_phrase()

    def _learn_text(self, text, prev):
        p = prev[-1] if prev else None
        for w in text.split(" "):
            if w:
                self.engine.learn(w, p)
                p = w

    def _maybe_switch_layout(self, word, fixed):
        """We fixed a wrong-layout word — switch the window's layout to the right one."""
        if not self.cfg.get("t9_layout_switch", True):
            return
        if word_script(word.lower()) == word_script(fixed.lower()):
            return
        hkl = self._alt_hkl.get(fixed.lower())
        if hkl is None:
            lang = self.engine.lang_of(fixed)
            hkl = layout_for_lang(lang) if lang else None
        if hkl and self.hwnd:
            user32.PostMessageW(self.hwnd, 0x0050, None, ctypes.c_void_p(hkl))
            self.hkl = None                      # re-detect the language on the next key

    # ---------- suggestions (background thread) ----------
    def _request(self, predict=False):
        if not self.cfg.get("t9_autocomplete", True):
            return
        if predict and not self.cfg.get("t9_predict", True):
            self._hide()
            return
        self._req.put(self.ver)

    def _worker(self):
        try:
            ctypes.windll.ole32.CoInitializeEx(None, 2)
        except Exception:
            pass
        while True:
            v = self._req.get()
            try:
                while True:
                    v = self._req.get_nowait()
            except queue.Empty:
                pass
            if not self.enabled or v != self.ver:
                continue
            try:
                self._compute(v, show=True)
            except Exception as e:
                dbg("suggest error:", repr(e))

    def _compute(self, v, show=False):
        if self.engine is None:
            return
        word, prev, before = self._split()
        items = []
        min_pref = int(self.cfg.get("t9_min_prefix", 2))
        if word:
            if len(word) < min_pref:
                items = []
            else:
                fixed = None
                if (self.cfg.get("t9_autocorrect", True) and len(word) >= 3
                        and not (self.no_fix and word.lower() == self.no_fix)):
                    alts = self._alts(word, list(self.wkeys)) \
                        if self.cfg.get("t9_layout_switch", True) else None
                    fixed = self.engine.fix(word, prev, self._sentence_start(before), alts)
                comps = self.engine.suggest(word, prev, 3)
                if fixed:
                    items.append({"text": fixed, "kind": "fix"})
                for c in comps:
                    if len(items) >= 3:
                        break
                    if not fixed or c.lower() != fixed.lower():
                        items.append({"text": c, "kind": "word"})
        elif before.endswith(" ") and WORD_ANY.search(before[-40:]):
            for c in self.engine.suggest("", prev, 3):
                items.append({"text": c, "kind": "next"})
        if v != self.ver:
            return
        self.items, self.sel, self.items_ver = items, 0, v
        if not show:
            return
        if items:
            x, y = caret_screen_pos()
            if v == self.ver:
                self.popup.show(items, 0, x, y)
        else:
            self.popup.hide()

    # ---------- cloud phrase ----------
    def _schedule_phrase(self):
        if self._phrase_timer:
            self._phrase_timer.cancel()
        v = self.ver
        self._phrase_timer = threading.Timer(0.8, self._run_phrase, args=(v,))
        self._phrase_timer.daemon = True
        self._phrase_timer.start()

    def _run_phrase(self, v):
        if not self.enabled or v != self.ver:
            return
        ctx = self.tail.strip()
        if len(ctx) < 12:
            return
        try:
            cont = (self.phrase_fn(ctx) or "").strip()
        except Exception:
            cont = ""
        if not cont or v != self.ver:
            return
        items = [{"text": cont, "kind": "phrase"}] + [i for i in self.items if i["kind"] == "next"][:2]
        self.items, self.sel, self.items_ver = items, 0, v
        self.popup.show(items, 0, *caret_screen_pos())
