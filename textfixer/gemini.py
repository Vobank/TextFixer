# -*- coding: utf-8 -*-
"""Cloud Gemini: text correction, phrase suggestions, automatic model selection.

Speed:
  * thinkingLevel=minimal — models do not "think" before answering (was 1–4 s, now ~0.5 s);
  * a single persistent HTTPS connection (keep-alive) + warm-up at startup;
  * a "hedge" request: if the primary model is silent for HEDGE_AFTER seconds
    or hits the rate limit, try the fallback right away (instead of 3 requests per
    correction as before, which quickly ate the free quota);
  * a cache of recent corrections.
"""

import time
import queue
import difflib
import threading
from collections import OrderedDict

import requests

from .config import save_config, dbg
from .i18n import t as _tr

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# primary + fallbacks (measured with thinkingLevel=minimal: 3.5-flash-lite ~0.5 s,
# 3.1-flash-lite ~1.7 s; 3.5-flash has a small quota on the free tier)
FAST_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash"]
HEDGE_AFTER = 1.5          # sec: how long to wait for the primary model before the fallback

# Tuned by measurements: without examples the model "improved" the text (Russian slang
# "щас" -> "сейчас", turned commas into "!") and mis-split merged words. The examples cover
# several languages; the model always answers in the language of the text.
SYSTEM_PROMPT = (
    "You are a proofreader. Fix ONLY mistakes in the text: spelling, typos and punctuation "
    "(commas, a period or \"?\" at the end). Never change the language of the text.\n"
    "Rules:\n"
    "1. Minimal edits. Keep intentional casual style and slang as is (e.g. Russian щас, чё, норм; "
    "English gonna, lol, ok). Do not replace words with synonyms and do not \"improve\" the style. "
    "But always fix typos and misspellings of ordinary words in any language "
    "(малако → молоко, кароче → короче, realy → really, your → you're when the meaning requires it).\n"
    "2. Punctuation: add missing commas; end a question with \"?\". Do not turn commas or periods "
    "into \"!\" and do not split sentences where the author didn't. Keep emoticons like \")\".\n"
    "3. Language-specific spelling: restore missing diacritics (Russian «ё»: всё, ещё, займёт; "
    "German umlauts; Polish, Czech, French accents…). Merged or wrongly split words: "
    "вобщем → в общем, потомучто → потому что, alot → a lot.\n"
    "4. Caps Lock: if a word or the whole text was typed in CAPITALS by accident "
    "(hELLO, ЗАВТРА СОБРАНИЕ) — restore normal case; keep acronyms (USA, EU, IT) and names. "
    "Capitalize the first letter of a sentence.\n"
    "5. Keep emoji, line breaks and formatting. If there are no mistakes, return the text unchanged.\n"
    "Examples:\n"
    "привет как дела → Привет, как дела?\n"
    "щас приду вобщем жди → Щас приду, в общем, жди.\n"
    "я незнаю что делать) → Я не знаю, что делать)\n"
    "i dont think its realy ok → I don't think it's really ok\n"
    "ich weis nicht ob er kommt → Ich weiß nicht, ob er kommt.\n"
    "URGENT CALL ME BACK → Urgent, call me back\n"
    "Return ONLY the corrected text, without explanations or quotes."
)

PHRASE_PROMPT = (
    "Continue the user's text naturally in the same language. "
    "Return ONLY a continuation of 2–5 words, without repeating what is already written, "
    "without quotes or explanations. If there is nothing to continue, return an empty string."
)


class GeminiError(Exception):
    pass


_session = requests.Session()
_session.mount("https://", requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=6))
_no_thinking_cfg = set()            # models that rejected thinkingConfig (400) — send without it
_cache = OrderedDict()              # (model-independent) text → correction
_last_phrase = [0.0]


def _headers(api_key):
    return {"x-goog-api-key": api_key, "Content-Type": "application/json"}


def warm_up(api_key):
    """Open the connection in advance (TLS handshake ~0.2–0.5 s); does not consume quota."""
    if not api_key:
        return

    def run():
        try:
            _session.get(f"{GEMINI_BASE}/models?pageSize=1", headers=_headers(api_key), timeout=10)
            dbg("Gemini: connection warmed up")
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


def list_flash_models(api_key):
    """Models with generateContent: stable flash ones first, excluding image/tts etc."""
    r = _session.get(f"{GEMINI_BASE}/models", headers=_headers(api_key), timeout=20)
    r.raise_for_status()
    bad = ("image", "tts", "embedding", "vision", "audio", "live", "thinking", "omni")
    models = []
    for m in r.json().get("models", []):
        name = m.get("name", "").replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods and name and not any(b in name for b in bad):
            models.append(name)

    def rank(n):
        base = 0 if "flash" in n else 50
        if "lite" in n:
            base -= 5                      # lite ones are the fastest
        if "preview" in n or "exp" in n:
            base += 20
        return (base, n)

    models.sort(key=rank)
    return models


def _extract_text(data):
    try:
        parts = data["candidates"][0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))
    except (KeyError, IndexError):
        return ""


def _post(model, api_key, system, text, gen_cfg, timeout):
    """A single generateContent request. Returns (status, text)."""
    cfg = dict(gen_cfg)
    if model not in _no_thinking_cfg:
        cfg["thinkingConfig"] = {"thinkingLevel": "minimal"}
    body = {"system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": text}]}], "generationConfig": cfg}
    url = f"{GEMINI_BASE}/models/{model}:generateContent"
    r = _session.post(url, headers=_headers(api_key), json=body, timeout=(5, timeout))
    if r.status_code == 400 and "thinkingConfig" in cfg:
        # the model does not support thinkingLevel=minimal — stop sending it
        _no_thinking_cfg.add(model)
        return _post(model, api_key, system, text, gen_cfg, timeout)
    return r.status_code, (_extract_text(r.json()) if r.status_code == 200 else "")


def _hedged(models, call):
    """models[0] first; the fallback if the first is silent for HEDGE_AFTER s or returns an error.
    Returns (text, winner, last_status)."""
    q = queue.Queue()
    started = []

    def start(m):
        started.append(m)

        def worker():
            t = time.time()
            try:
                status, out = call(m)
            except Exception as e:
                dbg(f"Gemini {m}: {e}")
                status, out = None, ""
            dbg(f"Gemini {m}: {status} in {time.time() - t:.2f}s")
            q.put((m, status, out))
        threading.Thread(target=worker, daemon=True).start()

    pending = list(models)
    start(pending.pop(0))
    last_status, done = None, 0
    deadline = time.time() + 25
    while done < len(started) and time.time() < deadline:
        wait = HEDGE_AFTER if pending else max(0.1, deadline - time.time())
        try:
            m, status, out = q.get(timeout=wait)
        except queue.Empty:
            if pending:                       # the primary is slow — bring in the fallback
                start(pending.pop(0))
            continue
        done += 1
        last_status = status if status is not None else last_status
        if status == 200 and out.strip():
            return out, m, 200
        if pending:                           # error/rate limit — the next one right away
            start(pending.pop(0))
    return None, None, last_status


def _models_for(cfg):
    """Order: the fastest known ones, then the model from the config (if different)."""
    models = []
    for m in FAST_MODELS + [cfg.get("model")]:
        if m and m not in models:
            models.append(m)
    return models


def correct_text(text, cfg):
    """Corrects text via Gemini (fast model + hedge)."""
    api_key = cfg.get("api_key", "")
    if not api_key:
        raise GeminiError(_tr("err_no_key"))
    if text in _cache:
        _cache.move_to_end(text)
        dbg("Gemini: from cache")
        return _cache[text]

    gen = {"temperature": min(float(cfg.get("temperature", 0.1)), 0.2),
           "maxOutputTokens": max(256, len(text) * 2)}
    t = time.time()
    out, winner, last_status = _hedged(
        _models_for(cfg),
        lambda m: _post(m, api_key, SYSTEM_PROMPT, text, gen, timeout=20))
    if out:
        dbg(f"Gemini: fixed in {time.time() - t:.2f}s by {winner}")
        out = _sanity(text, out)
        _cache[text] = out
        if len(_cache) > 50:
            _cache.popitem(last=False)
        return out

    if last_status == 429:
        raise GeminiError(_tr("err_quota"))
    if last_status == 503:
        raise GeminiError(_tr("err_busy"))
    # nobody answered — pick a working model from the server's list
    try:
        for alt in list_flash_models(api_key):
            if alt in _models_for(cfg):
                continue
            status, out = _post(alt, api_key, SYSTEM_PROMPT, text, gen, timeout=20)
            if status == 200 and out.strip():
                cfg["model"] = alt
                save_config(cfg)
                return _sanity(text, out)
    except Exception:
        pass
    raise GeminiError(_tr("err_no_answer", code=last_status))


def _sanity(original, corrected):
    """Protection against "rewriting": if the model changed the text beyond recognition
    (instead of fixing errors), keep the original."""
    a, b = original.strip(), corrected.strip()
    if len(a) >= 40:
        ratio = difflib.SequenceMatcher(None, a.lower(), b.lower(), autojunk=False).ratio()
        if ratio < 0.6:
            dbg(f"Gemini: the answer differs too much (similarity {ratio:.2f}) — not applying it")
            raise GeminiError(_tr("err_rewrote"))
    return corrected


def predict_continuation(context, cfg):
    """A short phrase continuation for T9 (cloud). Empty on any error.
    At most once every 3 s so as not to eat the quota needed for corrections."""
    api_key = cfg.get("api_key", "")
    if not api_key or not context:
        return ""
    now = time.time()
    if now - _last_phrase[0] < 3.0:
        return ""
    _last_phrase[0] = now
    gen = {"temperature": 0.4, "maxOutputTokens": 24}
    try:
        status, out = _post(FAST_MODELS[0], api_key, PHRASE_PROMPT, context, gen, timeout=6)
        return out.strip() if status == 200 else ""
    except Exception:
        return ""


def preserve_edges(original, corrected):
    """Preserve the original's leading/trailing whitespace and line breaks."""
    lead = original[: len(original) - len(original.lstrip())]
    trail = original[len(original.rstrip()):]
    return lead + corrected.strip() + trail
