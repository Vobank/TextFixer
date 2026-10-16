# -*- coding: utf-8 -*-
"""Облачный Gemini: исправление текста, подсказки-фразы, автоподбор модели."""

import time
import queue
import threading
import requests

from .config import save_config, dbg

# Быстрые модели для «гонки» (шлём параллельно, берём первый ответ).
# Латентность Gemini плавает, поэтому несколько кандидатов = стабильная скорость.
RACE_MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.6-flash"]

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

SYSTEM_PROMPT = (
    "Ты — корректор текста. Исправь орфографические ошибки, опечатки и пунктуацию, "
    "правильно расставь запятые. Определи язык (русский или английский) и правь на нём же.\n"
    "ДОПОЛНИТЕЛЬНО:\n"
    "— В русском расставляй букву «ё» там, где она положена (всё, ещё, её, живёт, полёт, тёплый).\n"
    "— Если слово или весь текст набраны СЛУЧАЙНО заглавными буквами (залип Caps Lock), "
    "приведи к нормальному регистру. Но осмысленный регистр не трогай: имена, названия, "
    "аббревиатуры (США, РФ), первую букву предложения.\n"
    "— Разделяй случайно слипшиеся слова (всехорошо → всё хорошо, усложнитпрограмму → "
    "усложнить программу).\n"
    "СТРОГО: не меняй стиль, тон, смысл и порядок слов; не перефразируй; не добавляй и не "
    "убирай предложения; сохраняй эмодзи, переносы строк и форматирование. Текст должен "
    "остаться живым, как будто его просто грамотно записали.\n"
    "Верни ТОЛЬКО исправленный текст — без пояснений, без кавычек, без префиксов."
)

PHRASE_PROMPT = (
    "Продолжи текст пользователя на том же языке естественным образом. "
    "Верни ТОЛЬКО продолжение из 2–5 слов, без повтора уже написанного, "
    "без кавычек и пояснений. Если продолжать нечего — верни пустую строку."
)


class GeminiError(Exception):
    pass


def _headers(api_key):
    return {"x-goog-api-key": api_key, "Content-Type": "application/json"}


def list_flash_models(api_key):
    """Модели с generateContent: сначала стабильные flash, без image/tts и т.п."""
    r = requests.get(f"{GEMINI_BASE}/models", headers=_headers(api_key), timeout=20)
    r.raise_for_status()
    bad = ("image", "tts", "embedding", "vision", "audio", "live", "thinking")
    models = []
    for m in r.json().get("models", []):
        name = m.get("name", "").replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods and name and not any(b in name for b in bad):
            models.append(name)

    def rank(n):
        base = 0 if "flash" in n else 50
        if "lite" in n:
            base += 5
        if "preview" in n or "exp" in n:
            base += 20
        return (base, n)

    models.sort(key=rank)
    return models


def _extract_text(data):
    try:
        parts = data["candidates"][0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError):
        return ""


def correct_text(text, cfg):
    """Исправляет текст через Gemini. «Гонка» нескольких быстрых моделей —
    берём первый пришедший ответ (латентность Gemini сильно плавает)."""
    api_key = cfg.get("api_key", "")
    if not api_key:
        raise GeminiError("нет API-ключа")

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"temperature": cfg.get("temperature", 0.2)},
    }

    def _call(model, timeout=20):
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        return requests.post(url, headers=_headers(api_key), json=body, timeout=timeout)

    # список для гонки: выбранная модель + быстрые кандидаты (без повторов)
    models = []
    for m in [cfg.get("model")] + RACE_MODELS:
        if m and m not in models:
            models.append(m)
    models = models[:3]

    out, winner, last_status = _race(models, _call)
    if out:
        if winner and winner != cfg.get("model"):   # запомним удачную модель
            cfg["model"] = winner
            save_config(cfg)
        return out

    # никто не ответил 200 — подбираем рабочую модель по списку сервера
    if last_status in (None, 429, 503):
        if last_status == 429:
            raise GeminiError("превышен лимит Gemini — подожди минуту (бесплатный тариф)")
        if last_status == 503:
            raise GeminiError("модель перегружена — попробуй ещё раз")
    try:
        for alt in list_flash_models(api_key):
            if alt in models:
                continue
            r = _call(alt, timeout=25)
            if r.status_code == 200:
                out = _extract_text(r.json())
                if out.strip():
                    cfg["model"] = alt
                    save_config(cfg)
                    return out
    except Exception:
        pass
    raise GeminiError(f"не удалось получить ответ (код {last_status})")


def _race(models, _call):
    """Параллельно шлём запрос всем моделям, возвращаем первый успешный ответ.
    Возвращает (text|None, winner_model|None, last_status)."""
    q = queue.Queue()

    def worker(model):
        try:
            r = _call(model)
            q.put((model, r.status_code, r))
        except Exception as e:
            dbg(f"модель {model}: {e}")
            q.put((model, None, None))

    for m in models:
        threading.Thread(target=worker, args=(m,), daemon=True).start()

    last_status = None
    for _ in range(len(models)):
        try:
            model, status, r = q.get(timeout=30)
        except queue.Empty:
            break
        last_status = status if status is not None else last_status
        if status == 200:
            out = _extract_text(r.json())
            if out.strip():
                dbg(f"первым ответил: {model}")
                return out, model, 200
    return None, None, last_status


def predict_continuation(context, cfg):
    """Короткое продолжение фразы для T9 (облако). Пусто при любой ошибке."""
    api_key = cfg.get("api_key", "")
    if not api_key or not context:
        return ""
    body = {
        "system_instruction": {"parts": [{"text": PHRASE_PROMPT}]},
        "contents": [{"parts": [{"text": context}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 24},
    }
    url = f"{GEMINI_BASE}/models/{cfg.get('model', 'gemini-3.5-flash-lite')}:generateContent"
    try:
        r = requests.post(url, headers=_headers(api_key), json=body, timeout=8)
        return _extract_text(r.json()).strip() if r.status_code == 200 else ""
    except Exception:
        return ""


def preserve_edges(original, corrected):
    """Сохраняем ведущие/замыкающие пробелы и переносы оригинала."""
    lead = original[: len(original) - len(original.lstrip())]
    trail = original[len(original.rstrip()):]
    return lead + corrected.strip() + trail
