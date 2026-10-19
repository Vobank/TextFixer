# -*- coding: utf-8 -*-
"""User interface strings. English by default; Russian when Windows is in Russian
(or "ui_language": "ru" in config.json). Add a language by adding a dict to STRINGS.

    from .i18n import t
    t("t9_on")                       -> "T9 on ✓ (Tab — suggestion, Esc — hide)"
    t("fix_failed", err="timeout")   -> "⚠ AI error: timeout"
"""

import os
import ctypes

STRINGS = {
    "en": {
        # --- app / tray ---
        "started": "TextFixer is running\nCtrl+Alt+C — fix  •  Ctrl+Alt+T — T9  •  Ctrl+Alt+L — layout",
        "tray_hint": "Ctrl+Alt+C — fix text | Ctrl+Alt+L — convert layout",
        "tray_t9_on": "● T9 on", "tray_t9_off": "○ T9 off",
        "tray_languages": "T9 languages…", "tray_settings": "T9 settings",
        "tray_autostart": "Start with Windows", "tray_key": "Enter / change API key",
        "tray_quit": "Quit",
        "opt_autocomplete": "Suggestions (Tab)", "opt_predict": "Predict the next word",
        "opt_autocorrect": "Fix typos", "opt_layout": "Fix wrong keyboard layout (ghbdtn → привет)",
        "opt_comma": "Auto-commas", "opt_autocap": "Capitalize sentences",
        "opt_double_space": "Double space → period", "opt_caps": "Turn off accidental Caps Lock",
        "opt_phrase": "Cloud phrases (Gemini)",
        "autostart_on": "✓ Start with Windows: on", "autostart_off": "Start with Windows: off",
        "key_title": "TextFixer — Gemini API key",
        "key_prompt": "Paste a free Google AI Studio API key\n(https://aistudio.google.com/apikey):",
        "key_saved": "✓ Key saved. Ready!", "key_missing": "⚠ Text fixing needs an API key",
        "no_key": "⚠ No API key (tray → Enter API key)",
        "select_less": "⚠ Select the part you need (too much text)",
        "select_text": "⚠ Select some text (or type in a field)",
        "fixing": "… fixing", "no_errors": "✓ No mistakes found", "fixed": "✓ Fixed",
        "ai_error": "⚠ AI error: {err}", "failure": "⚠ Something went wrong: {err}",
        "select_plain": "⚠ Select some text", "nothing_to_change": "⚠ Nothing to change",
        "layout_fixed": "✓ Layout converted",
        "lang_window_failed": "⚠ Couldn't open the languages window: {err}",
        "no_languages": "⚠ No T9 languages selected (tray → T9 languages)",
        # --- T9 ---
        "t9_loading": "… loading T9 dictionaries",
        "t9_load_failed": "⚠ Couldn't load dictionaries: {err}",
        "t9_no_dicts": "⚠ No T9 dictionaries — choose languages (tray → T9 languages)",
        "t9_on": "T9 on ✓  (Tab — suggestion, Esc — hide)", "t9_off": "T9 off",
        # --- Gemini ---
        "err_no_key": "no API key",
        "err_quota": "Gemini limit reached — wait a minute (free tier)",
        "err_busy": "models are overloaded — try again",
        "err_no_answer": "no answer (code {code})",
        "err_rewrote": "the AI rewrote the text instead of fixing it — left as is",
        # --- dictionaries ---
        "err_cancelled": "cancelled", "err_corrupt": "file is corrupted (checksum mismatch)",
        "err_not_on_server": "this dictionary is not on the server",
        # --- languages window ---
        "win_title": "TextFixer — languages",
        "h_first": "Choose your <span class=\"grad\">languages</span>",
        "h_again": "My <span class=\"grad\">languages</span>",
        "sub_first": "T9 will suggest words and fix typos and keyboard layout in these languages. "
                     "Only the ones you check are downloaded — no wasted space.",
        "sub_again": "Add or remove T9 languages. New ones are downloaded, unchecked ones are removed.",
        "search": "Search: “German”, “Deutsch”, “de”…",
        "my_layouts": "✨ My keyboards", "clear": "Clear all", "nothing_found": "Nothing found 🤷",
        "later": "Later", "download_start": "Download & start", "done_btn": "Done",
        "downloading": "Downloading…",
        "selected": "Selected: {n} {langs}", "lang1": "language", "lang2": "languages", "lang5": "languages",
        "pick_one": "Pick at least one language", "all_downloaded": "Everything is downloaded",
        "to_download": "Download {n} · {size}", "to_remove": " · remove {n}",
        "installed": "installed", "will_remove": "will be removed", "will_download": "will download",
        "basic": "basic",
        "basic_tip": "No open spelling dictionary for this language — frequent words count as correct",
        "queued": "queued…", "done": "done", "error": "error: {err}",
        "progress": "{got} of {total} MB · {speed} MB/s · ~{left} s left",
        "finished": "Done", "with_errors": "Some downloads failed",
        "toast_errors": "Not everything downloaded: {n}. Check your connection and try again.",
        "toast_unpublished": "Dictionaries aren't published yet: set your repository in "
                             "textfixer/languages.py (DICT_REPO) or \"dict_source\" in config.json.",
        "toast_offline": "Can't reach the dictionary server — showing what's known. Check your connection.",
        "done_title": "All set!", "done_text": "T9 knows {n} {langs}: {names}.",
        "k_tab": "insert a suggestion", "k_stab": "another suggestion", "k_back": "undo a correction",
        "k_t9": "turn T9 on / off", "k_fix": "fix the selection (Gemini)",
        "start_typing": "Start typing", "minimize": "Minimize", "close": "Close",
        "mb": "MB", "tk_title": "Choose T9 languages", "tk_sub": "Only the checked ones are downloaded",
    },
    "ru": {
        "started": "TextFixer запущен\nCtrl+Alt+C — исправить  •  Ctrl+Alt+T — T9  •  Ctrl+Alt+L — раскладка",
        "tray_hint": "Ctrl+Alt+C — исправить | Ctrl+Alt+L — раскладка",
        "tray_t9_on": "● T9 включён", "tray_t9_off": "○ T9 выключен",
        "tray_languages": "Языки T9…", "tray_settings": "Настройки T9",
        "tray_autostart": "Автозапуск с Windows", "tray_key": "Ввести/сменить ключ", "tray_quit": "Выход",
        "opt_autocomplete": "Подсказки (Tab)", "opt_predict": "Предсказывать следующее слово",
        "opt_autocorrect": "Исправлять опечатки", "opt_layout": "Исправлять раскладку (ghbdtn → привет)",
        "opt_comma": "Автозапятые", "opt_autocap": "Заглавная в начале предложения",
        "opt_double_space": "Двойной пробел → точка", "opt_caps": "Гасить случайный Caps Lock",
        "opt_phrase": "Облачные фразы (Gemini)",
        "autostart_on": "✓ Автозапуск включён", "autostart_off": "Автозапуск выключен",
        "key_title": "TextFixer — ключ Gemini",
        "key_prompt": "Вставь бесплатный API-ключ Google AI Studio\n(https://aistudio.google.com/apikey):",
        "key_saved": "✓ Ключ сохранён. Готов к работе!", "key_missing": "⚠ Без ключа исправление не работает",
        "no_key": "⚠ Нет API-ключа (трей → Ввести ключ)",
        "select_less": "⚠ Выдели нужный фрагмент (текста много)",
        "select_text": "⚠ Выдели текст (или напиши в поле)",
        "fixing": "… исправляю", "no_errors": "✓ Ошибок не нашёл", "fixed": "✓ Исправлено",
        "ai_error": "⚠ Ошибка ИИ: {err}", "failure": "⚠ Сбой: {err}",
        "select_plain": "⚠ Выдели текст", "nothing_to_change": "⚠ Нечего менять",
        "layout_fixed": "✓ Раскладка исправлена",
        "lang_window_failed": "⚠ Не открыть окно языков: {err}",
        "no_languages": "⚠ Языки T9 не выбраны (трей → Языки T9)",
        "t9_loading": "… загружаю словари T9", "t9_load_failed": "⚠ Не загрузить словари: {err}",
        "t9_no_dicts": "⚠ Нет словарей T9 — выбери языки (трей → Языки T9)",
        "t9_on": "T9 включён ✓  (Tab — подсказка, Esc — скрыть)", "t9_off": "T9 выключен",
        "err_no_key": "нет API-ключа",
        "err_quota": "превышен лимит Gemini — подожди минуту (бесплатный тариф)",
        "err_busy": "модели перегружены — попробуй ещё раз",
        "err_no_answer": "не удалось получить ответ (код {code})",
        "err_rewrote": "ИИ переписал текст вместо исправления — оставил как было",
        "err_cancelled": "отменено", "err_corrupt": "файл повреждён (не совпала контрольная сумма)",
        "err_not_on_server": "словаря нет на сервере",
        "win_title": "TextFixer — языки",
        "h_first": "Выбери <span class=\"grad\">языки</span>",
        "h_again": "Мои <span class=\"grad\">языки</span>",
        "sub_first": "T9 будет подсказывать слова, исправлять опечатки и раскладку на этих языках. "
                     "Скачаются только отмеченные — лишнего места не займёт.",
        "sub_again": "Добавь или убери языки T9. Новые скачаются, снятые — удалятся с диска.",
        "search": "Поиск: «немецкий», «Deutsch», «de»…",
        "my_layouts": "✨ Мои раскладки", "clear": "Снять всё", "nothing_found": "Ничего не нашлось 🤷",
        "later": "Позже", "download_start": "Скачать и начать", "done_btn": "Готово",
        "downloading": "Скачиваю…",
        "selected": "Выбрано: {n} {langs}", "lang1": "язык", "lang2": "языка", "lang5": "языков",
        "pick_one": "Отметь хотя бы один язык", "all_downloaded": "Всё уже скачано",
        "to_download": "Скачать {n} · {size}", "to_remove": " · удалить {n}",
        "installed": "установлен", "will_remove": "будет удалён", "will_download": "скачается",
        "basic": "базовый",
        "basic_tip": "Для языка нет открытого орфографического словаря — правильными считаются частые слова",
        "queued": "в очереди…", "done": "готово", "error": "ошибка: {err}",
        "progress": "{got} из {total} МБ · {speed} МБ/с · осталось ~{left} с",
        "finished": "Готово", "with_errors": "Есть ошибки",
        "toast_errors": "Не всё скачалось: {n}. Проверь интернет и нажми ещё раз.",
        "toast_unpublished": "Словари ещё не опубликованы: укажи свой репозиторий в "
                             "textfixer/languages.py (DICT_REPO) или \"dict_source\" в config.json.",
        "toast_offline": "Нет связи с сервером словарей — показываю, что известно. Проверь интернет.",
        "done_title": "Готово!", "done_text": "T9 знает {n} {langs}: {names}.",
        "k_tab": "вставить подсказку", "k_stab": "другая подсказка", "k_back": "отменить исправление",
        "k_t9": "включить / выключить T9", "k_fix": "исправить выделенное (Gemini)",
        "start_typing": "Начать печатать", "minimize": "Свернуть", "close": "Закрыть",
        "mb": "МБ", "tk_title": "Выбери языки T9", "tk_sub": "Скачаются только отмеченные",
    },
}

GROUP_NAMES = {
    "en": {"top": "Popular", "eu": "Europe", "world": "Latin script worldwide"},
    "ru": {"top": "Популярные", "eu": "Европа", "world": "Латиница по всему миру"},
}

LANG_NAMES_EN = {
    "ru": "Russian", "en": "English", "uk": "Ukrainian", "de": "German", "fr": "French",
    "es": "Spanish", "it": "Italian", "pt": "Portuguese", "pl": "Polish", "tr": "Turkish",
    "nl": "Dutch", "cs": "Czech", "sk": "Slovak", "hu": "Hungarian", "ro": "Romanian",
    "bg": "Bulgarian", "el": "Greek", "sv": "Swedish", "da": "Danish", "nb": "Norwegian",
    "fi": "Finnish", "et": "Estonian", "lv": "Latvian", "lt": "Lithuanian", "sl": "Slovenian",
    "hr": "Croatian", "sr": "Serbian", "bs": "Bosnian", "mk": "Macedonian", "sq": "Albanian",
    "be": "Belarusian", "ga": "Irish", "cy": "Welsh", "is": "Icelandic", "mt": "Maltese",
    "ca": "Catalan", "eu": "Basque", "gl": "Galician", "lb": "Luxembourgish",
    "id": "Indonesian", "ms": "Malay", "vi": "Vietnamese", "tl": "Filipino", "sw": "Swahili",
    "az": "Azerbaijani", "uz": "Uzbek", "af": "Afrikaans", "eo": "Esperanto", "la": "Latin",
}

_lang = None


def ui_lang(cfg=None):
    """'en' | 'ru' — from config ("ui_language": "auto" | "en" | "ru") or the Windows UI language."""
    global _lang
    want = (cfg or {}).get("ui_language", "auto") if cfg is not None else None
    env = os.environ.get("TEXTFIXER_UI_LANG")              # override (tests, screenshots)
    if env in STRINGS:
        _lang = env
        return _lang
    if want and want != "auto" and want in STRINGS:
        _lang = want
        return _lang
    if _lang is None or want == "auto":
        try:
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        except Exception:
            lid = 0x09
        _lang = "ru" if lid in (0x19, 0x23) else "en"     # Russian / Belarusian Windows
    return _lang


def set_lang(cfg):
    ui_lang(cfg)


def t(key, **kw):
    lang = _lang or ui_lang()
    s = STRINGS.get(lang, {}).get(key) or STRINGS["en"].get(key, key)
    return s.format(**kw) if kw else s


def table(lang=None):
    """All strings for the current language (for the HTML window)."""
    lang = lang or _lang or ui_lang()
    out = dict(STRINGS["en"])
    out.update(STRINGS.get(lang, {}))
    out["_lang"] = lang
    return out


def lang_name(code, ru_name=None):
    """Language name in the interface language."""
    if (_lang or ui_lang()) == "ru" and ru_name:
        return ru_name
    return LANG_NAMES_EN.get(code, code)


def group_name(gid):
    return GROUP_NAMES.get(_lang or ui_lang(), GROUP_NAMES["en"]).get(gid, gid)


def plural(n):
    """Correct word for 'language(s)' after a number."""
    if (_lang or ui_lang()) == "ru":
        m, h = n % 10, n % 100
        return t("lang1") if m == 1 and h != 11 else t("lang2") if 2 <= m <= 4 and not 12 <= h <= 14 \
            else t("lang5")
    return t("lang1") if n == 1 else t("lang2")
