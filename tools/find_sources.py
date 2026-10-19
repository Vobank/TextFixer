# -*- coding: utf-8 -*-
"""Developer tool: finds a Hunspell dictionary (wooorm / LibreOffice) and the largest
Leipzig corpus for each language. Output: tools/sources.json (read by build_all.py).

  python tools/find_sources.py
"""
import os
import sys
import json
import concurrent.futures as cf

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from textfixer.languages import LANGS  # noqa: E402

ISO3 = {"ru": ["rus"], "en": ["eng"], "uk": ["ukr"], "de": ["deu"], "fr": ["fra"], "es": ["spa"],
        "it": ["ita"], "pt": ["por"], "pl": ["pol"], "tr": ["tur"], "nl": ["nld"], "cs": ["ces"],
        "sk": ["slk"], "hu": ["hun"], "ro": ["ron"], "bg": ["bul"], "el": ["ell"], "sv": ["swe"],
        "da": ["dan"], "nb": ["nob", "nor"], "fi": ["fin"], "et": ["est", "ekk"], "lv": ["lav", "lvs"],
        "lt": ["lit"], "sl": ["slv"], "hr": ["hrv"], "sr": ["srp"], "bs": ["bos"], "mk": ["mkd"],
        "sq": ["sqi", "als"], "be": ["bel"], "ga": ["gle"], "cy": ["cym"], "is": ["isl"], "mt": ["mlt"],
        "ca": ["cat"], "eu": ["eus"], "gl": ["glg"], "lb": ["ltz"], "id": ["ind"], "ms": ["msa", "zsm"],
        "vi": ["vie"], "tl": ["tgl"], "sw": ["swa", "swh"], "az": ["aze", "azj"], "uz": ["uzb", "uzn"],
        "af": ["afr"], "eo": ["epo"], "la": ["lat"]}
LO = {"ru": "ru_RU/ru_RU", "en": "en/en_US", "uk": "uk_UA/uk_UA", "de": "de/de_DE_frami",
      "fr": "fr_FR/fr", "es": "es/es_ES", "it": "it_IT/it_IT", "pt": "pt_PT/pt_PT", "pl": "pl_PL/pl_PL",
      "tr": "tr_TR/tr_TR", "nl": "nl_NL/nl_NL", "cs": "cs_CZ/cs_CZ", "sk": "sk_SK/sk_SK",
      "hu": "hu_HU/hu_HU", "ro": "ro/ro_RO", "bg": "bg_BG/bg_BG", "el": "el_GR/el_GR",
      "sv": "sv_SE/sv_SE", "da": "da_DK/da_DK", "nb": "no/nb_NO", "et": "et_EE/et_EE",
      "lv": "lv_LV/lv_LV", "lt": "lt_LT/lt", "sl": "sl_SI/sl_SI", "hr": "hr_HR/hr_HR",
      "sr": "sr/sr", "bs": "bs_BA/bs_BA", "sq": "sq_AL/sq_AL", "be": "be_BY/be_BY",
      "is": "is/is", "ca": "ca/dictionaries/ca", "gl": "gl/gl_ES", "id": "id/id_ID",
      "sw": "sw_TZ/sw_TZ", "af": "af_ZA/af_ZA", "mk": "mk_MK/mk_MK", "eu": "eu/eu", "vi": "vi/vi_VN"}
WOOORM = {c: c for c in ["bg", "ca", "cs", "cy", "da", "de", "el", "en", "eo", "es", "et", "eu", "fr",
                         "ga", "gl", "hr", "hu", "is", "it", "la", "lb", "lt", "lv", "mk", "nb", "nl",
                         "pl", "pt", "ro", "ru", "sk", "sl", "sr", "sv", "tr", "uk", "vi"]}
WOOORM["pt"] = "pt-PT"
S = requests.Session()


def ok(url):
    try:
        r = S.head(url, timeout=15, allow_redirects=True)
        return r.status_code == 200 and int(r.headers.get("Content-Length", "1")) > 1000
    except Exception:
        return False


def find_hunspell(code):
    if code in WOOORM:
        b = f"https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/{WOOORM[code]}/index"
        if ok(b + ".dic"):
            return {"aff": b + ".aff", "dic": b + ".dic", "src": f"wooorm/dictionaries ({WOOORM[code]})"}
    if code in LO:
        b = f"https://raw.githubusercontent.com/LibreOffice/dictionaries/master/{LO[code]}"
        if ok(b + ".dic"):
            return {"aff": b + ".aff", "dic": b + ".dic", "src": f"LibreOffice/dictionaries ({LO[code]})"}
    return None


GENRES = ["news", "newscrawl", "web", "wikipedia", "mixed", "community", "web-public", "newscrawl-public", "web-wrt"]
YEARS = list(range(2024, 2009, -1))


def find_corpus(code):
    base = "https://downloads.wortschatz-leipzig.de/corpora/"
    for size in ["1M", "300K", "100K", "30K"]:
        names = [f"{iso}_{g}_{y}_{size}" for iso in ISO3[code] for g in GENRES for y in YEARS]
        with cf.ThreadPoolExecutor(24) as ex:
            res = list(ex.map(lambda n: (n, ok(base + n + ".tar.gz")), names))
        hits = [n for n, h in res if h]
        if hits:
            # prefer web (living language) and more recent
            pref = {"web": 0, "web-public": 0, "web-wrt": 0, "community": 1, "news": 2, "newscrawl": 2,
                    "newscrawl-public": 2, "mixed": 3, "wikipedia": 4}
            hits.sort(key=lambda n: (pref.get(n.split("_")[1], 5), -int(n.split("_")[2])))
            return {"name": hits[0], "url": base + hits[0] + ".tar.gz", "all": hits[:6]}
    return None


out = {}
for code in LANGS:
    h, c = find_hunspell(code), find_corpus(code)
    out[code] = {"hunspell": h, "corpus": c}
    print(f"{code}: hunspell={'yes' if h else 'NO'}  corpus={c['name'] if c else 'NO'}", flush=True)
with open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "sources.json"),
          "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

