# -*- coding: utf-8 -*-
"""Build the T9 dictionary for one language (run by the developer, not by the app).

Takes:
  * a Hunspell dictionary (.aff/.dic) — which words are correct (if one exists for the language);
  * wordfreq frequencies — how common a word is (if the language is supported);
  * a Leipzig sentence corpus (…-sentences.txt) — frequencies, bigrams/trigrams,
    so that suggestions take the previous words into account ("by context").

Output: <out>/<lang>.pkl.gz. Usually run from tools/build_all.py.

  python tools/build_dicts.py de --hunspell src/de/index --corpus deu_news_2023_1M-sentences.txt
"""

import os
import re
import sys
import gzip
import math
import time
import zlib
import pickle
import argparse
from array import array
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from textfixer.languages import LANGS, word_script, kb_rows  # noqa: E402

BI_TOP, TRI_TOP = 40, 12
BOS = "<s>"
MAX_FORMS = 9_000_000                # safety limit for agglutinative languages
TOKEN_RE = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*|[.!?;:()\"«»…—–\[\]/|]")
WORD_RE = re.compile(r"^[^\W\d_]+(?:[-'][^\W\d_]+)*$")
ELISION = {"fr", "it", "ca", "ga", "mt", "lb"}     # l'homme → l' + homme


class Flat:
    """A "key → (total, [(id, count)…])" table stored in flat arrays."""

    def __init__(self, key_type):
        self.keys = array(key_type)
        self.tot = array("i")
        self.off = array("i", [0])
        self.ids = array("i")
        self.cnt = array("i")

    def add(self, key, tot, items):
        self.keys.append(key)
        self.tot.append(tot)
        for i, c in items:
            self.ids.append(i)
            self.cnt.append(c)
        self.off.append(len(self.ids))

    def dump(self):
        return {"keys": self.keys, "tot": self.tot, "off": self.off,
                "ids": self.ids, "cnt": self.cnt}


def edits1(w, alpha):
    out = set()
    for i in range(len(w) + 1):
        L, R = w[:i], w[i:]
        if R:
            out.add(L + R[1:])
            if len(R) > 1:
                out.add(L + R[1] + R[0] + R[2:])
            for c in alpha:
                out.add(L + c + R[1:])
        for c in alpha:
            out.add(L + c + R)
    out.discard(w)
    return out


def expand_hunspell(dic, limit=MAX_FORMS):
    """All Hunspell word forms (a simple unmunch: suffixes, second-level suffixes,
    prefixes and their combinations), lowercased. Returns (forms, whether complete)."""
    aff = dic.aff
    SFX, PFX = aff.SFX, aff.PFX
    need = getattr(aff, "NEEDAFFIX", None)
    bad = {f for f in (getattr(aff, "FORBIDDENWORD", None), getattr(aff, "ONLYINCOMPOUND", None)) if f}
    forms = set()

    def sfx_forms(stem, flags):
        out = []
        for f in flags:
            for s in SFX.get(f, ()):
                if stem.endswith(s.strip) and s.cond_regexp.search(stem):
                    form = stem[:len(stem) - len(s.strip)] + s.add
                    out.append((form, s))
                    for f2 in s.flags or ():            # second level of suffixes
                        for s2 in SFX.get(f2, ()):
                            if form.endswith(s2.strip) and s2.cond_regexp.search(form):
                                out.append((form[:len(form) - len(s2.strip)] + s2.add, s2))
        return out

    for w in dic.dic.words:
        if len(forms) > limit:
            return {f.lower() for f in forms if f and " " not in f}, False
        flags = set(w.flags or ())
        if flags & bad:
            continue
        stem = w.stem
        if not (need and need in flags):
            forms.add(stem)
        sfx = sfx_forms(stem, flags)
        for form, s in sfx:
            if not (s.flags and need and need in s.flags):
                forms.add(form)
        for f in flags:
            for p in PFX.get(f, ()):
                if stem.startswith(p.strip) and p.cond_regexp.search(stem):
                    forms.add(p.add + stem[len(p.strip):])
                    if p.crossproduct:
                        for form, s in sfx:
                            if s.crossproduct and form.startswith(p.strip):
                                forms.add(p.add + form[len(p.strip):])
    return {f.lower() for f in forms if f and " " not in f}, True


def expand_forms_cased(dic):
    """For fast mode: forms written in lowercase, and forms that exist only capitalized."""
    lower, upper = set(), set()
    saved = dic.dic.words
    for w in saved:
        (upper if w.stem[:1].isupper() else lower).add(w.stem.lower())
    forms, _ = expand_hunspell(dic)
    # forms of "capitalized" stems (names) go to upper, the rest to lower
    up_stems = {w.stem.lower() for w in saved if w.stem[:1].isupper()}
    for f in forms:
        (lower if f not in up_stems else upper).add(f)
    upper -= lower
    return {"lower": lower, "upper": upper}


_DIC = None


def _init_worker(base):
    global _DIC
    from spylls.hunspell import Dictionary
    _DIC = Dictionary.from_files(base)


def _check_chunk(words):
    """0 — unknown, 1 — correct, 2 — correct only when capitalized (name/noun)."""
    out = []
    for w in words:
        try:
            if _DIC.lookup(w):
                out.append(1)
            elif _DIC.lookup(w[:1].upper() + w[1:]):
                out.append(2)
            else:
                out.append(0)
        except Exception:
            out.append(0)
    return out


def check_words(base, words, workers):
    import multiprocessing as mp
    chunks = [words[i:i + 2000] for i in range(0, len(words), 2000)]
    with mp.Pool(workers, initializer=_init_worker, initargs=(base,)) as pool:
        res = []
        for i, part in enumerate(pool.imap(_check_chunk, chunks)):
            res.extend(part)
            if i % 25 == 0:
                print(f"       checked {len(res):,}/{len(words):,}", flush=True)
    return res


def _lines(paths, holdout):
    """Corpus lines; every 200th one (by hash) goes to the held-out set for evaluation."""
    for path in paths:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                tab = line.find("\t")
                text = line[tab + 1:] if tab >= 0 else line
                if zlib.crc32(text.encode("utf-8")) % 200 == 0:
                    if holdout is not None:
                        holdout.append(text.strip())
                    continue
                yield text


def tokenize(paths, lang, holdout=None):
    """Segments (lists of words): split at end-of-sentence marks and at foreign tokens."""
    scr = LANGS[lang][2]
    el = lang in ELISION
    for text in _lines(paths, holdout):
        text = text.lower().replace("’", "'")
        if el:
            text = text.replace("'", "' ")
        seg = [BOS]
        for tok in TOKEN_RE.findall(text):
            if WORD_RE.match(tok) and word_script(tok) == scr:
                seg.append(tok)
            else:
                if len(seg) > 1:
                    yield seg
                seg = [BOS] if tok in ".!?…" else []
        if len(seg) > 1:
            yield seg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lang")
    ap.add_argument("--hunspell", help="path to the dictionary without extension (.aff/.dic)")
    ap.add_argument("--corpus", nargs="+", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "dicts"))
    ap.add_argument("--max-vocab", type=int, default=None)
    ap.add_argument("--holdout-out", help="where to save the held-out sentences")
    ap.add_argument("--max-lookup", type=int, default=350000,
                    help="how many of the most frequent words to check with Hunspell")
    ap.add_argument("--workers", type=int, default=4, help="processes for Hunspell checking")
    ap.add_argument("--fast", action="store_true",
                    help="do not check words via spylls, compare with expanded forms instead "
                         "(for dictionaries on which spylls is very slow: is, eu)")
    a = ap.parse_args()
    lang = a.lang
    native, _, scr, _, _, wf_code, _ = LANGS[lang]
    t0 = time.time()

    dic = None
    if a.hunspell:
        from spylls.hunspell import Dictionary
        dic = Dictionary.from_files(a.hunspell)
    zipf_frequency = top_n_list = None
    if wf_code:
        try:
            from wordfreq import top_n_list, zipf_frequency
            top_n_list(wf_code, 10)
        except Exception as e:
            print("   wordfreq unavailable:", e)
            wf_code = None

    print(f"[{lang}] 1/4 corpus…", flush=True)
    holdout = []
    corpus = Counter()
    for seg in tokenize(a.corpus, lang, holdout):
        corpus.update(seg[1:] if seg[0] == BOS else seg)
    n_tok = sum(corpus.values()) or 1
    print(f"[{lang}]    tokens {n_tok:,}, distinct {len(corpus):,}  ({time.time() - t0:.0f}s)", flush=True)

    # the alphabet comes from the corpus itself (letters of the language's script, frequent enough)
    letters = Counter()
    for w, c in corpus.most_common(50000):
        for ch in w:
            if ch.isalpha():
                letters[ch] += c
    tot_l = sum(letters.values()) or 1
    alpha = "".join(sorted(ch for ch, c in letters.items()
                           if c / tot_l > 1e-4 and word_script(ch) == scr))
    for row in kb_rows(lang):                     # keyboard layout letters — always
        for ch in row:
            if ch not in alpha and ch.isalpha():
                alpha += ch
    print(f"[{lang}]    alphabet ({len(alpha)}): {alpha}", flush=True)

    print(f"[{lang}] 2/4 vocabulary…", flush=True)
    small = n_tok < 5_000_000
    min_c = 2 if small else 3
    cands = {w for w, c in corpus.items() if c >= min_c}
    if wf_code:
        cands |= {w for w in top_n_list(wf_code, 400000)
                  if WORD_RE.match(w) and word_script(w) == scr}

    def zipf(w):
        z = zipf_frequency(w, wf_code) if wf_code else 0.0
        c = corpus.get(w, 0)
        zc = math.log10(c * 1e9 / n_tok) if c else 0.0
        return z if z > 0 else zc

    zs = {w: zipf(w) for w in cands}
    cands = [w for w in sorted(cands, key=lambda w: -zs[w]) if zs[w] >= 0.9][:a.max_lookup]
    valid, proper, other = {}, set(), {}
    if dic is None:
        for w in cands:                           # without Hunspell: "correct" = occurs often
            (valid if zs[w] >= 1.6 else other)[w] = zs[w]
    elif a.fast:
        # fast mode (spylls is too slow on this dictionary): correctness comes from
        # the expanded word forms, "capitalized" if the form exists only capitalized
        forms_all = expand_forms_cased(dic)
        for w in cands:
            if w in forms_all["lower"]:
                valid[w] = zs[w]
            elif w in forms_all["upper"]:
                valid[w] = zs[w]
                proper.add(w)
            else:
                other[w] = zs[w]
    else:
        # Hunspell check — in several processes (spylls is slow on compound words)
        res = check_words(a.hunspell, cands, a.workers)
        for w, r in zip(cands, res):
            if r == 1:
                valid[w] = zs[w]
            elif r == 2:
                valid[w] = zs[w]
                proper.add(w)
            else:
                other[w] = zs[w]

    slang = {}
    for w, z in other.items():
        if z < 3.3 or len(w) < 2:
            continue
        best = max((valid.get(e, 0) for e in edits1(w, alpha)), default=0)
        if best - z >= 1.0:                       # there is a 10+ times more frequent word nearby
            continue
        slang[w] = z
    print(f"[{lang}]    correct {len(valid):,}, capitalized {len(proper):,}, "
          f"slang {len(slang):,}  ({time.time() - t0:.0f}s)", flush=True)

    allw = dict(valid)
    allw.update(slang)
    max_vocab = a.max_vocab or (260000 if lang in ("ru", "uk", "pl", "cs", "fi", "hu", "tr") else 200000)
    words = sorted(allw, key=lambda w: -allw[w])[:max_vocab]
    words.insert(0, BOS)
    wid = {w: i for i, w in enumerate(words)}
    zipfs = array("f", [0.0] + [allw[w] for w in words[1:]])
    proper_ids = sorted(wid[w] for w in proper if w in wid)
    slang_ids = sorted(wid[w] for w in slang if w in wid)

    print(f"[{lang}] 3/4 n-grams…", flush=True)
    bi = defaultdict(Counter)
    tri = Counter()
    for seg in tokenize(a.corpus, lang):
        ids = [wid.get(w, -1) for w in seg]
        for i in range(1, len(ids)):
            x, y = ids[i - 1], ids[i]
            if x >= 0 and y >= 0:
                bi[x][y] += 1
                if i >= 2 and ids[i - 2] >= 0:
                    tri[(ids[i - 2], x, y)] += 1

    bi_flat = Flat("i")
    for x in sorted(bi):
        cnt = bi[x]
        top = [(y, c) for y, c in cnt.most_common(BI_TOP) if c >= 2]
        if top:
            bi_flat.add(x, sum(cnt.values()), top)
    del bi
    tri_group = defaultdict(list)
    for (x, y, z), n in tri.items():
        if n >= 3:
            tri_group[x * 1000000 + y].append((z, n))
    del tri
    tri_flat = Flat("q")
    for key in sorted(tri_group):
        lst = tri_group[key]
        tot = sum(n for _, n in lst)
        if tot >= 6:
            lst.sort(key=lambda t: -t[1])
            tri_flat.add(key, tot, lst[:TRI_TOP])
    del tri_group
    print(f"[{lang}]    bigrams {len(bi_flat.keys):,}, trigrams {len(tri_flat.keys):,}  "
          f"({time.time() - t0:.0f}s)", flush=True)

    # deletion index (SymSpell): crc32(word minus 1 letter) → id
    pairs = []
    for i in range(1, len(words)):
        w = words[i]
        if zipfs[i] < 1.8 or len(w) < 3:
            continue
        for d in {w[:k] + w[k + 1:] for k in range(len(w))}:
            pairs.append((zlib.crc32(d.encode("utf-8")), i))
    pairs.sort()

    # all correct word forms — hashes only (for "the word is correct — leave it alone")
    forms, complete = (expand_hunspell(dic) if dic is not None else (set(), False))
    forms |= set(valid)
    forms |= {f.replace("ё", "е") for f in forms if "ё" in f}
    vhash = array("I", sorted({zlib.crc32(f.encode("utf-8")) for f in forms}))
    del forms
    print(f"[{lang}]    forms {len(vhash):,}{'' if complete else ' (incomplete)'}", flush=True)

    print(f"[{lang}] 4/4 writing…", flush=True)
    os.makedirs(a.out, exist_ok=True)
    data = {"version": 4, "lang": lang, "name": native, "script": scr, "alpha": alpha,
            # "full" Hunspell — only if the forms are fully known (otherwise T9 is more cautious)
            "hunspell": dic is not None and (complete or not a.fast),
            "words": words, "zipf": zipfs, "valid_hash": vhash,
            "proper": array("i", proper_ids), "slang": array("i", slang_ids),
            "bi": bi_flat.dump(), "tri": tri_flat.dump(),
            "del_hash": array("I", [h for h, _ in pairs]),
            "del_ids": array("i", [i for _, i in pairs])}
    out = os.path.join(a.out, f"{lang}.pkl.gz")
    with gzip.open(out + ".tmp", "wb", compresslevel=9) as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(out + ".tmp", out)
    if a.holdout_out:
        with open(a.holdout_out, "w", encoding="utf-8") as f:
            f.write("\n".join(holdout[:5000]))
    print(f"[{lang}] done: {os.path.getsize(out) / 1e6:.1f} MB  ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
