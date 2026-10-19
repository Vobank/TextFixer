# -*- coding: utf-8 -*-
"""Config and logging: paths, defaults, reading/writing config.json."""

import os
import json

# project root (where config.json and main.py live) — one level above the package
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEBUG = True


def dbg(*a):
    if DEBUG:
        print("[dbg]", *a)


DEFAULT_CONFIG = {
    "api_key": "",                     # Google AI Studio key (or the GEMINI_API_KEY variable)
    "model": "gemini-3.5-flash-lite",  # fallback model (primary ones are FAST_MODELS in gemini.py)
    "temperature": 0.1,                # lower = stricter fixes, style left untouched
    "copy_delay": 0.06,                # pause before copying, sec
    "ui_language": "auto",             # interface language: "auto" (from Windows), "en", "ru"
    # --- hotkey display (the hotkeys themselves are fixed in app.py) ---
    "hotkey": "Ctrl+Alt+C",            # fix the selection
    "t9_hotkey": "Ctrl+Alt+T",         # T9 on/off
    "layout_hotkey": "Ctrl+Alt+L",     # keyboard layout conversion
    # --- T9 mode ---
    "languages": [],                   # T9 languages (chosen in a window on first run)
    "dict_source": "",                 # where to download dictionaries from ("" — GitHub Releases)
    "t9_start": True,                  # enable T9 right at startup
    "t9_autocomplete": True,           # suggestion bar (Tab — insert, Shift+Tab — another one)
    "t9_predict": True,                # predict the next word after a space
    "t9_min_prefix": 2,                # from which letter to show suggestions
    "t9_autocorrect": True,            # typo correction on space/punctuation/Enter
    "t9_layout_switch": True,          # ghbdtn → привет and switch the window's layout
    "t9_autocomma": True,              # commas before «что», «но», «а», «который»…
    "t9_autocap": True,                # capital letter at the start of a sentence
    "t9_double_space": True,           # double space → ". "
    "t9_caps_off": True,               # undo accidental Caps Lock (Shift with Caps on, «пРИВЕТ»)
    "t9_phrase": False,                # cloud phrase suggestions on pause (consume the Gemini quota)
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[config] could not read config.json: {e}")
    if not cfg.get("api_key"):
        cfg["api_key"] = os.environ.get("GEMINI_API_KEY", "")
    return cfg


def save_config(cfg):
    """Saves only the known keys (no junk)."""
    data = {k: cfg.get(k, DEFAULT_CONFIG[k]) for k in DEFAULT_CONFIG}
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[config] could not save config.json: {e}")
