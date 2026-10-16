# -*- coding: utf-8 -*-
"""Локальный словарный движок T9: автодополнение и исправление опечаток
по частотному словарю wordfreq (офлайн), плюс перевод раскладки (Punto Switcher)."""

RU_ALPHA = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
EN_ALPHA = "abcdefghijklmnopqrstuvwxyz"


def has_cyrillic(s):
    return any("а" <= c.lower() <= "я" or c.lower() == "ё" for c in s)


def _osa_distance(a, b):
    """Расстояние Дамерау–Левенштейна (OSA): замена/вставка/удаление/перестановка."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 2:
        return 99
    prev2 = None
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            if (i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]):
                cur[j] = min(cur[j], prev2[j - 2] + 1)      # перестановка
        prev2, prev = prev, cur
    return prev[lb]


class LocalEngine:
    """Загружает словари wordfreq (150k) и даёт complete()/correct()."""

    def __init__(self):
        from wordfreq import top_n_list, zipf_frequency
        self._zipf = zipf_frequency
        self.learned = set()                       # слова пользователя — не трогаем
        self.vocab = {"ru": set(), "en": set()}    # большой словарь для проверки
        self._index = {"ru": {}, "en": {}}         # префикс -> частые продолжения
        self._build(top_n_list)

    def _build(self, top_n_list):
        for lang in ("ru", "en"):
            voc = set()
            idx = {}
            for word in top_n_list(lang, 150000):          # словарь проверки/исправления
                if word.isalpha():
                    voc.add(word)
            for word in top_n_list(lang, 60000):           # подсказки — частые слова
                if len(word) >= 4 and word.isalpha():
                    for n in (2, 3):
                        if len(word) > n:
                            lst = idx.setdefault(word[:n], [])
                            if len(lst) < 10:
                                lst.append(word)
            self.vocab[lang] = voc
            self._index[lang] = idx

    @staticmethod
    def _lang(word):
        return "ru" if has_cyrillic(word) else "en"

    def learn(self, word):
        if len(word) >= 3:
            self.learned.add(word.lower())

    def complete(self, prefix):
        """Самое частое уместное дополнение префикса или None."""
        if len(prefix) < 3 or not prefix.isalpha():
            return None
        low = prefix.lower()
        lang = self._lang(prefix)
        if self._zipf(low, lang) >= 4.2:               # уже частое слово — не навязываем
            return None
        for w in self._index[lang].get(low[:3], []):
            if w.startswith(low) and len(w) > len(low) and self._zipf(w, lang) >= 4.0:
                return w[0].upper() + w[1:] if prefix[0].isupper() else w
        return None

    @staticmethod
    def _edits1(word, alpha):
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        res = set()
        for L, R in splits:
            if R:
                res.add(L + R[1:])                          # удаление
                if len(R) > 1:
                    res.add(L + R[1] + R[0] + R[2:])        # перестановка
                for c in alpha:
                    res.add(L + c + R[1:])                  # замена
            for c in alpha:
                res.add(L + c + R)                          # вставка
        return res

    def correct(self, word):
        """Исправление опечатки (Norvig по словарю wordfreq, до 2 правок) или None."""
        if len(word) < 4 or not word.isalpha():
            return None
        low = word.lower()
        if low in self.learned:
            return None
        lang = self._lang(word)
        voc = self.vocab[lang]
        if low in voc or self._zipf(low, lang) >= 2.6:      # уже слово — не трогаем
            return None
        alpha = RU_ALPHA if lang == "ru" else EN_ALPHA

        maxd = 2 if len(low) >= 5 else 1
        e1 = self._edits1(low, alpha)
        cands = {w for w in e1 if w in voc}
        if maxd == 2:
            cands |= {w2 for w in e1 for w2 in self._edits1(w, alpha) if w2 in voc}

        # ранг: меньше правок -> та же первая буква -> выше частота
        best, best_key = None, None
        for c in cands:
            z = self._zipf(c, lang)
            if z < 3.3:                                     # кандидат должен быть частым
                continue
            d = _osa_distance(low, c)
            if d > maxd:
                continue
            key = (d, 0 if c[0] == low[0] else 1, -z)
            if best_key is None or key < best_key:
                best, best_key = c, key
        if not best:
            return None
        return best[0].upper() + best[1:] if word[0].isupper() else best


# -----------------------------------------------------------------------------
# Перевод раскладки (ghbdtn <-> привет), стиль Punto Switcher
# -----------------------------------------------------------------------------
_LOW_EN = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./"
_LOW_RU = "ёйцукенгшщзхъфывапролджэячсмитьбю."
_EN2RU, _RU2EN = {}, {}
for _e, _r in zip(_LOW_EN, _LOW_RU):
    _EN2RU[_e] = _r
    _RU2EN[_r] = _e
    _eu, _ru = _e.upper(), _r.upper()
    if _eu != _e and _ru != _r:                    # заглавные только для букв
        _EN2RU[_eu] = _ru
        _RU2EN[_ru] = _eu


def switch_layout(text):
    """Меняет раскладку текста целиком: латиница<->кириллица по физическим клавишам.
    Направление — по большинству букв (чтобы запятые и пр. не ломались)."""
    cyr = sum(1 for c in text if "а" <= c.lower() <= "я" or c.lower() == "ё")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    table = _RU2EN if cyr > lat else _EN2RU
    return "".join(table.get(c, c) for c in text)
