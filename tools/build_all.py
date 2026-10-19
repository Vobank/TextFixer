# -*- coding: utf-8 -*-
"""Developer tool: download the sources and build T9 dictionaries for all (or the given) languages.

  pip install -r tools/requirements-build.txt
  python tools/build_all.py --cache D:/t9cache                # all languages
  python tools/build_all.py --cache D:/t9cache de fr es       # only these
  python tools/build_all.py --cache D:/t9cache --jobs 6 --extra-corpus ru=a.txt,b.txt

Output: dist/dicts/<lang>.pkl.gz + dist/dicts/manifest.json — these are published
to a GitHub Release (tools/publish_dicts.ps1), from which the app downloads the selected languages.
"""

import os
import sys
import gzip
import json
import time
import pickle
import shutil
import hashlib
import tarfile
import argparse
import subprocess
import concurrent.futures as cf

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from textfixer.languages import LANGS  # noqa: E402

DICT_FORMAT = 4
FAST = {"is", "eu"}          # spylls takes too long to check words with these dictionaries


def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    tmp = path + ".part"
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    os.replace(tmp, path)
    return path


def fetch(code, src, cache):
    d = os.path.join(cache, code)
    os.makedirs(d, exist_ok=True)
    hun = None
    if src.get("hunspell"):
        download(src["hunspell"]["aff"], os.path.join(d, "dict.aff"))
        download(src["hunspell"]["dic"], os.path.join(d, "dict.dic"))
        hun = os.path.join(d, "dict")
    corpus = None
    if src.get("corpus"):
        name = src["corpus"]["name"]
        sent = os.path.join(d, f"{name}-sentences.txt")
        if not os.path.exists(sent):
            tgz = download(src["corpus"]["url"], os.path.join(d, name + ".tar.gz"))
            with tarfile.open(tgz) as t:
                m = next(x for x in t.getmembers() if x.name.endswith("-sentences.txt"))
                with t.extractfile(m) as fin, open(sent + ".part", "wb") as fout:
                    shutil.copyfileobj(fin, fout)
            os.replace(sent + ".part", sent)
            os.remove(tgz)                         # the archive is no longer needed
        corpus = sent
    return hun, corpus


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("langs", nargs="*")
    ap.add_argument("--cache", required=True, help="folder for downloaded sources (~10 GB)")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist", "dicts"))
    ap.add_argument("--jobs", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 4)),
                    help="how many languages to build in parallel")
    ap.add_argument("--workers", type=int, default=3, help="Hunspell processes per language")
    ap.add_argument("--extra-corpus", action="append", default=[],
                    help="lang=file1,file2 — add your own corpora to a language")
    ap.add_argument("--max-lookup", action="append", default=[],
                    help="lang=N — check only N words with Hunspell (slow dictionaries, e.g. eu=15000)")
    ap.add_argument("--manifest-only", action="store_true", help="only rebuild manifest.json")
    a = ap.parse_args()
    if a.manifest_only:
        a.langs = ["__none__"]
    with open(os.path.join(HERE, "sources.json"), encoding="utf-8") as f:
        sources = json.load(f)
    langs = [c for c in (a.langs or list(LANGS)) if c in LANGS]
    lookups = dict(e.split("=", 1) for e in a.max_lookup)
    extra = {}
    for e in a.extra_corpus:
        k, v = e.split("=", 1)
        extra[k] = v.split(",")
    os.makedirs(a.out, exist_ok=True)
    logs = os.path.join(a.cache, "logs")
    os.makedirs(logs, exist_ok=True)

    print(f"downloading sources for {len(langs)} languages…", flush=True)
    paths = {}
    with cf.ThreadPoolExecutor(6) as ex:
        futs = {ex.submit(fetch, c, sources[c], a.cache): c for c in langs}
        for fu in cf.as_completed(futs):
            c = futs[fu]
            try:
                paths[c] = fu.result()
                print(f"  {c}: sources ready", flush=True)
            except Exception as e:
                print(f"  {c}: DOWNLOAD FAILED — {e}", flush=True)

    def build(c):
        hun, corpus = paths[c]
        corpora = [x for x in [corpus] + extra.get(c, []) if x]
        cmd = [sys.executable, "-X", "utf8", os.path.join(HERE, "build_dicts.py"), c,
               "--out", a.out, "--holdout-out", os.path.join(a.cache, c, "holdout.txt"),
               "--workers", str(a.workers), "--corpus", *corpora]
        if hun:
            cmd[5:5] = ["--hunspell", hun]
        if c in lookups:
            cmd[5:5] = ["--max-lookup", lookups[c]]
        if c in FAST:
            cmd[5:5] = ["--fast"]
        t = time.time()
        with open(os.path.join(logs, f"{c}.log"), "w", encoding="utf-8") as log:
            rc = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT)
        return c, rc, time.time() - t

    print(f"building ({a.jobs} in parallel)…", flush=True)
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for c, rc, dt in ex.map(build, [c for c in langs if c in paths]):
            print(f"  {c}: {'done' if rc == 0 else 'ERROR, see logs/' + c + '.log'} ({dt:.0f}s)",
                  flush=True)

    # manifest — the list of what can be downloaded
    man_path = os.path.join(a.out, "manifest.json")
    manifest = {"format": DICT_FORMAT, "langs": {}}
    if os.path.exists(man_path):
        with open(man_path, encoding="utf-8") as f:
            old = json.load(f)
        if old.get("format") == DICT_FORMAT:
            manifest = old
    for c in LANGS:
        p = os.path.join(a.out, f"{c}.pkl.gz")
        if os.path.exists(p):
            src = sources.get(c, {})
            with gzip.open(p, "rb") as f:
                full = pickle.load(f).get("hunspell", True)    # False — a "basic" dictionary
            manifest["langs"][c] = {
                "file": f"{c}.pkl.gz", "size": os.path.getsize(p), "sha256": sha256(p),
                "hunspell": (src.get("hunspell") or {}).get("src") if full else None,
                "corpus": (src.get("corpus") or {}).get("name"),
            }
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"manifest: {len(manifest['langs'])} languages → {man_path}")


if __name__ == "__main__":
    main()
