# Button Masher Pro

Button Masher Pro ist ein plattformübergreifendes Desktop-Tool (Windows / Linux / macOS) zum automatisierten Drücken von Tastensequenzen und Mausklicks mit Profilen, Sets und globalen Hotkeys.

Entwickelt mit Python, PyQt6 und pynput.

---

## Features

- Automatisches Tastendrücken (Sequenzen, Intervalle)
- Automatisierte Mausklicks (global oder positionsbasiert)
- Profile & Sets mit JSON-Speicherung
- Mehrsprachig (DE, EN, TR, AR, RU) - (DE → Deutsch, EN → English, TR → Türkçe, AR → العربية, RU → Русский)
- Hell- / Dunkel-Theme
- Globale Hotkeys (Start / Stop / Position speichern)
- Wayland-kompatibel über XWayland

---

## Voraussetzungen

- Python >= 3.10
- Virtuelle Umgebung empfohlen

---

## Python-Abhängigkeiten

```bash
pip install PyQt6 pynput
```

---

## Betriebssystem-Abhängigkeiten (Linux)

Unter Linux werden globale Tastatur- und Maus-Events nur über X11 unterstützt.  
Unter Wayland wird automatisch XWayland (xcb) verwendet.

### Ubuntu / Debian

```bash
sudo apt install python3-dev python3-xlib xclip xdotool
```

### Fedora

```bash
sudo dnf install python3-devel python3-xlib xdotool
```

### Arch Linux

```bash
sudo pacman -S python-xlib xdotool
```

⚠️ PyCharm **nicht als Flatpak** starten, da sonst `pynput` keine globalen Events empfangen kann.

---

## Starten (Development)

```bash
python main.py
```

---

## Build (PyInstaller)

### PyInstaller installieren

```bash
pip install pyinstaller
```

### Windows (mit Icon)

```bash
pyinstaller --onefile --windowed --name ButtonMasherPro --icon icon.ico main.py
```

### Linux (mit Icon + pynput-Fix)

```bash
pyinstaller --onefile --windowed --name ButtonMasherPro --icon icon.png --hidden-import pynput.keyboard._xorg --hidden-import pynput.mouse._xorg main.py
```

### macOS (mit Icon)

```bash
pyinstaller --onefile --windowed --name ButtonMasherPro --icon icon.icns main.py
```

Nach dem Build befindet sich die ausführbare Datei im Ordner:

```text
dist/
```

---

## Konfiguration

Profile und UI-Status werden automatisch gespeichert in:

```text
button_masher_profiles.json
```

(im selben Verzeichnis wie das Programm)

---

## Hinweise

- Globale Eingaben unter Linux nur über X11 / XWayland möglich
- Keine Administrator- oder Root-Rechte erforderlich
- Nutzung auf eigene Verantwortung (z. B. in Spielen)
