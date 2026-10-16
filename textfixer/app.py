# -*- coding: utf-8 -*-
"""Главное приложение TextFixer: Tk-поток для тостов, хоткеи, трей, режим T9.

Хоткеи (библиотека keyboard, с подавлением нажатия):
  Ctrl+Alt+C — исправить выделенное (или весь текст поля) облаком
  Ctrl+Alt+T — вкл/выкл режим T9
  Ctrl+Alt+L — перевести раскладку выделенного (ghbdtn -> привет)
"""

import sys
import time
import threading
import tkinter as tk
from tkinter import simpledialog

from .config import load_config, save_config, dbg
from .gemini import correct_text, predict_continuation, preserve_edges, GeminiError
from .keyio import grab_selection, paste_text, clip_set
from .toasts import ToastManager, exclude_from_capture
from .engine import switch_layout
from .t9 import T9Controller
from . import autostart


class TextFixerApp:
    def __init__(self):
        self.cfg = load_config()
        self.busy = threading.Lock()

        self.root = tk.Tk()
        self.root.withdraw()
        self.toasts = ToastManager(self.root)

        self.t9 = T9Controller(
            self.root, self.cfg,
            toast_fn=self.toasts.show,
            phrase_fn=lambda ctx: predict_continuation(ctx, self.cfg),
        )

        if not self.cfg.get("api_key"):
            self.root.after(300, self._ask_api_key)

        self._start_hotkeys()
        self._start_tray()

        if self.cfg.get("t9_start"):
            self.root.after(800, self.t9.enable)

    # ---- ключ ----
    def _ask_api_key(self):
        dlg = tk.Toplevel(self.root)
        dlg.withdraw()
        exclude_from_capture(dlg)
        key = simpledialog.askstring(
            "TextFixer — ключ Gemini",
            "Вставь бесплатный API-ключ Google AI Studio\n"
            "(https://aistudio.google.com/apikey):",
            parent=dlg, show="*",
        )
        dlg.destroy()
        if key:
            self.cfg["api_key"] = key.strip()
            save_config(self.cfg)
            self.toasts.show("✓ Ключ сохранён. Готов к работе!", "#2ecc71")
        else:
            self.toasts.show("⚠ Без ключа исправление не работает", "#e67e22", 2600)

    # ---- горячие клавиши ----
    def _start_hotkeys(self):
        import keyboard as kblib
        self._kblib = kblib
        self._last_hk = 0.0
        kblib.add_hotkey("ctrl+alt+c", self._hk_fix, suppress=True, trigger_on_release=False)
        kblib.add_hotkey("ctrl+alt+t", self._hk_t9, suppress=True, trigger_on_release=False)
        kblib.add_hotkey("ctrl+alt+l", self._hk_layout, suppress=True, trigger_on_release=False)
        print("[hotkey] Ctrl+Alt+C исправить | Ctrl+Alt+T T9 | Ctrl+Alt+L раскладка")

    def _debounce(self):
        now = time.time()
        if now - self._last_hk < 0.35:
            return False
        self._last_hk = now
        return True

    def _hk_fix(self):
        if not self._debounce():
            return
        print("[hotkey] Ctrl+Alt+C")
        if self.busy.acquire(blocking=False):
            threading.Thread(target=self._process_fix, daemon=True).start()

    def _hk_t9(self):
        if not self._debounce():
            return
        print("[hotkey] Ctrl+Alt+T")
        self.root.after(0, self.t9.toggle)

    def _hk_layout(self):
        if not self._debounce():
            return
        print("[hotkey] Ctrl+Alt+L (раскладка)")
        threading.Thread(target=self._process_layout, daemon=True).start()

    # ---- исправление выделенного (облако) ----
    def _process_fix(self):
        try:
            if not self.cfg.get("api_key"):
                self.toasts.show("⚠ Нет API-ключа (открой трей → Ключ)", "#e67e22", 2600)
                return
            cd = self.cfg.get("copy_delay", 0.06)
            # быстрая проверка выделения (1 попытка ~0.35с), чтобы не ждать впустую
            selected, original = grab_selection(cd, attempts=1, polls=18)
            if not selected:                       # нет выделения — берём весь текст поля
                selected, original = grab_selection(0.0, select_all=True)
                if selected and len(selected) > 2000:
                    self.toasts.show("⚠ Выдели нужный фрагмент (текста много)", "#e67e22", 2600)
                    clip_set(original)
                    return
            if not selected or not selected.strip():
                self.toasts.show("⚠ Выдели текст (или напиши в поле)", "#e67e22")
                clip_set(original)
                return

            self.toasts.show("… исправляю", "#3498db", 1200)
            corrected = correct_text(selected, self.cfg)
            final = preserve_edges(selected, corrected)
            if final == selected:
                self.toasts.show("✓ Ошибок не нашёл", "#2ecc71")
                clip_set(original)
                return
            paste_text(final, original)
            self.toasts.show("✓ Исправлено", "#2ecc71")
        except GeminiError as e:
            self.toasts.show(f"⚠ Ошибка ИИ: {e}", "#e74c3c", 3000)
        except Exception as e:
            self.toasts.show(f"⚠ Сбой: {e}", "#e74c3c", 3000)
        finally:
            self.busy.release()

    # ---- перевод раскладки ----
    def _process_layout(self):
        try:
            cd = self.cfg.get("copy_delay", 0.06)
            selected, original = grab_selection(cd, attempts=1, polls=18)
            if not selected:
                selected, original = grab_selection(0.0, select_all=True)
            if not selected or not selected.strip():
                self.toasts.show("⚠ Выдели текст", "#e67e22")
                clip_set(original)
                return
            fixed = switch_layout(selected)
            if fixed == selected:
                self.toasts.show("⚠ Нечего менять", "#95a5a6")
                clip_set(original)
                return
            paste_text(fixed, original)
            self.toasts.show("✓ Раскладка исправлена", "#2ecc71")
        except Exception as e:
            self.toasts.show(f"⚠ Сбой: {e}", "#e74c3c", 3000)

    # ---- системный трей ----
    def _start_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception as e:
            print(f"[tray] трей недоступен ({e}); работаю без иконки.")
            return

        img = Image.new("RGB", (64, 64), "#1b1b1f")
        ImageDraw.Draw(img).text((16, 18), "TF", fill="#2ecc71")

        def do_quit(icon, item):
            icon.stop()
            self.root.after(0, self.root.quit)

        def change_key(icon, item):
            self.root.after(0, self._ask_api_key)

        def toggle_t9(icon, item):
            self.root.after(0, self.t9.toggle)

        def toggle_autostart(icon, item):
            state = autostart.toggle()
            self.toasts.show("✓ Автозапуск включён" if state else "Автозапуск выключен",
                             "#2ecc71" if state else "#95a5a6")

        menu = pystray.Menu(
            pystray.MenuItem("Ctrl+Alt+C — исправить | Ctrl+Alt+L — раскладка",
                             None, enabled=False),
            pystray.MenuItem(
                lambda item: ("● T9 включён" if self.t9.enabled else "○ T9 выключен")
                + "  (Ctrl+Alt+T)",
                toggle_t9, checked=lambda item: self.t9.enabled),
            pystray.MenuItem("Автозапуск с Windows", toggle_autostart,
                             checked=lambda item: autostart.is_enabled()),
            pystray.MenuItem("Ввести/сменить ключ", change_key),
            pystray.MenuItem("Выход", do_quit),
        )
        self.icon = pystray.Icon("TextFixer", img, "TextFixer", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()
        print("[tray] иконка в трее запущена")

    def run(self):
        self.toasts.show(
            "TextFixer запущен\n"
            "Ctrl+Alt+C — исправить  •  Ctrl+Alt+T — T9  •  Ctrl+Alt+L — раскладка",
            "#2ecc71", 3400)
        self.root.mainloop()


def main():
    if "--check" in sys.argv:
        cfg = load_config()
        print("config:", {k: ("***" if k == "api_key" and v else v) for k, v in cfg.items()})
        print("импорты ок")
        return
    TextFixerApp().run()
