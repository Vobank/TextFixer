# -*- coding: utf-8 -*-
"""Developer tool: evaluate T9 dictionary quality on held-out sentences
(every 200th corpus sentence is excluded from the build — build_dicts --holdout-out).

  python tools/eval_lang.py de D:/t9cache/de/holdout.txt [--dict-dir dist/dicts]

Prints: how often T9 "corrects" correct words (lower is better) and how many
artificial typos (adjacent key, missing letter, extra letter, transposition, diacritics)
it corrects properly.
"""
import os
import re
import sys
import random
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from textfixer import engine as E  # noqa: E402
from textfixer.languages import word_script, base_letter  # noqa: E402

WORD = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lang")
    ap.add_argument("holdout")
    ap.add_argument("--dict-dir", default=os.path.join(os.path.dirname(HERE), "dist", "dicts"))
    ap.add_argument("-n", type=int, default=600)
    a = ap.parse_args()
    eng = E.LocalEngine(os.path.join(os.environ.get("TEMP", "."), "t9_eval_nouser.json"),
                        langs=[a.lang], dict_dir=a.dict_dir)
    eng.user.save = lambda: None
    m = eng.models[a.lang]
    rnd = random.Random(3)
    lines = [l for l in open(a.holdout, encoding="utf-8").read().splitlines() if l.strip()]
    rnd.shuffle(lines)
    neigh = {}
    for x, y in m.em[1]:
        neigh.setdefault(x, []).append(y)
    fp = n = 0
    fps = []
    ok = wrong = nt = 0
    wrongs = []
    for line in lines[:a.n]:
        toks = [t for t in WORD.findall(line) if word_script(t) == m.script]
        if len(toks) < 4:
            continue
        for j, w in enumerate(toks):
            prev = ([E.BOS] + toks[:j])[-2:]
            st = j == 0
            n += 1
            r = eng.fix(w, prev, st)
            if r is not None and r.lower() != w.lower():
                fp += 1
                if len(fps) < 20:
                    fps.append(f"{w}→{r}")
            lw = w.lower()
            if len(lw) >= 4 and lw in m.wid and rnd.random() < 0.3:
                for _ in range(15):
                    k = rnd.choice(["kb", "del", "ins", "swap", "mark"])
                    i = rnd.randrange(len(lw))
                    c = lw[i]
                    if k == "kb" and neigh.get(c):
                        t = lw[:i] + rnd.choice(neigh[c]) + lw[i + 1:]
                    elif k == "del":
                        t = lw[:i] + lw[i + 1:]
                    elif k == "ins" and neigh.get(c):
                        t = lw[:i] + rnd.choice(neigh[c]) + lw[i:]
                    elif k == "swap" and i < len(lw) - 1 and lw[i] != lw[i + 1]:
                        t = lw[:i] + lw[i + 1] + lw[i] + lw[i + 2:]
                    elif k == "mark" and base_letter(c) != c:
                        t = lw[:i] + base_letter(c) + lw[i + 1:]
                    else:
                        continue
                    if t != lw and not eng.is_known(t):
                        nt += 1
                        r = eng.fix(t, prev, st)
                        if r and r.lower() == lw:
                            ok += 1
                        elif r:
                            wrong += 1
                            if len(wrongs) < 12:
                                wrongs.append(f"{t}→{r} ({lw})")
                        break
    print(f"[{a.lang}] breaks correct words: {100 * fp / max(n, 1):.2f}% ({fp}/{n})")
    print(f"[{a.lang}] typos: correct {100 * ok / max(nt, 1):.1f}%, wrong {100 * wrong / max(nt, 1):.1f}% (n={nt})")
    if fps:
        print("   false positive examples:", ", ".join(fps[:12]))
    if wrongs:
        print("   wrong correction examples:", ", ".join(wrongs))


if __name__ == "__main__":
    main()
