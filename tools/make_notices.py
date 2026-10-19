# -*- coding: utf-8 -*-
"""Developer tool: generate THIRD_PARTY_NOTICES.md (dictionary sources and licenses).

  python tools/make_notices.py
"""
import os
import sys
import json
import concurrent.futures as cf

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from textfixer.languages import LANGS  # noqa: E402


def wooorm_license(url):
    """The dictionary's SPDX license from package.json in the wooorm/dictionaries repository."""
    base = url.rsplit("/", 1)[0]
    try:
        r = requests.get(base + "/package.json", timeout=20)
        return r.json().get("license") or "?"
    except Exception:
        return "?"


def main():
    with open(os.path.join(HERE, "sources.json"), encoding="utf-8") as f:
        src = json.load(f)
    man = {}
    mp = os.path.join(ROOT, "dist", "dicts", "manifest.json")
    if os.path.exists(mp):
        with open(mp, encoding="utf-8") as f:
            man = json.load(f).get("langs", {})

    def row(code):
        s = src.get(code, {})
        h = s.get("hunspell")
        lic, link = "—", "—"
        if h:
            link = h["dic"].replace("raw.githubusercontent.com", "github.com").replace("/main/", "/tree/main/") \
                .replace("/master/", "/tree/master/").rsplit("/", 1)[0]
            lic = wooorm_license(h["dic"]) if "wooorm" in h["dic"] else "see the folder's README"
            link = f"[{h['src']}]({link})"
        c = s.get("corpus")
        corpus = f"[{c['name']}](https://wortschatz.uni-leipzig.de/en/download)" if c else "—"
        return f"| {code} | {LANGS[code][0]} | {link} | {lic} | {corpus} | CC BY 4.0 |"

    langs = [c for c in LANGS if not man or c in man]
    with cf.ThreadPoolExecutor(12) as ex:
        rows = list(ex.map(row, langs))
    text = f"""# Third-party data

The TextFixer code is distributed under the MIT license (see `LICENSE`). **T9 dictionaries** (`<lang>.pkl.gz`
in GitHub Releases) are derived data from open sources; each dictionary is distributed
under the license terms of its sources:

* **Hunspell dictionaries** — the list of correct word forms (the T9 dictionary stores only their hashes
  and frequent words). The license is in the table below (for LibreOffice, in the dictionary folder's README).
* **Leipzig Corpora Collection** — frequencies of words and word pairs/triples. The downloadable corpora
  are distributed under the CC BY license ([terms](https://wortschatz.uni-leipzig.de/en/usage)).
  D. Goldhahn, T. Eckart, U. Quasthoff: *Building Large Monolingual Dictionaries at the Leipzig
  Corpora Collection: From 100 to 200 Languages.* LREC 2012.
* **wordfreq** (R. Speer) — word frequencies, data under CC BY-SA 4.0
  ([github.com/rspeer/wordfreq](https://github.com/rspeer/wordfreq)); used for the languages
  it supports.
* **Inter font** (language selection window) — SIL Open Font License 1.1, `textfixer/ui/fonts/LICENSE-Inter.txt`.

| Code | Language | Hunspell | Dictionary license | Leipzig corpus | Corpus license |
|---|---|---|---|---|---|
""" + "\n".join(rows) + "\n"
    with open(os.path.join(ROOT, "THIRD_PARTY_NOTICES.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print("THIRD_PARTY_NOTICES.md:", len(rows), "languages")


if __name__ == "__main__":
    main()
