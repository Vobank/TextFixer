# TextFixer

**[Русский](#русский) · [English](#english)**

> 🌐 **Язык интерфейса: русский** · правит текст на **русском и английском** · **UI: Russian; fixes RU & EN text**

Исправление текста по горячей клавише. Выделяете текст где угодно, жмёте `Ctrl+Alt+C` — орфография и запятые исправляются на месте. Работает через облачный Gemini, поэтому не грузит ПК.

Hotkey text correction. Select text anywhere, press `Ctrl+Alt+C` — spelling and commas are fixed in place. Uses cloud Gemini, so it doesn't load your PC.

---

## Русский

### Что это
Фоновая утилита: по хоткею берёт выделенный текст, исправляет и вставляет обратно. Поскольку обработка в облаке (Gemini), видеокарта и процессор не нагружаются.

### Возможности
- ⌨️ Хоткей `Ctrl+Alt+C` — исправить выделенное
- ✍️ Орфография и пунктуация (запятые)
- 🌍 Русский и английский текст
- ☁️ Облачный Gemini (не грузит ПК)
- 🙈 Окна скрыты от записи экрана

### Требования
- Windows, Python 3.12
- Ключ Gemini API (в `.env`, в репозиторий не входит)

### Запуск
- `Запуск.bat` — запустить в фоне
- `Отладка.bat` — с выводом для отладки

---

## English

### What it is
A background tool: on a hotkey it takes the selected text, fixes it and pastes it back. Processing is in the cloud (Gemini), so GPU/CPU aren't loaded.

### Features
- ⌨️ Hotkey `Ctrl+Alt+C` — fix the selection
- ✍️ Spelling and punctuation (commas)
- 🌍 Russian and English text
- ☁️ Cloud Gemini (no PC load)
- 🙈 Windows hidden from screen capture

### Requirements
- Windows, Python 3.12
- A Gemini API key (in `.env`, not included in the repo)

### Run
- `Запуск.bat` — run in the background
- `Отладка.bat` — with debug output

---

### Технологии / Tech
Python · Google Gemini API · глобальные хоткеи / global hotkeys

### ⚠️
Текст отправляется в облако Gemini для обработки. / Text is sent to the Gemini cloud for processing.
