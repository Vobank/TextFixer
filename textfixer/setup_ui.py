# -*- coding: utf-8 -*-
"""T9 language picker (first run and tray → "T9 languages…").

Runs as a separate process:  python -m textfixer.setup_ui [--first-run]
The UI is HTML (textfixer/ui/setup.html) in the built-in WebView2 (pywebview); a simple
Tk window is the fallback. The choice is saved to config.json ("languages"); checked
dictionaries are downloaded, unchecked ones removed. Exit code 0 — something changed.
"""

import os
import sys
import time
import ctypes
import threading

from . import dicts
from .config import load_config, save_config
from .languages import LANGS, GROUPS
from .i18n import t, table, set_lang, lang_name, group_name, plural

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "setup.html")


def _hide_from_capture(title):
    """Like every TextFixer window, this one is excluded from screen capture."""
    if os.environ.get("TEXTFIXER_SHOW_IN_CAPTURE"):         # for README screenshots
        return
    u = ctypes.windll.user32
    for _ in range(50):
        hwnd = u.FindWindowW(None, title)
        if hwnd:
            u.SetWindowDisplayAffinity(hwnd, 0x11)
            return
        time.sleep(0.1)


class Api:
    """Methods called from JavaScript (window.pywebview.api.*). Private attributes start
    with "_" so pywebview does not try to expose them to JS."""

    def __init__(self, first_run):
        self._first_run = first_run
        self._cfg = load_config()
        set_lang(self._cfg)
        self._window = None
        self._manifest = dicts.fetch_manifest(self._cfg) or {}
        self._prog = {"langs": {}, "pct": 0, "text": "", "finished": False, "errors": 0}
        self._changed = False
        self._lock = threading.Lock()

    # ---- for JS ----
    def state(self):
        inst = dicts.installed()
        avail = self._manifest.get("langs", {})
        sel = [c for c in (self._cfg.get("languages") or []) if c in LANGS]
        if not sel and inst and not self._first_run:
            sel = list(inst)
        langs = []
        for code, (native, ru_name, *_rest) in LANGS.items():
            info = avail.get(code, {})
            if avail and code not in avail and code not in inst:
                continue                              # no dictionary for this language yet
            langs.append({"code": code, "native": native, "name": lang_name(code, ru_name),
                          "group": LANGS[code][6],
                          "size": info.get("size") or inst.get(code, 0),
                          "installed": code in inst,
                          "hunspell": bool(info.get("hunspell")) if info else None})
        src = dicts.source(self._cfg)
        return {"langs": langs, "groups": [(gid, group_name(gid)) for gid, _ in GROUPS],
                "selected": sel, "strings": table(),
                "system": [c for c in dicts.system_langs() if any(l["code"] == c for l in langs)],
                "first_run": self._first_run, "offline": not avail,
                "unpublished": "/OWNER/" in src}

    def start(self, chosen):
        threading.Thread(target=self._run, args=(list(chosen),), daemon=True).start()
        return True

    def progress(self):
        with self._lock:
            return dict(self._prog, langs={k: dict(v) for k, v in self._prog["langs"].items()})

    def minimize(self):
        if self._window:
            self._window.minimize()

    def close(self):
        if self._window:
            self._window.destroy()

    def finish(self):
        self.close()

    # ---- downloading ----
    def _run(self, chosen):
        inst = dicts.installed()
        avail = self._manifest.get("langs", {})
        need = [c for c in chosen if c not in inst]
        total = sum(int(avail.get(c, {}).get("size") or 0) for c in need) or 1
        done_bytes = {c: 0 for c in need}
        t0 = time.time()
        errors = []
        mb = t("mb")
        with self._lock:
            for c in need:
                self._prog["langs"][c] = {"pct": 0, "state": t("queued")}

        def upd(c, done, size):
            done_bytes[c] = done
            with self._lock:
                self._prog["langs"][c] = {"pct": round(100 * done / max(size, 1)),
                                          "state": f"{done / 1048576:.1f} / {size / 1048576:.1f} {mb}"}
                got = sum(done_bytes.values())
                speed = got / max(time.time() - t0, 0.1)
                left = (total - got) / max(speed, 1)
                self._prog["pct"] = round(100 * got / total)
                self._prog["text"] = t("progress", got=f"{got / 1048576:.0f}",
                                       total=f"{total / 1048576:.0f}",
                                       speed=f"{speed / 1048576:.1f}", left=max(0, int(left)))

        def one(c):
            info = avail.get(c)
            if not info:
                raise RuntimeError(t("err_not_on_server"))
            size = int(info.get("size") or 0)
            dicts.download(c, info, self._cfg, progress=lambda d, tot: upd(c, d, tot or size))

        sem = threading.Semaphore(3)                  # 3 files in parallel
        threads = []

        def worker(c):
            with sem:
                try:
                    one(c)
                    with self._lock:
                        self._prog["langs"][c] = {"pct": 100, "state": t("done")}
                except Exception as e:
                    errors.append(c)
                    with self._lock:
                        self._prog["langs"][c] = {"pct": 0, "state": "",
                                                  "error": t("error", err=e)[:80]}

        for c in need:
            th = threading.Thread(target=worker, args=(c,), daemon=True)
            th.start()
            threads.append(th)
        for th in threads:
            th.join()

        for c in inst:                                # unchecked languages are removed
            if c not in chosen:
                dicts.remove(c)
        ok = [c for c in chosen if c in dicts.installed()]
        self._cfg = load_config()
        self._cfg["languages"] = ok
        save_config(self._cfg)
        self._changed = True
        names = ", ".join(lang_name(c, LANGS[c][1]) for c in ok[:6]) + ("…" if len(ok) > 6 else "")
        with self._lock:
            self._prog.update(finished=True, errors=len(errors), pct=100, count=len(ok),
                              names=names, langs_word=plural(len(ok)),
                              text=t("finished") if not errors else t("with_errors"))


def run_webview(api):
    import webview
    title = t("win_title")
    window = webview.create_window(title, HTML, js_api=api, width=1040, height=740,
                                   min_size=(760, 560), frameless=True, easy_drag=False,
                                   background_color="#0b0c12")
    api._window = window
    threading.Thread(target=_hide_from_capture, args=(title,), daemon=True).start()
    webview.start(gui="edgechromium", debug=False)


def run_tk(api):
    """Fallback window when WebView2 is not available."""
    import tkinter as tk
    from tkinter import ttk
    st = api.state()
    root = tk.Tk()
    root.title(t("win_title"))
    root.geometry("560x640")
    root.configure(bg="#11131c")
    tk.Label(root, text=t("tk_title"), fg="#f3f4f8", bg="#11131c",
             font=("Segoe UI", 16, "bold")).pack(pady=(16, 4))
    tk.Label(root, text=t("tk_sub"), fg="#9aa0b4", bg="#11131c",
             font=("Segoe UI", 10)).pack()
    frame = tk.Frame(root, bg="#11131c")
    frame.pack(fill="both", expand=True, padx=16, pady=10)
    canvas = tk.Canvas(frame, bg="#11131c", highlightthickness=0)
    sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg="#11131c")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    chosen = set(st["selected"] or st["system"])
    vars_ = {}
    for l in st["langs"]:
        v = tk.BooleanVar(value=l["code"] in chosen)
        vars_[l["code"]] = v
        size = f'  ·  {l["size"] / 1048576:.0f} {t("mb")}' if l["size"] else ""
        tk.Checkbutton(inner, text=f'{l["native"]} — {l["name"]}{size}', variable=v,
                       fg="#f3f4f8", bg="#11131c", selectcolor="#2b2f45", activebackground="#11131c",
                       activeforeground="#fff", font=("Segoe UI", 11), anchor="w").pack(fill="x")
    status = tk.Label(root, text="", fg="#9aa0b4", bg="#11131c", font=("Segoe UI", 10))
    status.pack()

    def go():
        api.start([c for c, v in vars_.items() if v.get()])
        btn.configure(state="disabled", text=t("downloading"))

        def tick():
            p = api.progress()
            status.configure(text=p["text"])
            if p["finished"]:
                root.destroy()
            else:
                root.after(200, tick)
        tick()
    btn = tk.Button(root, text=t("download_start"), command=go, bg="#7c5cff", fg="#fff",
                    font=("Segoe UI", 12, "bold"), relief="flat", padx=20, pady=8)
    btn.pack(pady=12)
    root.mainloop()


def main():
    first = "--first-run" in sys.argv
    dicts.migrate_old()
    api = Api(first)
    try:
        run_webview(api)
    except Exception as e:
        print("[setup] WebView is not available, using a simple window:", e)
        run_tk(api)
    sys.exit(0 if api._changed else 1)


if __name__ == "__main__":
    main()
