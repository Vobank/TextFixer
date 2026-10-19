# -*- coding: utf-8 -*-
"""TextFixer — entry point. All logic is split into modules in the textfixer/ package:
  config   — settings and config.json
  gemini   — cloud text correction
  keyio    — clipboard and key emulation
  toasts   — pop-ups hidden from screen recording
  engine   — local T9 dictionary + keyboard layout conversion
  t9       — T9 mode controller (typing interception)
  autostart— start with Windows
  app      — wires everything together
"""

from textfixer.app import main

if __name__ == "__main__":
    main()
