# -*- coding: utf-8 -*-
"""TextFixer main application: Tk thread for toasts, hotkeys, tray icon, T9 mode.

Hotkeys (the `keyboard` library, key press is suppressed):
  Ctrl+Alt+C — fix the selection (or the whole field) with Gemini
  Ctrl+Alt+T — turn T9 on/off
  Ctrl+Alt+L — convert the keyboard layout of the selection (ghbdtn -> привет)
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import simpledialog

from .config import load_config, save_config, dbg
from .gemini import correct_text, predict_continuation, preserve_edges, GeminiError, warm_up
from .keyio import grab_selection, paste_text, clip_set
from .toasts import ToastManager, exclude_from_capture
from .engine import switch_layout
from .t9 import T9Controller
from .i18n import t, set_lang
from . import autostart, dicts


class TextFixerApp:
    def __init__(self):
        self.cfg = load_config()
        set_lang(self.cfg)
        self.busy = threading.Lock()

        self.root = tk.Tk()
        self.root.withdraw()
        self.toasts = ToastManager(self.root)

        self.t9 = T9Controller(
            self.root, self.cfg,
            toast_fn=self.toasts.show,
            phrase_fn=lambda ctx: predict_continuation(ctx, self.cfg),
        )

        self._start_hotkeys()
        self._start_tray()

        dicts.migrate_old()
        need_setup = not self.cfg.get("languages") or not dicts.installed()
        self._ask_key_after_setup = need_setup and not self.cfg.get("api_key")
        if need_setup:                               # first run: languages first, then the key
            self.root.after(500, lambda: self.open_languages(first_run=True))
        elif self.cfg.get("t9_start"):
            self.root.after(800, self.t9.enable)
        if self.cfg.get("api_key"):
            warm_up(self.cfg["api_key"])
        elif not need_setup:
            self.root.after(300, self._ask_api_key)

    # ---- language picker (a separate process with its own window) ----
    def open_languages(self, first_run=False):
        if getattr(self, "_setup_proc", None) and self._setup_proc.poll() is None:
            return                                   # the window is already open
        import subprocess
        # same interpreter (pythonw in the background, no console), separate process:
        # the WebView window needs its own main thread
        args = [sys.executable, "-m", "textfixer.setup_ui"] + (["--first-run"] if first_run else [])
        try:
            self._setup_proc = subprocess.Popen(args, cwd=os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
        except Exception as e:
            self.toasts.show(t("lang_window_failed", err=e), "#e74c3c", 3000)
            return

        def wait():
            rc = self._setup_proc.wait()
            new = load_config()
            self.cfg["languages"] = new.get("languages", [])
            if rc == 0 or first_run:
                self.root.after(0, self._languages_changed)
        threading.Thread(target=wait, daemon=True).start()

    def _languages_changed(self):
        if self.cfg.get("languages") and dicts.installed():
            self.t9.reload()
        else:
            self.toasts.show(t("no_languages"), "#e67e22", 3000)
        if self._ask_key_after_setup:
            self._ask_key_after_setup = False
            self.root.after(600, self._ask_api_key)

    # ---- API key ----
    def _ask_api_key(self):
        dlg = tk.Toplevel(self.root)
        dlg.withdraw()
        exclude_from_capture(dlg)
        key = simpledialog.askstring(t("key_title"), t("key_prompt"), parent=dlg, show="*")
        dlg.destroy()
        if key:
            self.cfg["api_key"] = key.strip()
            save_config(self.cfg)
            warm_up(self.cfg["api_key"])
            self.toasts.show(t("key_saved"), "#2ecc71")
        else:
            self.toasts.show(t("key_missing"), "#e67e22", 2600)

    # ---- hotkeys ----
    def _start_hotkeys(self):
        import keyboard as kblib
        self._kblib = kblib
        self._last_hk = 0.0
        kblib.add_hotkey("ctrl+alt+c", self._hk_fix, suppress=True, trigger_on_release=False)
        kblib.add_hotkey("ctrl+alt+t", self._hk_t9, suppress=True, trigger_on_release=False)
        kblib.add_hotkey("ctrl+alt+l", self._hk_layout, suppress=True, trigger_on_release=False)
        print("[hotkey] Ctrl+Alt+C fix | Ctrl+Alt+T T9 | Ctrl+Alt+L layout")

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
        print("[hotkey] Ctrl+Alt+L (layout)")
        threading.Thread(target=self._process_layout, daemon=True).start()

    # ---- fix the selection (cloud) ----
    def _process_fix(self):
        try:
            if not self.cfg.get("api_key"):
                self.toasts.show(t("no_key"), "#e67e22", 2600)
                return
            cd = self.cfg.get("copy_delay", 0.06)
            # quick selection check (1 attempt, ~0.25 s) so we don't wait for nothing
            t0 = time.time()
            selected, original = grab_selection(cd, attempts=1, polls=12)
            if not selected:                       # nothing selected — take the whole field
                selected, original = grab_selection(0.0, select_all=True)
                if selected and len(selected) > 2000:
                    self.toasts.show(t("select_less"), "#e67e22", 2600)
                    clip_set(original)
                    return
            if not selected or not selected.strip():
                self.toasts.show(t("select_text"), "#e67e22")
                clip_set(original)
                return

            self.toasts.show(t("fixing"), "#3498db", 1200)
            corrected = correct_text(selected, self.cfg)
            final = preserve_edges(selected, corrected)
            if final == selected:
                self.toasts.show(t("no_errors"), "#2ecc71")
                clip_set(original)
                return
            paste_text(final, original)
            dbg(f"whole fix took {time.time() - t0:.2f}s")
            self.toasts.show(t("fixed"), "#2ecc71")
        except GeminiError as e:
            self.toasts.show(t("ai_error", err=e), "#e74c3c", 3000)
        except Exception as e:
            self.toasts.show(t("failure", err=e), "#e74c3c", 3000)
        finally:
            self.busy.release()

    # ---- keyboard layout conversion ----
    def _process_layout(self):
        try:
            cd = self.cfg.get("copy_delay", 0.06)
            selected, original = grab_selection(cd, attempts=1, polls=18)
            if not selected:
                selected, original = grab_selection(0.0, select_all=True)
            if not selected or not selected.strip():
                self.toasts.show(t("select_plain"), "#e67e22")
                clip_set(original)
                return
            fixed = switch_layout(selected)
            if fixed == selected:
                self.toasts.show(t("nothing_to_change"), "#95a5a6")
                clip_set(original)
                return
            paste_text(fixed, original)
            self.toasts.show(t("layout_fixed"), "#2ecc71")
        except Exception as e:
            self.toasts.show(t("failure", err=e), "#e74c3c", 3000)

    # ---- system tray ----
    def _start_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception as e:
            print(f"[tray] tray is unavailable ({e}); running without an icon.")
            return

        img = Image.new("RGB", (64, 64), "#1b1b1f")
        ImageDraw.Draw(img).text((16, 18), "TF", fill="#2ecc71")

        def do_quit(icon, item):
            self.t9.save()                         # don't lose learned words
            icon.stop()
            self.root.after(0, self.root.quit)

        def t9_option(key, title):
            def flip(icon, item):
                self.cfg[key] = not self.cfg.get(key, True)
                save_config(self.cfg)
            return pystray.MenuItem(title, flip, checked=lambda item: bool(self.cfg.get(key, True)))

        def change_key(icon, item):
            self.root.after(0, self._ask_api_key)

        def toggle_t9(icon, item):
            self.root.after(0, self.t9.toggle)

        def toggle_autostart(icon, item):
            state = autostart.toggle()
            self.toasts.show(t("autostart_on") if state else t("autostart_off"),
                             "#2ecc71" if state else "#95a5a6")

        menu = pystray.Menu(
            pystray.MenuItem(t("tray_hint"), None, enabled=False),
            pystray.MenuItem(
                lambda item: (t("tray_t9_on") if self.t9.enabled else t("tray_t9_off")) + "  (Ctrl+Alt+T)",
                toggle_t9, checked=lambda item: self.t9.enabled),
            pystray.MenuItem(t("tray_languages"), lambda icon, item: self.root.after(0, self.open_languages)),
            pystray.MenuItem(t("tray_settings"), pystray.Menu(
                t9_option("t9_autocomplete", t("opt_autocomplete")),
                t9_option("t9_predict", t("opt_predict")),
                t9_option("t9_autocorrect", t("opt_autocorrect")),
                t9_option("t9_layout_switch", t("opt_layout")),
                t9_option("t9_autocomma", t("opt_comma")),
                t9_option("t9_autocap", t("opt_autocap")),
                t9_option("t9_double_space", t("opt_double_space")),
                t9_option("t9_caps_off", t("opt_caps")),
                t9_option("t9_phrase", t("opt_phrase")),
            )),
            pystray.MenuItem(t("tray_autostart"), toggle_autostart,
                             checked=lambda item: autostart.is_enabled()),
            pystray.MenuItem(t("tray_key"), change_key),
            pystray.MenuItem(t("tray_quit"), do_quit),
        )
        self.icon = pystray.Icon("TextFixer", img, "TextFixer", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()
        print("[tray] tray icon started")

    def run(self):
        self.toasts.show(t("started"), "#2ecc71", 3400)
        try:
            self.root.mainloop()
        finally:
            self.t9.save()


def main():
    if "--check" in sys.argv:
        cfg = load_config()
        print("config:", {k: ("***" if k == "api_key" and v else v) for k, v in cfg.items()})
        print("imports ok")
        return
    TextFixerApp().run()
