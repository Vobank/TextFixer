# -*- coding: utf-8 -*-
"""T9 dictionaries: what is installed, what can be downloaded, verified downloading.

Dictionaries live in <app folder>/dicts/<lang>.pkl.gz. They are downloaded from GitHub
Releases (languages.DICT_REPO / DICT_TAG) according to manifest.json. The source can be
overridden in config.json ("dict_source": a URL or a local folder) —
for example, the dist/dicts folder after tools/build_all.py.
"""

import os
import json
import shutil
import hashlib
import ctypes

from .config import APP_DIR
from .i18n import t as _tr
from .languages import LANGS, dict_base_url

DICT_DIR = os.path.join(APP_DIR, "dicts")


def source(cfg=None):
    src = (cfg or {}).get("dict_source") or os.environ.get("TEXTFIXER_DICTS") or dict_base_url()
    return src.rstrip("/\\")


def _is_local(src):
    return not src.lower().startswith(("http://", "https://"))


def installed():
    """{code: size in bytes} of the installed dictionaries."""
    out = {}
    try:
        for f in os.listdir(DICT_DIR):
            if f.endswith(".pkl.gz") and f[:-7] in LANGS:
                out[f[:-7]] = os.path.getsize(os.path.join(DICT_DIR, f))
    except FileNotFoundError:
        pass
    return out


def fetch_manifest(cfg=None, timeout=10):
    """The source's manifest.json (or the last saved one if there is no network)."""
    src = source(cfg)
    cache = os.path.join(DICT_DIR, "manifest.json")
    try:
        if _is_local(src):
            with open(os.path.join(src, "manifest.json"), encoding="utf-8") as f:
                man = json.load(f)
        else:
            import requests
            r = requests.get(f"{src}/manifest.json", timeout=timeout)
            r.raise_for_status()
            man = r.json()
        os.makedirs(DICT_DIR, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(man, f, ensure_ascii=False)
        return man
    except Exception:
        try:
            with open(cache, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


def download(code, info, cfg=None, progress=None, cancel=None):
    """Download a language's dictionary. progress(done, total). Verifies SHA-256."""
    src = source(cfg)
    os.makedirs(DICT_DIR, exist_ok=True)
    dst = os.path.join(DICT_DIR, f"{code}.pkl.gz")
    tmp = dst + ".part"
    total = int(info.get("size") or 0)
    h = hashlib.sha256()
    done = 0
    if _is_local(src):
        fin = open(os.path.join(src, info.get("file", f"{code}.pkl.gz")), "rb")
        chunks = iter(lambda: fin.read(1 << 18), b"")
        closer = fin.close
    else:
        import requests
        r = requests.get(f"{src}/{info.get('file', f'{code}.pkl.gz')}", stream=True, timeout=30)
        r.raise_for_status()
        total = total or int(r.headers.get("Content-Length") or 0)
        chunks = r.iter_content(1 << 18)
        closer = r.close
    try:
        with open(tmp, "wb") as f:
            for chunk in chunks:
                if cancel and cancel():
                    raise RuntimeError(_tr("err_cancelled"))
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except BaseException:
        closer()
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    closer()
    want = info.get("sha256")
    if want and h.hexdigest() != want:
        os.remove(tmp)
        raise RuntimeError(_tr("err_corrupt"))
    os.replace(tmp, dst)
    return dst


def remove(code):
    try:
        os.remove(os.path.join(DICT_DIR, f"{code}.pkl.gz"))
    except FileNotFoundError:
        pass


def migrate_old():
    """Dictionaries from old versions (textfixer/data) → dicts/."""
    old = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    if not os.path.isdir(old):
        return
    os.makedirs(DICT_DIR, exist_ok=True)
    for f in os.listdir(old):
        if f.endswith(".pkl.gz") and not os.path.exists(os.path.join(DICT_DIR, f)):
            shutil.copy2(os.path.join(old, f), os.path.join(DICT_DIR, f))


def system_langs():
    """Languages of the installed keyboard layouts + the Windows language — offered first."""
    from .languages import lang_by_langid
    out = []
    try:
        u = ctypes.windll.user32
        n = u.GetKeyboardLayoutList(0, None)
        arr = (ctypes.c_void_p * max(n, 1))()
        u.GetKeyboardLayoutList(n, arr)
        lids = [(h or 0) & 0x3FF for h in arr]
        lids.append(ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF)
        for lid in lids:
            for c in lang_by_langid(lid, list(LANGS)):
                if c not in out and c not in ("sr", "bs"):     # hr/sr/bs share a LANGID
                    out.append(c)
    except Exception:
        pass
    return out or ["en"]
