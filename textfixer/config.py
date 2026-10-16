# -*- coding: utf-8 -*-
"""Конфиг и логирование: пути, значения по умолчанию, чтение/запись config.json."""

import os
import json

# корень проекта (где лежит config.json и main.py) — на уровень выше пакета
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEBUG = True


def dbg(*a):
    if DEBUG:
        print("[dbg]", *a)


DEFAULT_CONFIG = {
    "api_key": "",                     # ключ Google AI Studio (или переменная GEMINI_API_KEY)
    "model": "gemini-3.5-flash-lite",  # быстрая бесплатная; при недоступности подберётся сама
    "temperature": 0.2,                # ниже = строже правим, стиль не трогаем
    "copy_delay": 0.06,                # пауза перед копированием, сек
    # --- отображение хоткеев (сами хоткеи фиксированы в hotkeys.py) ---
    "hotkey": "Ctrl+Alt+C",            # исправить выделенное
    "t9_hotkey": "Ctrl+Alt+T",         # вкл/выкл T9
    "layout_hotkey": "Ctrl+Alt+L",     # перевод раскладки
    # --- режим T9 ---
    "t9_start": False,                 # включать T9 сразу при запуске
    "t9_autocomplete": True,           # подсказки-дополнения (Tab принять)
    "t9_autocorrect": True,            # исправление опечаток на пробел
    "t9_phrase": False,                # облачные подсказки-фразы по паузе (едят лимит Gemini)
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[config] не смог прочитать config.json: {e}")
    if not cfg.get("api_key"):
        cfg["api_key"] = os.environ.get("GEMINI_API_KEY", "")
    return cfg


def save_config(cfg):
    """Сохраняет только известные ключи (без мусора)."""
    data = {k: cfg.get(k, DEFAULT_CONFIG[k]) for k in DEFAULT_CONFIG}
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[config] не смог сохранить config.json: {e}")
