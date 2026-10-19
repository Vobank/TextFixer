# -*- coding: utf-8 -*-
"""Local multilingual T9 engine (offline), in the style of the iPhone keyboard:

  * language dictionary = Hunspell (valid words, all word forms stored as hashes) +
    wordfreq/corpus frequencies + common slang;
  * language model = trigrams/bigrams from the Leipzig corpus + the user's own
    writing habits (remembered in user_dict.json);
  * suggestions (suggest) are ranked by P(word | 2 previous words);
  * autocorrect (fix) — weighted Damerau–Levenshtein distance (adjacent keys of
    the language's layout, forgotten diacritics é→e, а/о, doubled letters…) +
    context; compound words (German, Swedish, etc.), run-together words, wrong
    keyboard layout (ghbdtn → привет), capitalization of names and German nouns,
    English contractions (dont → don't);
  * automatic commas before conjunctions (comma_before) for ru/uk/pl/cs/sk/de.

Word language: script + active window's keyboard layout + language of recent words
(set_pref). Dictionaries: dicts/<lang>.pkl.gz (tools/build_all.py → GitHub Releases).
"""

import os
import re
import gzip
import json
import math
import time
import zlib
import pickle
import bisect
import threading
from collections import Counter, deque

from .languages import (LANGS, COMPOUND, LINKERS, kb_rows, word_script, base_letter, script)

BOS = "<s>"
ELISION = {"fr", "it", "ca", "ga", "mt", "lb"}
NOUN_CAPS = {"de", "lb"}                  # nouns are capitalized
# where splitting run-together words makes sense (not agglutinative or compounding languages)
SPLIT_OK = {"ru", "uk", "be", "bg", "mk", "sr", "en", "fr", "es", "it", "pt", "ca", "gl", "pl",
            "cs", "sk", "sl", "hr", "bs", "ro", "lt", "lv", "el", "sq", "ga", "cy", "id", "ms", "tl"}
# one letter with two encodings (Romanian: ş/ș, ţ/ț) — both are valid
_VARIANTS = {"ro": str.maketrans("şţŞŢ", "șțȘȚ")}


def has_cyrillic(s):
    return word_script(s) == "cyr"


def apply_case(src, dst):
    """Carries the case of the typed word over to the suggestion/correction."""
    if len(src) > 1 and src.isupper():
        return dst.upper()
    if src[:1].isupper():
        return dst[:1].upper() + dst[1:]
    return dst


_WIDE = {"ß": "ss", "æ": "ae", "œ": "oe", "þ": "th"}


def strip_marks(w):
    """żółty → zolty, tiếng → tieng, straße → strasse (ё is left alone — handled separately)."""
    return "".join(_WIDE.get(c) or (base_letter(c) if c != "ё" else c) for c in w)


# -----------------------------------------------------------------------------
# Error model: which letters get confused with which
# -----------------------------------------------------------------------------
_ROW_SHIFT = [0.0, 0.3, 0.8]
_SOUND = {
    "ru": [("а", "о", .35), ("е", "и", .35), ("е", "ё", .1), ("и", "ы", .55), ("е", "я", .5),
           ("я", "а", .6), ("э", "е", .45), ("ю", "у", .6), ("о", "ё", .5), ("и", "й", .45),
           ("ь", "ъ", .3), ("ш", "щ", .5), ("з", "с", .45), ("д", "т", .5), ("б", "п", .5),
           ("в", "ф", .5), ("г", "к", .5), ("ж", "ш", .5), ("ц", "с", .7), ("ч", "щ", .7),
           ("т", "ц", .8)],
    "uk": [("е", "и", .35), ("и", "і", .4), ("і", "ї", .3), ("е", "є", .3), ("г", "ґ", .3),
           ("а", "о", .5), ("з", "с", .45), ("д", "т", .5), ("б", "п", .5), ("ш", "щ", .5)],
    "en": [("a", "e", .6), ("e", "i", .6), ("i", "y", .6), ("o", "u", .6), ("c", "k", .6),
           ("s", "c", .6), ("s", "z", .6), ("a", "o", .7), ("e", "a", .6)],
    "de": [("s", "ß", .3), ("f", "v", .6), ("d", "t", .6), ("b", "p", .6), ("e", "ä", .4)],
    "pl": [("u", "ó", .3), ("ż", "rz", .3), ("h", "ch", .3)],
    "es": [("b", "v", .45), ("y", "ll", .5), ("s", "z", .5), ("c", "z", .5)],
}
_CHEAP_INDEL = {"ru": {"ь": .45, "ъ": .5, "й": .6, "т": .8, "в": .8, "д": .8, "л": .85},
                "uk": {"ь": .45, "й": .6, "'": .4},
                "en": {"e": .75, "h": .8, "u": .8}, "fr": {"e": .75, "s": .8, "h": .8},
                "de": {"h": .7, "e": .75}, "es": {"h": .6}, "it": {"h": .6}, "pt": {"h": .6}}

# Tuned by coordinate search on RU+EN Wikipedia (held out from training):
# correct fixes 89.5% → 94.2%, wrong fixes 8.4% → 4.8%, valid words broken → 0.55%.
COST = {
    "k": 3.4,          # 1 unit of edit cost ≈ how many times (10^k) more probable the word must be
    "first": 0.0,      # surcharge if the first letter differs
    "kb": 0.75,        # substitution with an adjacent key
    "missing": 0.7,    # missing letter (the most common typo)
    "extra": 1.2,      # extra letter
    "extra_kb": 0.8,   # extra letter from an adjacent key (finger brushed it)
    "double": 0.45,    # doubled/undoubled letter (нн, ll)
    "swap": 0.4,       # transposition of adjacent letters
    "mark": 0.25,      # missing/extra diacritic (e ↔ é, s ↔ š)
    "split": 0.9,      # cost of splitting run-together words
    "max3": 0.75, "max4": 0.8, "max6": 1.15, "max7": 1.6,    # max cost by word length
    "zmin": 2.2, "zmin3": 3.6,  # only correct to sufficiently frequent words (zipf)
}
# language model interpolation: λ = lam · N / (N + k), N = how many times the context was seen
LM = {"bi_lam": 0.85, "bi_k": 25.0, "tri_lam": 0.75, "tri_k": 12.0}

_EM = {}                                  # lang → (subs, neigh, cheap, cheap_alt)


def error_model(lang, alpha):
    em = _EM.get(lang)
    if em is not None:
        return em
    pos = {}
    for r, row in enumerate(kb_rows(lang)):
        for c, ch in enumerate(row):
            pos[ch] = (c + _ROW_SHIFT[min(r, 2)], r)
    subs, neigh = {}, set()
    for a, (xa, ya) in pos.items():
        for b, (xb, yb) in pos.items():
            if a != b and math.hypot(xa - xb, ya - yb) <= 1.25:
                subs[(a, b)] = COST["kb"]
                neigh.add((a, b))
    for a, b, c in _SOUND.get(lang, ()):
        if len(a) == 1 and len(b) == 1:
            for k in ((a, b), (b, a)):
                subs[k] = min(subs.get(k, 1.0), c)
    # diacritics: é ↔ e, é ↔ è (letters sharing a base letter)
    by_base = {}
    for ch in alpha:
        by_base.setdefault(base_letter(ch), []).append(ch)
    for base, group in by_base.items():
        members = set(group) | ({base} if base in alpha else set())
        for a in members:
            for b in members:
                if a != b:
                    subs[(a, b)] = min(subs.get((a, b), 1.0), COST["mark"])
    cheap_alt = {}
    for (a, b), c in subs.items():
        if c <= 0.5:
            cheap_alt.setdefault(a, []).append(b)
    em = (subs, neigh, _CHEAP_INDEL.get(lang, {}), cheap_alt)
    _EM[lang] = em
    return em


def rebuild_costs():
    """Clear the table cache after COST changes (used during tuning)."""
    _EM.clear()


def weighted_distance(a, b, em, limit=3.0):
    """Weighted OSA distance from the typed string a to the word b."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 2:
        return 99.0
    subs, neigh, cheap, _ = em
    c_miss, c_extra, c_ekb, c_dbl, c_swap = (COST["missing"], COST["extra"], COST["extra_kb"],
                                             COST["double"], COST["swap"])

    def missing(i):                        # letter b[i] is missing from the typed string
        ch = b[i]
        if (i > 0 and b[i - 1] == ch) or (i + 1 < lb and b[i + 1] == ch):
            return c_dbl
        return cheap.get(ch, c_miss)

    def extra(i):                          # extra letter a[i] in the typed string
        ch = a[i]
        if (i > 0 and a[i - 1] == ch) or (i + 1 < la and a[i + 1] == ch):
            return c_dbl
        if (i > 0 and (a[i - 1], ch) in neigh) or (i + 1 < la and (a[i + 1], ch) in neigh):
            return c_ekb
        return cheap.get(ch, c_extra)

    miss = [missing(j) for j in range(lb)]
    ext = [extra(i) for i in range(la)]
    prev2 = None
    prev = [0.0] * (lb + 1)
    for j in range(1, lb + 1):
        prev[j] = prev[j - 1] + miss[j - 1]
    for i in range(1, la + 1):
        ei = ext[i - 1]
        cur = [prev[0] + ei] + [0.0] * lb
        ai = a[i - 1]
        best = cur[0]
        for j in range(1, lb + 1):
            bj = b[j - 1]
            sc = 0.0 if ai == bj else subs.get((ai, bj), 1.0)
            v = min(cur[j - 1] + miss[j - 1], prev[j] + ei, prev[j - 1] + sc)
            if i > 1 and j > 1 and ai == b[j - 2] and a[i - 2] == bj and ai != bj:
                v = min(v, prev2[j - 2] + c_swap)
            cur[j] = v
            if v < best:
                best = v
        if best > limit:
            return 99.0
        prev2, prev = prev, cur
    return prev[lb]


def _edits1(word, alpha):
    out = set()
    for i in range(len(word) + 1):
        L, R = word[:i], word[i:]
        if R:
            out.add(L + R[1:])
            if len(R) > 1:
                out.add(L + R[1] + R[0] + R[2:])
            for c in alpha:
                out.add(L + c + R[1:])
        for c in alpha:
            out.add(L + c + R)
    out.discard(word)
    return out


def _deletes1(word):
    return {word[:i] + word[i + 1:] for i in range(len(word))}


def _cheap_variants(word, em):
    """Up to two "cheap" substitutions (а↔о, е↔и, é↔e, adjacent keys…)."""
    alt = em[3]
    lvl1 = set()
    for i, ch in enumerate(word):
        for b in alt.get(ch, ()):
            lvl1.add(word[:i] + b + word[i + 1:])
    lvl2 = set()
    if len(lvl1) < 400:
        for w in lvl1:
            for i, ch in enumerate(w):
                for b in alt.get(ch, ()):
                    lvl2.add(w[:i] + b + w[i + 1:])
    return lvl1 | lvl2


# -----------------------------------------------------------------------------
# Explicit rules (what the error model misses or catches unreliably)
# -----------------------------------------------------------------------------
EN_FORCED = {
    "i": "I", "im": "I'm", "ive": "I've", "id": None, "ill": None,
    "dont": "don't", "cant": "can't", "wont": "won't", "didnt": "didn't",
    "doesnt": "doesn't", "isnt": "isn't", "wasnt": "wasn't", "arent": "aren't",
    "werent": "weren't", "couldnt": "couldn't", "shouldnt": "shouldn't",
    "wouldnt": "wouldn't", "havent": "haven't", "hasnt": "hasn't", "hadnt": "hadn't",
    "youre": "you're", "youve": "you've", "youll": "you'll", "theyre": "they're",
    "theyve": "they've", "thats": "that's", "whats": "what's", "theres": "there's",
    "heres": "here's", "shes": "she's", "hes": None, "itll": "it'll", "lets": None,
    "aint": "ain't", "mustnt": "mustn't", "neednt": "needn't", "wheres": "where's",
    "whos": "who's", "hows": "how's", "ive'": None,
}
RU_FORCED = {
    "щас": None, "ща": None, "чё": None, "че": None, "шо": None, "норм": None,
    "ок": None, "окей": None, "спс": None, "пжл": None, "пж": None, "плз": None,
    "мб": None, "кст": None, "кста": None, "имхо": None, "лол": None, "кек": None,
    "здраствуй": "здравствуй", "здраствуйте": "здравствуйте",
    "пожалуста": "пожалуйста", "пожалуйсто": "пожалуйста", "пожайлуста": "пожалуйста",
    "сдесь": "здесь", "чуствую": "чувствую", "чуство": "чувство", "чуствовать": "чувствовать",
    "солнышко": None, "сонце": "солнце", "лесница": "лестница", "чесно": "честно",
    "вобщем": "в общем", "вообщем": "в общем", "впринципе": "в принципе",
    "вкратце": None, "навсякий": "на всякий", "както": "как-то", "чтото": "что-то",
    "ктото": "кто-то", "гдето": "где-то", "когдато": "когда-то", "почемуто": "почему-то",
    "какойто": "какой-то", "какието": "какие-то", "чтонибудь": "что-нибудь",
    "ктонибудь": "кто-нибудь", "какнибудь": "как-нибудь", "гдинибудь": "где-нибудь",
    "извените": "извините", "извени": "извини", "симпотичный": "симпатичный",
    "агенство": "агентство", "интерестный": "интересный", "интерестно": "интересно",
    "скушно": "скучно", "конешно": "конечно", "канешно": "конечно", "канечно": "конечно",
    "ихний": None, "ложить": "класть", "координально": "кардинально",
    "придти": None, "попробывать": "попробовать", "будте": "будьте",
    "зделать": "сделать", "зделал": "сделал", "зделала": "сделала", "здела": "сделал",
    "севодня": "сегодня", "сиводня": "сегодня", "сегодя": "сегодня",
    "тся": None, "щя": None, "ваще": None, "вообще-то": None,
    "седня": "сегодня", "сёдня": "сегодня", "седня-то": None, "пасиб": None, "пасибо": None,
    "спасибки": None, "приветик": None, "чел": None, "типо": None, "кароч": None,
    "оч": None, "щяс": "щас", "ничо": None, "ничё": None, "чего-то": None,
}
FORCED = {"en": EN_FORCED, "ru": RU_FORCED}


# --- automatic commas: conjunctions, relative pronouns, prepositions, "no comma after these" ---
def _rule(words, rel=(), preps=(), no_prev=(), skip=()):
    return {"words": set(words) | set(rel), "rel": set(rel), "preps": set(preps),
            "no_prev": set(no_prev) | set(preps) | {BOS}, "skip": set(skip)}


_RU_REL = {"который", "которая", "которое", "которые", "которого", "которой", "которому",
           "которым", "которыми", "которых", "котором", "которую"}
_RU_PREPS = {"в", "во", "на", "с", "со", "о", "об", "обо", "про", "за", "по", "для", "у",
             "от", "до", "из", "к", "ко", "при", "через", "над", "под", "перед", "между",
             "без", "после", "около", "благодаря", "согласно", "вместо", "среди"}
COMMA_RULES = {
    "ru": _rule(
        {"что", "чтобы", "но", "а", "однако", "зато", "если", "когда", "хотя", "будто",
         "словно", "поэтому", "потому", "где", "куда", "откуда", "почему", "зачем"},
        _RU_REL, _RU_PREPS,
        {"и", "или", "либо", "не", "ни", "а", "но", "да", "что", "чтобы", "потому", "так",
         "лишь", "только", "даже", "ведь", "вот", "именно", "как", "раз", "тогда", "если",
         "когда", "чем", "ну", "почти", "особенно", "разве", "неужели", "вроде", "хотя",
         "зато", "однако", "кто", "где", "куда", "зачем", "почему", "откуда", "пока",
         "будто", "словно", "поэтому", "тем", "это", "все", "всё", "вообще", "ещё", "еще",
         "уже", "просто", "тоже", "также", "же", "ли", "бы", "б", "ж", "то", "больше",
         "меньше", "лучше", "хуже", "скорее", "прежде", "из-за", "несмотря", "кроме",
         # «Ты где?», «Ты что, …» — after a subject pronoun this is a question, not a conjunction
         "я", "ты", "он", "она", "оно", "мы", "вы", "они"}),
    "uk": _rule(
        {"що", "щоб", "але", "а", "проте", "однак", "якщо", "коли", "хоча", "бо", "тому",
         "де", "куди", "звідки", "чому", "навіщо"},
        {"який", "яка", "яке", "які", "якого", "якої", "якому", "якій", "яким", "якими",
         "яких", "якім", "яку"},
        {"в", "у", "на", "з", "із", "зі", "о", "об", "про", "за", "по", "для", "від", "до",
         "к", "при", "через", "над", "під", "перед", "між", "без", "після", "біля"},
        {"і", "й", "та", "або", "чи", "не", "ні", "а", "але", "що", "щоб", "так", "лише",
         "тільки", "навіть", "ось", "як", "коли", "якщо", "ну", "це", "все", "вже", "теж",
         "також", "ж", "же", "б", "би", "то", "я", "ти", "він", "вона", "воно", "ми", "ви",
         "вони"}),
    "pl": _rule(
        {"że", "żeby", "aby", "ale", "lecz", "bo", "ponieważ", "gdy", "kiedy", "jeśli",
         "jeżeli", "chociaż", "choć", "dlatego", "gdzie", "dlaczego"},
        {"który", "która", "które", "którzy", "którego", "której", "któremu", "którym",
         "którymi", "których", "którą"},
        {"w", "we", "na", "z", "ze", "o", "po", "do", "od", "dla", "przy", "przez", "nad",
         "pod", "przed", "między", "bez", "u", "za"},
        {"i", "oraz", "lub", "albo", "ani", "czy", "nie", "a", "ale", "że", "tak", "tylko",
         "nawet", "jak", "gdy", "kiedy", "to", "ja", "ty", "on", "ona", "ono", "my", "wy",
         "oni", "one", "już", "też", "także", "właśnie"}),
    "cs": _rule(
        {"že", "aby", "ale", "protože", "když", "jestli", "pokud", "přestože", "kde", "proč"},
        {"který", "která", "které", "kteří", "kterého", "kterou", "kterém", "kterým",
         "kterými", "kterých", "kterému"},
        {"v", "ve", "na", "s", "se", "o", "po", "do", "od", "pro", "při", "přes", "nad",
         "pod", "před", "mezi", "bez", "u", "za", "z", "ze", "k", "ke"},
        {"a", "i", "nebo", "ani", "či", "ne", "ale", "že", "tak", "jen", "jenom", "ani",
         "jak", "když", "to", "já", "ty", "on", "ona", "ono", "my", "vy", "oni", "už",
         "také", "taky"}),
    "sk": _rule(
        {"že", "aby", "ale", "pretože", "keď", "ak", "hoci", "kde", "prečo"},
        {"ktorý", "ktorá", "ktoré", "ktorí", "ktorého", "ktorú", "ktorom", "ktorým",
         "ktorými", "ktorých", "ktorému"},
        {"v", "vo", "na", "s", "so", "o", "po", "do", "od", "pre", "pri", "cez", "nad",
         "pod", "pred", "medzi", "bez", "u", "za", "z", "zo", "k", "ku"},
        {"a", "i", "alebo", "ani", "či", "nie", "ale", "že", "tak", "len", "iba", "ako",
         "keď", "to", "ja", "ty", "on", "ona", "ono", "my", "vy", "oni", "už", "tiež"}),
    "de": _rule(
        {"dass", "weil", "obwohl", "ob", "wenn", "damit", "sondern", "aber", "nachdem",
         "bevor", "falls", "sodass", "indem", "wodurch", "weshalb", "warum", "wo"},
        (), (),
        {"und", "oder", "sowie", "so", "als", "nicht", "auch", "nur", "sogar", "aber", "doch",
         "dass", "weil", "wenn", "ob", "ich", "du", "er", "sie", "es", "wir", "ihr", "noch",
         "schon", "erst", "gerade", "selbst", "eben", "denn", "also", "bloß"}),
}


# -----------------------------------------------------------------------------
# Language model for a single language
# -----------------------------------------------------------------------------
class LangModel:
    def __init__(self, path):
        with gzip.open(path, "rb") as f:
            d = pickle.load(f)
        self.lang = d["lang"]
        self.script = d.get("script") or script(self.lang)
        self.words = d["words"]                     # id → word (id 0 = <s>), sorted by frequency
        self.zipf = d["zipf"]
        self.wid = {w: i for i, w in enumerate(self.words)}
        self.proper = set(d["proper"])
        self.slang = set(d.get("slang") or ())      # frequent words not in Hunspell
        self.bi = d["bi"]                           # flat tables: see _flat_lookup
        self.tri = d["tri"]                         # trigram key: a*1e6+b
        self.del_hash = d["del_hash"]               # crc32(deletion) → del_ids
        self.del_ids = d["del_ids"]
        self.valid_hash = d.get("valid_hash")       # crc32 of all Hunspell forms
        self.hunspell = d.get("hunspell", True)     # without Hunspell, correct more cautiously
        self.alpha = d.get("alpha") or "".join(sorted({c for w in self.words[1:5000] for c in w
                                                         if c.isalpha()}))
        self.compound = self.lang in COMPOUND
        self.linkers = LINKERS.get(self.lang, ("",))
        self.em = error_model(self.lang, self.alpha)
        self._bi_cache = {}
        self._tri_cache = {}

        # alphabetical index for prefix completion
        order = sorted(range(1, len(self.words)), key=self.words.__getitem__)
        self.sorted_words = [self.words[i] for i in order]
        self.sorted_ids = order
        # for short prefixes, precompute the most frequent words
        self.prefix_top = {}
        for i in range(1, len(self.words)):
            w = self.words[i]
            for k in (1, 2, 3):
                if len(w) > k:
                    lst = self.prefix_top.setdefault(w[:k], [])
                    if len(lst) < 40:
                        lst.append(i)
        # "typed without diacritics": zolty → żółty (the most frequent word with that base form)
        self.unmarked = {}
        for i in range(1, len(self.words)):
            if self.zipf[i] < 2.3:
                continue
            w = self.words[i]
            s = strip_marks(w)
            if s != w and s not in self.unmarked:
                self.unmarked[s] = i

    # --- word validity ---
    def _valid_simple(self, s):
        if s in self.wid:
            return True
        vh = self.valid_hash
        if not vh:
            return False
        for v in ({s, s.replace("ё", "е")} if "ё" in s else (s,)):
            h = zlib.crc32(v.encode("utf-8"))
            k = bisect.bisect_left(vh, h)
            if k < len(vh) and vh[k] == h:
                return True
        return False

    def is_valid(self, low):
        """Valid word form: a frequent word, any Hunspell form (by hash),
        elision (l'homme), hyphenated words, compound words (Haus+tür)."""
        if self._valid_simple(low):
            return True
        tr = _VARIANTS.get(self.lang)
        if tr and low.translate(tr) != low and self._valid_simple(low.translate(tr)):
            return True
        if "'" in low:
            parts = [p for p in low.split("'") if p]
            if parts and all(len(p) <= 2 or self._valid_simple(p) for p in parts):
                return True
        if "-" in low:
            parts = [p for p in low.split("-") if p]
            if len(parts) > 1 and all(self._valid_simple(p) or len(p) <= 2 for p in parts):
                return True
        if self.compound and len(low) >= 7:
            return self._compound(low, 0)
        return False

    def _compound(self, s, depth):
        for i in range(3, len(s) - 2):
            if not self._valid_simple(s[:i]):
                continue
            rest = s[i:]
            for lk in self.linkers:
                if not rest.startswith(lk):
                    continue
                r = rest[len(lk):]
                if len(r) >= 3 and (self._valid_simple(r) or (depth < 1 and len(r) >= 7
                                                              and self._compound(r, depth + 1))):
                    return True
        return False

    def deleted_from(self, s):
        """IDs of words that yield s by deleting one letter (SymSpell)."""
        h = zlib.crc32(s.encode("utf-8"))
        k = bisect.bisect_left(self.del_hash, h)
        out = []
        while k < len(self.del_hash) and self.del_hash[k] == h:
            out.append(self.del_ids[k])               # collisions are possible — the distance
            k += 1                                    # check filters them out
        return out

    # --- probabilities ---
    def uni(self, i):
        return 10.0 ** (self.zipf[i] - 9.0)

    @staticmethod
    def _flat_lookup(t, key):
        keys = t["keys"]
        k = bisect.bisect_left(keys, key)
        if k == len(keys) or keys[k] != key:
            return 0, {}
        s, e = t["off"][k], t["off"][k + 1]
        return t["tot"][k], dict(zip(t["ids"][s:e], t["cnt"][s:e]))

    def _bi_map(self, a):
        m = self._bi_cache.get(a)
        if m is None:
            m = self._flat_lookup(self.bi, a)
            if len(self._bi_cache) > 5000:
                self._bi_cache.clear()
            self._bi_cache[a] = m
        return m

    def _tri_map(self, a, b):
        key = a * 1000000 + b
        m = self._tri_cache.get(key)
        if m is None:
            m = self._flat_lookup(self.tri, key)
            if len(self._tri_cache) > 5000:
                self._tri_cache.clear()
            self._tri_cache[key] = m
        return m

    def followers(self, p1, p2=None):
        """Words that frequently follow (p2, p1)."""
        out = []
        if p1 is None:
            return out
        if p2 is not None:
            out.extend(self._tri_map(p2, p1)[1].keys())
        out.extend(self._bi_map(p1)[1].keys())
        return out

    def prob(self, i, p1=None, p2=None):
        pu = self.uni(i)
        if p1 is None:
            return pu
        tot, m = self._bi_map(p1)
        p = pu
        if tot:
            lam = LM["bi_lam"] * tot / (tot + LM["bi_k"])
            p = lam * m.get(i, 0) / tot + (1 - lam) * pu
        if p2 is not None:
            tot3, m3 = self._tri_map(p2, p1)
            if tot3:
                lam3 = LM["tri_lam"] * tot3 / (tot3 + LM["tri_k"])
                p = lam3 * m3.get(i, 0) / tot3 + (1 - lam3) * p
        return p

    def prefix_ids(self, low, limit=2500):
        if len(low) <= 3 and low in self.prefix_top:
            ids = list(self.prefix_top[low])
            if len(low) < 3:
                return ids
        lo = bisect.bisect_left(self.sorted_words, low)
        hi = bisect.bisect_left(self.sorted_words, low + "￿", lo)
        if hi - lo > limit:
            return self.prefix_top.get(low[:3], [])
        return [self.sorted_ids[k] for k in range(lo, hi)]

    def display(self, i):
        w = self.words[i]
        return w[:1].upper() + w[1:] if i in self.proper else w


# -----------------------------------------------------------------------------
# User dictionary (what T9 has learned from you)
# -----------------------------------------------------------------------------
class UserModel:
    def __init__(self, path):
        self.path = path
        self.words = Counter()          # word → how many times it was typed
        self.known = set()              # words that must not be corrected
        self.bi = Counter()             # "w1 w2" → count
        self.bi_tot = Counter()         # w1 → how many times something followed it
        self.dirty = False
        self.lock = threading.Lock()
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.words.update(d.get("words", {}))
            self.known.update(d.get("known", []))
            for k, v in d.get("bigrams", {}).items():
                self.bi[k] = v
                self.bi_tot[k.split(" ", 1)[0]] += v
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[t9] failed to read {self.path}: {e}")

    def save(self):
        if not self.dirty:
            return
        with self.lock:
            words = dict(self.words.most_common(20000))
            bigrams = dict(self.bi.most_common(60000))
            data = {"words": words, "known": sorted(self.known), "bigrams": bigrams}
            self.dirty = False
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except Exception as e:
            print(f"[t9] failed to save {self.path}: {e}")

    def observe(self, word, prev=None):
        with self.lock:
            self.words[word] += 1
            if prev:
                self.bi[f"{prev} {word}"] += 1
                self.bi_tot[prev] += 1
            self.dirty = True

    def add_known(self, word):
        with self.lock:
            self.known.add(word)
            self.dirty = True

    def p_next(self, word, prev):
        tot = self.bi_tot.get(prev, 0) if prev else 0
        if not tot:
            return 0.0
        return self.bi.get(f"{prev} {word}", 0) / (tot + 2.0)


# -----------------------------------------------------------------------------
# Engine
# -----------------------------------------------------------------------------
def default_dict_dir():
    from .config import APP_DIR
    return os.path.join(APP_DIR, "dicts")


def installed_langs(dict_dir=None):
    d = dict_dir or default_dict_dir()
    try:
        return [f[:-7] for f in os.listdir(d) if f.endswith(".pkl.gz") and f[:-7] in LANGS]
    except FileNotFoundError:
        return []


class LocalEngine:
    def __init__(self, user_path=None, langs=None, dict_dir=None):
        dict_dir = dict_dir or default_dict_dir()
        if langs is None:
            langs = installed_langs(dict_dir)
        self.models = {}
        for lang in langs:
            path = os.path.join(dict_dir, f"{lang}.pkl.gz")
            if not os.path.exists(path):
                continue
            t = time.time()
            try:
                self.models[lang] = LangModel(path)
            except Exception as e:
                print(f"[t9] dictionary {lang} failed to load: {e!r}")
                continue
            print(f"[t9] dictionary {lang}: {len(self.models[lang].words):,} words "
                  f"in {time.time() - t:.1f}s")
        if user_path is None:
            from .config import APP_DIR
            user_path = os.path.join(APP_DIR, "user_dict.json")
        self.user = UserModel(user_path)
        self.lock = threading.Lock()
        self.pref = list(self.models)            # language order (layout, context)
        self.recent = deque(maxlen=4)            # language of recent words

    # --- language selection ---
    def set_pref(self, layout_langs):
        """Language order: the window's keyboard layout, but if the recent words are
        confidently in another language (German on an English layout), it goes first."""
        order = [c for c in layout_langs if c in self.models]
        if len(self.recent) >= 3 and len(set(self.recent)) == 1:
            r = self.recent[-1]
            if r in self.models:
                order = [r] + [c for c in order if c != r]
        order += [c for c in self.pref if c not in order]
        order += [c for c in self.models if c not in order]
        self.pref = order

    def _models(self, scr):
        return [self.models[c] for c in self.pref if c in self.models
                and self.models[c].script == scr]

    def lang_of(self, word):
        """The language in which the word is valid (respecting priority), or None."""
        low = word.lower()
        for m in self._models(word_script(low)):
            if m.is_valid(low):
                return m.lang
        return None

    # --- helpers ---
    def _ctx_ids(self, m, prev):
        """prev is the list of previous words (last = nearest), BOS = start of phrase."""
        ids = []
        for w in (prev or [])[-2:]:
            ids.append(m.wid.get(w.lower()) if w != BOS else 0)
        p1 = ids[-1] if ids else None
        p2 = ids[-2] if len(ids) >= 2 and p1 is not None else None
        return p1, p2

    def _score(self, m, i, p1, p2, prev_word):
        p = m.prob(i, p1, p2)
        w = m.words[i]
        u = self.user
        pu = u.p_next(w, prev_word)
        if pu:
            p = 0.55 * p + 0.45 * pu
        uc = u.words.get(w)
        if uc:
            p *= 1.0 + min(uc, 50) / 10.0          # words you type often
        return p

    def is_known(self, word):
        low = word.lower()
        scr = word_script(low)
        if scr is None:
            return True
        if low in self.user.known or self.user.words.get(low, 0) >= 3:
            return True
        return any(m.is_valid(low) for m in self._models(scr))

    def learn(self, word, prev=None):
        """A word was typed (and not corrected) — record its frequency and word pairs."""
        low = word.lower()
        if not low or word_script(low) is None:
            return
        if len(low) >= 3:
            # the word's language is the one where it is clearly more frequent (ich: de, not "internet en")
            best, bz, second = None, -1.0, -1.0
            for m in self._models(word_script(low)):
                i = m.wid.get(low)
                z = m.zipf[i] if i is not None else (0.5 if m.is_valid(low) else -1.0)
                if z > bz:
                    best, bz, second = m.lang, z, bz
                elif z > second:
                    second = z
            if best and bz >= 0 and bz - second >= 0.7:
                self.recent.append(best)
        p = prev.lower() if prev and prev != BOS else None
        self.user.observe(low, p)

    def remember(self, word):
        """The user undid a correction — never touch this word again."""
        self.user.add_known(word.lower())

    # --- suggestions ---
    def suggest(self, prefix, prev=None, n=3):
        """Up to n context-aware completions of the prefix. With no prefix, predicts the next word."""
        with self.lock:
            try:
                return self._suggest(prefix, prev, n)
            except Exception as e:
                print("[t9] suggest error:", repr(e))
                return []

    def _suggest(self, prefix, prev, n):
        low = prefix.lower()
        if low:
            scr = word_script(low)
            if scr is None or not low.replace("-", "").replace("'", "").isalpha():
                return []
        else:
            ctx = " ".join(w for w in (prev or []) if w != BOS)
            scr = word_script(ctx) if ctx else None
            if scr is None:
                scr = self.models[self.pref[0]].script if self.pref else None
        models = self._models(scr) if scr else []
        if not models:
            return []
        # context language: the first one where the previous word is known
        m = models[0]
        if prev and prev[-1] != BOS:
            for mm in models:
                if prev[-1].lower() in mm.wid:
                    m = mm
                    break
        out = self._suggest_in(m, low, prefix, prev, n)
        if low and not out and len(models) > 1:            # nothing in the main language — try another
            for mm in models[1:]:
                out = self._suggest_in(mm, low, prefix, prev, n)
                if out:
                    break
        return out

    def _suggest_in(self, m, low, prefix, prev, n):
        p1, p2 = self._ctx_ids(m, prev)
        prev_word = prev[-1].lower() if prev and prev[-1] != BOS else None

        cands = set()
        for i in m.followers(p1, p2):
            if i and m.words[i].startswith(low):
                cands.add(i)
        if low:
            cands.update(m.prefix_ids(low))
        else:
            cands.update(range(1, 30))
        for w, c in self.user.words.most_common(400):          # user's words
            if c >= 2 and w.startswith(low) and w in m.wid:
                cands.add(m.wid[w])

        scored = []
        for i in cands:
            w = m.words[i]
            if w == low or len(w) <= len(low) or i == 0:
                continue
            if "-" in w and "-" not in low and \
                    w.rsplit("-", 1)[1] in ("то", "ка", "де", "таки", "know-what"):
                continue                                   # «дело-то», «мы-то»
            if w.count("-") >= 2:
                continue
            if not low and len(w) < 2:
                continue                                   # a single letter is easier to just type
            scored.append((self._score(m, i, p1, p2, prev_word), i))
        scored.sort(reverse=True)
        # is the typed text itself already a frequent word («ты», «как»)? then only suggest
        # what is more probable than it in this context
        ti = m.wid.get(low) if low else None
        if ti:
            typed_p = self._score(m, ti, p1, p2, prev_word)
            k = 0.12 if len(low) <= 2 else 0.02
            scored = [(s, i) for s, i in scored if s >= k * typed_p]
        out = []
        for _, i in scored[:n]:
            out.append(apply_case(prefix, m.display(i)) if prefix else m.display(i))
        if len(out) < n and low:                           # user's out-of-dictionary words
            for w, c in self.user.words.most_common(400):
                if c >= 3 and w.startswith(low) and w != low and w not in m.wid:
                    out.append(apply_case(prefix, w))
                    if len(out) >= n:
                        break
        return out

    # --- autocorrect ---
    def fix(self, word, prev=None, sentence_start=False, alts=None):
        """The corrected word, or None. prev is the context; alts is [(lang, word)] — the same
        keystrokes in the other installed keyboard layouts (for ghbdtn → привет)."""
        with self.lock:
            try:
                return self._fix(word, prev, sentence_start, alts)
            except Exception as e:
                print("[t9] fix error:", repr(e))
                return None

    def _fix(self, word, prev, sentence_start, alts):
        low = word.lower()
        scr = word_script(low)
        if scr is None or not low.replace("-", "").replace("'", "").isalpha():
            return None
        if low.endswith("-") or low.endswith("'"):
            return None
        models = self._models(scr)
        if not models:
            return None
        # explicit rules of the main language (dont → don't, вобщем → в общем)
        for m in models[:1]:
            forced = FORCED.get(m.lang)
            if forced and low in forced:
                res = forced[low]
                if res is None or res == word:
                    return None
                if res == "I":
                    return "I"
                out = apply_case(word, res)
                if res.startswith("I'"):
                    out = "I'" + res[2:]
                return out if out != word else None

        if low in self.user.known or self.user.words.get(low, 0) >= 3:
            return None
        # names and (German) nouns get a capital letter: москва → Москва, haus → Haus
        if word.islower():
            for m in models[:1]:
                i = m.wid.get(low)
                if i is not None and i in m.proper and m.zipf[i] >= 2.5 and \
                        (m.lang in NOUN_CAPS or m.zipf[i] >= 3.0):
                    return m.display(i)
        # «dziekuje» is common online, but it is the same word without diacritics
        for m in models[:1]:
            i = m.wid.get(low)
            if i is not None and i in m.slang:
                j = m.unmarked.get(low)
                if j is not None and j != i and m.zipf[j] >= m.zipf[i] + 0.3:
                    return apply_case(word, m.display(j))
        if any(m.is_valid(low) for m in models):
            return None                                # valid word form
        if len(word) > 1 and word.isupper() and len(word) <= 6:
            return None                                # abbreviation
        noun_caps = models[0].lang in NOUN_CAPS
        if word[:1].isupper() and not sentence_start and not noun_caps:
            return None                                # name/title mid-sentence

        # 1) wrong keyboard layout? (ghbdtn → привет)
        sw = self._layout_candidate(word, alts)
        if sw:
            return sw
        if len(low) < 3:
            return None

        # (German) a capitalized word mid-sentence is a noun or a name: names are left
        # alone, so only one cheap edit is allowed
        strict = word[:1].isupper() and not sentence_start
        best, best_s = None, -1e9
        for rank, m in enumerate(models[:2]):          # main language + one fallback
            r = self._best_in(m, low, prev, strict)
            if r and r[1] - 0.7 * rank > best_s:
                best, best_s = (m, r[0], r[2]), r[1] - 0.7 * rank
        if best is None:
            return None
        m, val, is_split = best
        if is_split:
            return apply_case(word, m.display(val[0]) + " " + m.display(val[1]))
        return apply_case(word, m.display(val))

    def _best_in(self, m, low, prev, strict=False):
        """Best correction in language m: (id | (id, id), score, is_split) or None."""
        p1, p2 = self._ctx_ids(m, prev)
        prev_word = prev[-1].lower() if prev and prev[-1] != BOS else None
        em = m.em
        L = len(low)
        maxc = (COST["max3"] if L <= 3 else COST["max4"] if L == 4
                else COST["max6"] if L <= 6 else COST["max7"])
        if strict:
            maxc = min(maxc, 0.5)
        if not m.hunspell:                      # not all word forms are known — only close matches
            maxc = min(maxc, 0.8)
        K = COST["k"]
        cands = set()
        e1 = _edits1(low, m.alpha)
        for e in e1:
            i = m.wid.get(e)
            if i is not None:
                cands.add(i)
        for e in (_deletes1(low) | {low} | e1) if L >= 5 else (_deletes1(low) | {low}):
            cands.update(m.deleted_from(e))
        for e in _cheap_variants(low, em):
            i = m.wid.get(e)
            if i is not None:
                cands.add(i)
        if L >= 7:
            for d in _deletes1(low):
                for d2 in _deletes1(d):
                    i = m.wid.get(d2)
                    if i is not None:
                        cands.add(i)
        um = m.unmarked.get(strip_marks(low))             # typed without diacritics
        if um is not None:
            cands.add(um)

        best, best_s = None, -1e9
        for i in cands:
            if i == 0:
                continue
            w = m.words[i]
            z = m.zipf[i]
            if z < (COST["zmin3"] if len(w) <= 3 else COST["zmin"]):
                continue
            if i in m.slang:                           # «zloty» is «złoty» without diacritics
                j = m.unmarked.get(w)
                if j is not None and j != i and m.zipf[j] >= z:
                    continue
            if i == um and strip_marks(w) == strip_marks(low):
                c = 0.15                               # typed with no diacritics at all
            else:
                c = weighted_distance(low, w, em, maxc)
            if c > maxc:
                continue
            if w[0] != low[0]:
                c += COST["first"]
            s = math.log10(self._score(m, i, p1, p2, prev_word)) - K * c
            if s > best_s:
                best, best_s = i, s

        # run-together words: «вобщем» → «в общем» (except languages that write compounds this way)
        split, split_s = None, -1e9
        if L >= 5 and m.lang in SPLIT_OK:
            for k in range(1, L):
                a, b = low[:k], low[k:]
                ia, ib = m.wid.get(a), m.wid.get(b)
                if ia is None or ib is None:
                    continue
                if len(a) < 2 and m.zipf[ia] < 5.0 or len(b) < 2:
                    continue
                if m.zipf[ia] < 3.5 or m.zipf[ib] < 3.0:
                    continue
                if not m._bi_map(ia)[1].get(ib):           # this pair never occurred in the corpus
                    continue
                s = (math.log10(self._score(m, ia, p1, p2, prev_word))
                     + math.log10(m.prob(ib, ia, p1)) - K * COST["split"])
                if s > split_s:
                    split, split_s = (ia, ib), s
        if split and split_s > best_s:
            return split, split_s, True
        if best is None:
            return None
        return best, best_s, False

    def _layout_candidate(self, word, alts):
        """The word was typed in the wrong keyboard layout — return it in the right one."""
        cands = list(alts or [])
        if not cands:                                       # fallback: ru↔en
            sw = switch_layout(word)
            if sw != word:
                scr = word_script(sw.lower())
                cands = [(m.lang, sw) for m in self._models(scr)] if scr else []
        src_scr = word_script(word.lower())
        for lang, sw in cands:
            m = self.models.get(lang)
            low = sw.lower()
            if m is None or not low.isalpha():
                continue
            i = m.wid.get(low)
            if i is None:
                continue
            z = m.zipf[i]
            need = 2.8 if len(low) >= 4 else 3.5 if len(low) == 3 else 5.0
            if z < need:
                continue
            # the original "word" must not be a typo of a frequent word in its own language
            if any(self._close_known(word.lower(), mm) > z - 1.5 for mm in self._models(src_scr)[:2]):
                continue
            return apply_case(word, m.display(i))         # keep the case as typed
        return None

    @staticmethod
    def _close_known(low, m):
        """Frequency (zipf) of the most frequent word within 1 edit of low."""
        best = 0.0
        for e in _edits1(low, m.alpha):
            i = m.wid.get(e)
            if i is not None and m.zipf[i] > best:
                best = m.zipf[i]
        return best

    # --- automatic commas ---
    def comma_before(self, word, prev):
        """Where to put a comma before word: 0 = before the word, 1 = before the previous
        word (a preposition: «, в котором»), None = no comma needed."""
        low = word.lower()
        if not prev or prev[-1] == BOS:
            return None
        p1 = prev[-1].lower()
        lang = self.lang_of(low)
        rule = COMMA_RULES.get(lang)
        if not rule or low not in rule["words"]:
            return None
        if self.lang_of(p1) != lang and word_script(p1) != word_script(low):
            return None
        if low in rule["rel"] and p1 in rule["preps"]:
            if len(prev) >= 2 and prev[-2] != BOS and prev[-2].lower() not in rule["no_prev"]:
                return 1
            return None
        if p1 in rule["no_prev"]:
            return None
        return 0


# -----------------------------------------------------------------------------
# Keyboard layout conversion (ghbdtn <-> привет), Punto Switcher style — for Ctrl+Alt+L
# and for when the actual keys pressed are unknown
# -----------------------------------------------------------------------------
_LOW_EN = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./"
_LOW_RU = "ёйцукенгшщзхъфывапролджэячсмитьбю."
_EN2RU, _RU2EN = {}, {}
for _e, _r in zip(_LOW_EN, _LOW_RU):
    _EN2RU[_e] = _r
    _RU2EN[_r] = _e
    _eu, _ru = _e.upper(), _r.upper()
    if _eu != _e and _ru != _r:                    # uppercase only for letters
        _EN2RU[_eu] = _ru
        _RU2EN[_ru] = _eu
_EN2RU.update({"{": "Х", "}": "Ъ", ":": "Ж", '"': "Э", "<": "Б", ">": "Ю", "~": "Ё"})


def switch_layout(text):
    """Converts the layout of the whole text: Latin <-> Cyrillic by physical keys.
    Direction is chosen by the majority of letters (so commas etc. don't get mangled)."""
    cyr = sum(1 for c in text if "а" <= c.lower() <= "я" or c.lower() == "ё")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    table = _RU2EN if cyr > lat else _EN2RU
    return "".join(table.get(c, c) for c in text)
