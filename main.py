# -*- coding: utf-8 -*-
"""TextFixer — точка входа. Вся логика разбита по модулям в пакете textfixer/:
  config   — настройки и config.json
  gemini   — облачное исправление текста
  keyio    — буфер обмена и эмуляция клавиш
  toasts   — всплывашки, скрытые от записи экрана
  engine   — локальный словарь T9 + перевод раскладки
  t9       — контроллер режима T9 (перехват набора)
  autostart— автозапуск с Windows
  app      — сборка всего вместе
"""

from textfixer.app import main

if __name__ == "__main__":
    main()
