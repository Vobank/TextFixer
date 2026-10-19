# -*- coding: utf-8 -*-
"""Pop-up notifications (toasts) in the screen corner, hidden from screen recording."""

import queue
import ctypes
import tkinter as tk

# WDA_EXCLUDEFROMCAPTURE (Win10 2004+/Win11): the window is visible on screen but not in recordings/streams.
WDA_EXCLUDEFROMCAPTURE = 0x00000011


def exclude_from_capture(win):
    """Makes the window invisible to screenshots/recordings/streams."""
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    except Exception as e:
        print(f"[capture] failed to hide window: {e}")


class ToastManager:
    """Notifications in the bottom-right corner (created in the main Tk thread via a queue)."""

    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.root.after(100, self._poll)

    def show(self, text, color="#2ecc71", ms=1600):
        self.q.put((text, color, ms))

    def _poll(self):
        try:
            while True:
                text, color, ms = self.q.get_nowait()
                self._render(text, color, ms)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _render(self, text, color, ms):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#1b1b1f")
        try:
            win.attributes("-alpha", 0.95)
        except Exception:
            pass
        frame = tk.Frame(win, bg="#1b1b1f", padx=16, pady=10,
                         highlightbackground=color, highlightthickness=2)
        frame.pack()
        tk.Label(frame, text=text, bg="#1b1b1f", fg="#f5f5f5",
                 font=("Segoe UI", 11), justify="left", wraplength=360).pack()
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_width(), win.winfo_height()
        win.geometry(f"+{sw - w - 24}+{sh - h - 60}")
        exclude_from_capture(win)
        win.after(ms, win.destroy)
