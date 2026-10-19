# -*- coding: utf-8 -*-
"""T9 language registry: names, script, keyboard layout (for the typo model),
Windows language ID (to detect the language from the window's keyboard layout),
and data sources for building dictionaries (tools/build_dicts.py)."""

import unicodedata

# Where the app downloads dictionaries from (GitHub Releases of this repository).
# Change to your own repository after publishing: "<user>/<repo>".
DICT_REPO = "Vobank/TextFixer"
DICT_TAG = "dicts-v1"


def dict_base_url():
    return f"https://github.com/{DICT_REPO}/releases/download/{DICT_TAG}"


QWERTY = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
QWERTZ = ["qwertzuiop", "asdfghjkl", "yxcvbnm"]

# code: (native name, Russian name, script, keyboard rows, Windows LANGID,
#        wordfreq code | None, group)
# LANGID is the low 10 bits of the HKL (PRIMARYLANGID).
LANGS = {
    # --- most popular ---
    "ru": ("Русский", "Русский", "cyr", ["йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю"], 0x19, "ru", "top"),
    "en": ("English", "Английский", "lat", QWERTY, 0x09, "en", "top"),
    "uk": ("Українська", "Украинский", "cyr", ["йцукенгшщзхї", "фівапролджє", "ячсмитьбю"], 0x22, "uk", "top"),
    "de": ("Deutsch", "Немецкий", "lat", ["qwertzuiopü", "asdfghjklöä", "yxcvbnm"], 0x07, "de", "top"),
    "fr": ("Français", "Французский", "lat", ["azertyuiop", "qsdfghjklm", "wxcvbn"], 0x0C, "fr", "top"),
    "es": ("Español", "Испанский", "lat", ["qwertyuiop", "asdfghjklñ", "zxcvbnm"], 0x0A, "es", "top"),
    "it": ("Italiano", "Итальянский", "lat", QWERTY, 0x10, "it", "top"),
    "pt": ("Português", "Португальский", "lat", ["qwertyuiop", "asdfghjklç", "zxcvbnm"], 0x16, "pt", "top"),
    "pl": ("Polski", "Польский", "lat", QWERTY, 0x15, "pl", "top"),
    "tr": ("Türkçe", "Турецкий", "lat", ["qwertyuıopğü", "asdfghjklşi", "zxcvbnmöç"], 0x1F, "tr", "top"),
    # --- Europe ---
    "nl": ("Nederlands", "Нидерландский", "lat", QWERTY, 0x13, "nl", "eu"),
    "cs": ("Čeština", "Чешский", "lat", QWERTZ, 0x05, "cs", "eu"),
    "sk": ("Slovenčina", "Словацкий", "lat", QWERTZ, 0x1B, "sk", "eu"),
    "hu": ("Magyar", "Венгерский", "lat", ["qwertzuiopőú", "asdfghjkléá", "yxcvbnm"], 0x0E, "hu", "eu"),
    "ro": ("Română", "Румынский", "lat", ["qwertyuiopăî", "asdfghjklșțâ", "zxcvbnm"], 0x18, "ro", "eu"),
    "bg": ("Български", "Болгарский", "cyr", ["явертъуиопшщ", "асдфгхйкл", "зьцжбнмю"], 0x02, "bg", "eu"),
    "el": ("Ελληνικά", "Греческий", "grk", ["ςερτυθιοπ", "ασδφγηξκλ", "ζχψωβνμ"], 0x08, "el", "eu"),
    "sv": ("Svenska", "Шведский", "lat", ["qwertyuiopå", "asdfghjklöä", "zxcvbnm"], 0x1D, "sv", "eu"),
    "da": ("Dansk", "Датский", "lat", ["qwertyuiopå", "asdfghjklæø", "zxcvbnm"], 0x06, "da", "eu"),
    "nb": ("Norsk", "Норвежский", "lat", ["qwertyuiopå", "asdfghjkløæ", "zxcvbnm"], 0x14, "nb", "eu"),
    "fi": ("Suomi", "Финский", "lat", ["qwertyuiopå", "asdfghjklöä", "zxcvbnm"], 0x0B, "fi", "eu"),
    "et": ("Eesti", "Эстонский", "lat", ["qwertyuiopüõ", "asdfghjklöä", "zxcvbnm"], 0x25, None, "eu"),
    "lv": ("Latviešu", "Латышский", "lat", QWERTY, 0x26, "lv", "eu"),
    "lt": ("Lietuvių", "Литовский", "lat", QWERTY, 0x27, "lt", "eu"),
    "sl": ("Slovenščina", "Словенский", "lat", ["qwertzuiopš", "asdfghjklčž", "yxcvbnm"], 0x24, "sl", "eu"),
    "hr": ("Hrvatski", "Хорватский", "lat", ["qwertzuiopšđ", "asdfghjklčćž", "yxcvbnm"], 0x1A, "sh", "eu"),
    "sr": ("Српски", "Сербский", "cyr", ["љњертзуиопшђ", "асдфгхјклчћж", "ѕџцвбнм"], 0x1A, None, "eu"),
    "bs": ("Bosanski", "Боснийский", "lat", ["qwertzuiopšđ", "asdfghjklčćž", "yxcvbnm"], 0x1A, "sh", "eu"),
    "mk": ("Македонски", "Македонский", "cyr", ["љњертѕуиопшѓ", "асдфгхјклчќж", "зџцвбнм"], 0x2F, "mk", "eu"),
    "sq": ("Shqip", "Албанский", "lat", ["qwertzuiopç", "asdfghjklë", "yxcvbnm"], 0x1C, None, "eu"),
    "be": ("Беларуская", "Белорусский", "cyr", ["йцукенгшўзх", "фывапролджэ", "ячсмітьбю"], 0x23, None, "eu"),
    "ga": ("Gaeilge", "Ирландский", "lat", QWERTY, 0x3C, None, "eu"),
    "cy": ("Cymraeg", "Валлийский", "lat", QWERTY, 0x52, None, "eu"),
    "is": ("Íslenska", "Исландский", "lat", ["qwertyuiopð", "asdfghjklæ", "zxcvbnmþ"], 0x0F, "is", "eu"),
    "mt": ("Malti", "Мальтийский", "lat", QWERTY, 0x3A, None, "eu"),
    "ca": ("Català", "Каталанский", "lat", ["qwertyuiop", "asdfghjklç", "zxcvbnm"], 0x03, "ca", "eu"),
    "eu": ("Euskara", "Баскский", "lat", ["qwertyuiop", "asdfghjklñ", "zxcvbnm"], 0x2D, None, "eu"),
    "gl": ("Galego", "Галисийский", "lat", ["qwertyuiop", "asdfghjklñ", "zxcvbnm"], 0x56, None, "eu"),
    "lb": ("Lëtzebuergesch", "Люксембургский", "lat", ["qwertzuiopü", "asdfghjkléä", "yxcvbnm"], 0x6E, None, "eu"),
    # --- Latin script worldwide ---
    "id": ("Bahasa Indonesia", "Индонезийский", "lat", QWERTY, 0x21, "id", "world"),
    "ms": ("Bahasa Melayu", "Малайский", "lat", QWERTY, 0x3E, "ms", "world"),
    "vi": ("Tiếng Việt", "Вьетнамский", "lat", QWERTY, 0x2A, "vi", "world"),
    "tl": ("Filipino", "Филиппинский", "lat", QWERTY, 0x64, "fil", "world"),
    "sw": ("Kiswahili", "Суахили", "lat", QWERTY, 0x41, None, "world"),
    "az": ("Azərbaycanca", "Азербайджанский", "lat", ["qüertyuiopöğ", "asdfghjklıə", "zxcvbnmçş"], 0x2C, None, "world"),
    "uz": ("Oʻzbekcha", "Узбекский", "lat", QWERTY, 0x43, None, "world"),
    "af": ("Afrikaans", "Африкаанс", "lat", QWERTY, 0x36, None, "world"),
    "eo": ("Esperanto", "Эсперанто", "lat", ["ŝĝertyuiop", "asdfghjklĵĥ", "zĉcvbnmŭ"], None, None, "world"),
    "la": ("Latina", "Латынь", "lat", QWERTY, None, None, "world"),
}

GROUPS = [("top", "Популярные"), ("eu", "Европа"), ("world", "Латиница по всему миру")]

# languages with compound words (Haustür = Haus + Tür) — compounds are validated too
COMPOUND = {"de", "nl", "sv", "da", "nb", "fi", "et", "is", "hu", "lb", "af"}
# linking elements (interfixes) in compound words
LINKERS = {"de": ("", "s", "es", "n", "en", "e", "er"), "nl": ("", "s", "en", "e"),
           "sv": ("", "s"), "da": ("", "s", "e"), "nb": ("", "s", "e"), "is": ("", "s", "a"),
           "af": ("", "s", "e"), "lb": ("", "s", "en"), "fi": ("",), "et": ("",), "hu": ("",)}


def name(code):
    return LANGS[code][1] if code in LANGS else code


def native(code):
    return LANGS[code][0] if code in LANGS else code


def script(code):
    return LANGS[code][2] if code in LANGS else "lat"


def kb_rows(code):
    return LANGS[code][3] if code in LANGS else QWERTY


def langid(code):
    return LANGS[code][4] if code in LANGS else None


def char_script(ch):
    """'cyr' | 'grk' | 'lat' | None for a letter."""
    if not ch.isalpha():
        return None
    o = ord(ch)
    if 0x0400 <= o <= 0x052F:
        return "cyr"
    if 0x0370 <= o <= 0x03FF or 0x1F00 <= o <= 0x1FFF:
        return "grk"
    if o < 0x0250 or 0x1E00 <= o <= 0x1EFF:
        return "lat"
    return None


def word_script(word):
    s = None
    for ch in word:
        cs = char_script(ch)
        if cs is None:
            continue
        if s is None:
            s = cs
        elif cs != s:
            return None                      # mixed scripts
    return s


# letters that Unicode does not decompose into "base + mark"
_NO_DECOMP = {"ł": "l", "ø": "o", "đ": "d", "ı": "i", "ħ": "h", "ŧ": "t", "ŀ": "l",
              "Ł": "L", "Ø": "O", "Đ": "D", "Ħ": "H"}


def base_letter(ch):
    """é → e, š → s, ł → l, ё → е (for the "forgot the diacritics" model)."""
    if ch in _NO_DECOMP:
        return _NO_DECOMP[ch]
    if ch == "ё":
        return "е"
    d = unicodedata.normalize("NFD", ch)
    b = "".join(c for c in d if not unicodedata.combining(c))
    return b if len(b) == 1 else ch


def lang_by_langid(lid, enabled):
    """Languages that match the keyboard layout (hr/sr/bs share one LANGID)."""
    return [c for c in enabled if LANGS.get(c, (None,) * 5)[4] == lid]
