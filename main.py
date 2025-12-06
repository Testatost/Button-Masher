import sys
import time
import math
import json
from pathlib import Path
from threading import Thread
from pynput import mouse

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QSpinBox, QCheckBox, QComboBox, QSizePolicy, QMessageBox,
    QTabWidget, QInputDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPainter, QPen, QColor

from pynput import keyboard
from pynput.keyboard import Controller as KeyController, Key
from pynput.mouse import Controller as MouseController, Button

# -------------------------------------------------------
# GLOBAL CONTROLLERS
# -------------------------------------------------------

kb = KeyController()
mouse = MouseController()

# Speicherpfad für Profile
SETTINGS_PATH = Path(__file__).with_name("button_masher_profiles.json")


# ---------------------------------------------------------
#               SHAPE GENERATORS
# ---------------------------------------------------------

def generate_circle_points(radius=150, steps=240):
    pts = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        pts.append((math.cos(a) * radius, math.sin(a) * radius))
    return pts


def generate_triangle_points(size=200, steps=180):
    pts = []
    corners = [(0, -size), (size, size), (-size, size), (0, -size)]
    seg = steps // 3
    for i in range(3):
        x1, y1 = corners[i]
        x2, y2 = corners[i + 1]
        for s in range(seg):
            t = s / seg
            pts.append((x1 + (x2 - x1) * t), (y1 + (y2 - y1) * t))
    return pts


def generate_square_points(size=200, steps=200):
    pts = []
    h = size // 2
    corners = [(-h, -h), (h, -h), (h, h), (-h, h), (-h, -h)]
    seg = steps // 4
    for i in range(4):
        x1, y1 = corners[i]
        x2, y2 = corners[i + 1]
        for s in range(seg):
            t = s / seg
            pts.append((x1 + (x2 - x1) * t), (y1 + (y2 - y1) * t))
    return pts

def generate_eight_points(radius=150, steps=300):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        x = radius * math.sin(t)
        y = radius * math.sin(t) * math.cos(t)
        pts.append((x, y))
    return pts


# ---------------------------------------------------------
#                DRAWING WIDGET
# ---------------------------------------------------------

class DrawingWidget(QWidget):
    def __init__(self, profile_widget):
        super().__init__()
        self.profile_widget = profile_widget

        # DYNAMISCHE GRÖSSE!
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.path = []
        self.drawing = False

    def sizeHint(self):
        return QSize(300, 300)

    def mousePressEvent(self, event):
        self.drawing = True
        self.path = [event.pos()]

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.path.append(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        self.drawing = False
        if len(self.path) > 1:
            pts = self.normalize_points(self.path)
            self.profile_widget.custom_path_points = pts

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(230, 230, 230))
        pen = QPen(QColor(0, 0, 0), 2)
        qp.setPen(pen)
        if len(self.path) >= 2:
            for i in range(len(self.path) - 1):
                qp.drawLine(self.path[i], self.path[i + 1])

    def normalize_points(self, pts):
        xs = [p.x() for p in pts]
        ys = [p.y() for p in pts]
        cx = (max(xs) + min(xs)) / 2
        cy = (max(ys) + min(ys)) / 2
        scale = max(max(xs) - min(xs), max(ys) - min(ys))
        if scale <= 0:
            scale = 1
        normalized = []
        for p in pts:
            x = (p.x() - cx) / scale * 200
            y = (p.y() - cy) / scale * 200
            normalized.append((x, y))
        return normalized


# ---------------------------------------------------------
#             EINZELNES PROFIL (TAB-INHALT)
# ---------------------------------------------------------

class ProfileWidget(QWidget):
    def __init__(self, main_window, initial_name="Profil 1"):
        super().__init__()

        self.main_window = main_window
        self.profile_name = initial_name

        self.running = False
        self.run_id = 0
        self.current_run_id = None

        self.custom_path_points = []
        self.mouse_enabled = False

        self.custom_hotkeys_enabled = False
        self.start_hotkey = ""
        self.stop_hotkey = ""

        self.movement_thread = None
        self.click_thread = None
        self.key_thread = None
        self.alternate_thread = None

        self.build_ui()


    # -----------------------------------------------------
    # GUI Aufbau
    # -----------------------------------------------------

    def build_ui(self):
        layout = QVBoxLayout()

        # Set 1
        layout.addWidget(QLabel("Tasten (Set 1):"))
        self.key_input1 = QLineEdit()
        layout.addWidget(self.key_input1)

        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Intervall Set 1 (ms):"))
        self.interval1 = QSpinBox()
        self.interval1.setRange(10, 60000)
        self.interval1.setValue(150)
        h1.addWidget(self.interval1)
        layout.addLayout(h1)

        h1b = QHBoxLayout()
        h1b.addWidget(QLabel("Intervall zw. Tasten (ms):"))
        self.inner1 = QSpinBox()
        self.inner1.setRange(1, 60000)
        self.inner1.setValue(50)
        h1b.addWidget(self.inner1)
        layout.addLayout(h1b)

        # Set 2
        self.cb_set2 = QCheckBox("Set 2 aktivieren")
        self.cb_set2.stateChanged.connect(self.toggle_set2)
        layout.addWidget(self.cb_set2)

        layout.addWidget(QLabel("Tasten (Set 2):"))
        self.key_input2 = QLineEdit()
        self.key_input2.setEnabled(False)
        layout.addWidget(self.key_input2)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Intervall Set 2 (ms):"))
        self.interval2 = QSpinBox()
        self.interval2.setRange(10, 60000)
        self.interval2.setValue(300)
        self.interval2.setEnabled(False)
        h2.addWidget(self.interval2)
        layout.addLayout(h2)

        h2b = QHBoxLayout()
        h2b.addWidget(QLabel("Intervall zw. Tasten Set 2 (ms):"))
        self.inner2 = QSpinBox()
        self.inner2.setRange(1, 60000)
        self.inner2.setValue(50)
        self.inner2.setEnabled(False)
        h2b.addWidget(self.inner2)
        layout.addLayout(h2b)

        # Switch
        self.cb_switch = QCheckBox("Zwischen Set 1 & 2 wechseln")
        self.cb_switch.stateChanged.connect(self.toggle_switch)
        layout.addWidget(self.cb_switch)

        hsw = QHBoxLayout()
        hsw.addWidget(QLabel("Wechselzeit:"))
        self.sw_min = QSpinBox()
        self.sw_min.setRange(0, 180)
        self.sw_min.setEnabled(False)
        hsw.addWidget(self.sw_min)
        hsw.addWidget(QLabel("min"))

        self.sw_sec = QSpinBox()
        self.sw_sec.setRange(0, 59)
        self.sw_sec.setEnabled(False)
        hsw.addWidget(self.sw_sec)
        hsw.addWidget(QLabel("sek"))
        layout.addLayout(hsw)

        self.cb_immediate = QCheckBox("Nach Set 2 sofort zurück")
        self.cb_immediate.setEnabled(False)
        layout.addWidget(self.cb_immediate)

        # Autoklicker
        self.cb_mouse = QCheckBox("Linksklick aktivieren")
        self.cb_mouse.stateChanged.connect(self.toggle_mouse)
        layout.addWidget(self.cb_mouse)

        hm = QHBoxLayout()
        hm.addWidget(QLabel("Klick Intervall (ms):"))
        self.mouse_interval = QSpinBox()
        self.mouse_interval.setRange(10, 60000)
        self.mouse_interval.setValue(200)
        self.mouse_interval.setEnabled(False)
        hm.addWidget(self.mouse_interval)
        layout.addLayout(hm)

        # Mausbewegung
        layout.addWidget(QLabel("Mausbewegung:"))
        self.combo_movement = QComboBox()
        self.combo_movement.addItems([
            "Keine",
            "Kreis",
            "Dreieck",
            "Quadrat",
            "Horizontale 8",
            "Eigenes Muster"
        ])
        self.combo_movement.currentTextChanged.connect(self.update_drawing_area)
        layout.addWidget(self.combo_movement)

        # Größe der Mausbewegung
        hsize = QHBoxLayout()
        hsize.addWidget(QLabel("Bewegungsgröße:"))

        from PyQt6.QtWidgets import QSlider
        from PyQt6.QtCore import Qt

        self.movement_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.movement_size_slider.setRange(10, 500)
        self.movement_size_slider.setValue(150)
        self.movement_size_slider.setTickInterval(10)
        self.movement_size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        hsize.addWidget(self.movement_size_slider)

        layout.addLayout(hsize)

        # Geschwindigkeit der Mausbewegung
        hspeed = QHBoxLayout()
        hspeed.addWidget(QLabel("Bewegungsgeschwindigkeit:"))

        from PyQt6.QtWidgets import QSlider

        self.movement_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.movement_speed_slider.setRange(1, 20)  # 1 = sehr schnell, 50 = sehr langsam
        self.movement_speed_slider.setValue(10)  # Standard
        self.movement_speed_slider.setTickInterval(1)
        self.movement_speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        hspeed.addWidget(self.movement_speed_slider)

        layout.addLayout(hspeed)

        self.cb_save_pattern = QCheckBox("Eigenes Muster mit speichern")
        layout.addWidget(self.cb_save_pattern)

        self.draw_container = QVBoxLayout()
        layout.addLayout(self.draw_container)

        # Hotkeys
        self.cb_hotkeys = QCheckBox("Eigene Hotkeys verwenden")
        self.cb_hotkeys.stateChanged.connect(self.toggle_hotkeys)
        layout.addWidget(self.cb_hotkeys)

        hk1 = QHBoxLayout()
        hk1.addWidget(QLabel("Start-Hotkey:"))
        self.start_hotkey_input = QLineEdit()
        self.start_hotkey_input.setEnabled(False)
        self.start_hotkey_input.setPlaceholderText("z.B. a, 1, f5, x1, left")
        hk1.addWidget(self.start_hotkey_input)
        layout.addLayout(hk1)

        hk2 = QHBoxLayout()
        hk2.addWidget(QLabel("Stop-Hotkey:"))
        self.stop_hotkey_input = QLineEdit()
        self.stop_hotkey_input.setEnabled(False)
        self.stop_hotkey_input.setPlaceholderText("z.B. b, 2, f6, x2, right")
        hk2.addWidget(self.stop_hotkey_input)
        layout.addLayout(hk2)

        save_layout = QHBoxLayout()

        self.btn_save = QPushButton("Profil(e) speichern")
        self.btn_save.clicked.connect(self.on_save_clicked)
        save_layout.addWidget(self.btn_save)

        self.btn_load = QPushButton("Profile laden")
        self.btn_load.clicked.connect(self.on_load_clicked)
        save_layout.addWidget(self.btn_load)

        layout.addLayout(save_layout)

        self.btn_start = QPushButton("Start (F5 / Hotkey)")
        self.btn_start.clicked.connect(self.start)
        layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop (F6 / Hotkey)")
        self.btn_stop.clicked.connect(self.stop)
        layout.addWidget(self.btn_stop)

        self.start_hotkey_input.textChanged.connect(self.apply_hotkeys)
        self.stop_hotkey_input.textChanged.connect(self.apply_hotkeys)

        self.setLayout(layout)

    # GUI Toggles…
    def toggle_set2(self):
        a = self.cb_set2.isChecked()
        self.key_input2.setEnabled(a)
        self.interval2.setEnabled(a)
        self.inner2.setEnabled(a)

    def toggle_switch(self):
        a = self.cb_switch.isChecked()
        self.sw_min.setEnabled(a)
        self.sw_sec.setEnabled(a)
        self.cb_immediate.setEnabled(a)

    def toggle_mouse(self):
        checked = self.cb_mouse.isChecked()
        self.mouse_interval.setEnabled(checked)
        self.mouse_enabled = checked

        if checked and self.running and self.current_run_id is not None:
            if not self.click_thread or not self.click_thread.is_alive():
                t = Thread(target=self.mouse_click_loop, args=(self.current_run_id,
                                                               self.mouse_interval.value()), daemon=True)
                self.click_thread = t
                t.start()

    def toggle_hotkeys(self):
        self.custom_hotkeys_enabled = self.cb_hotkeys.isChecked()
        self.start_hotkey_input.setEnabled(self.custom_hotkeys_enabled)
        self.stop_hotkey_input.setEnabled(self.custom_hotkeys_enabled)
        if self.custom_hotkeys_enabled:
            self.apply_hotkeys()

    def apply_hotkeys(self):
        self.start_hotkey = self.start_hotkey_input.text().strip().lower()
        self.stop_hotkey = self.stop_hotkey_input.text().strip().lower()

    def adjust_drawing_window_height(self):
        main_win = self.main_window

        # Zeichenfeld aktiv?
        if self.combo_movement.currentText() == "Eigenes Muster":
            # Empfohlene zusätzliche Höhe
            extra_height = 150
        else:
            extra_height = -150

        # aktuelle Größe des Fensters
        current_w = main_win.width()
        current_h = main_win.height()

        # neue Höhe berechnen
        new_h = max(600, current_h + extra_height)

        main_win.resize(current_w, new_h)

    def update_drawing_area(self):
        for i in reversed(range(self.draw_container.count())):
            w = self.draw_container.itemAt(i).widget()
            if w:
                w.deleteLater()

        if self.combo_movement.currentText() == "Eigenes Muster":
            self.drawing_widget = DrawingWidget(self)
            self.draw_container.addWidget(QLabel("Zeichnen Sie Ihr Muster:"))
            self.draw_container.addWidget(self.drawing_widget)
        else:
            self.drawing_widget = None

        # Fenster dynamisch anpassen
        self.adjust_drawing_window_height()

    # ---------------- THREAD-FUNKTIONEN ----------------

    def press_keys_loop(self, my_run_id, keys, outer_interval, inner_interval):
        while self.running and my_run_id == self.run_id:
            for k in keys:
                if not self.running or my_run_id != self.run_id:
                    return
                self.press_single_key(k)
                time.sleep(inner_interval / 1000)
            time.sleep(outer_interval / 1000)

    def press_single_key(self, key):
        special = {
            "enter": Key.enter, "space": Key.space, "tab": Key.tab,
            "shift": Key.shift, "ctrl": Key.ctrl, "alt": Key.alt, "esc": Key.esc,
            "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
            **{f"f{i}": getattr(Key, f"f{i}") for i in range(1, 13)}
        }
        if key in special:
            kb.press(special[key])
            kb.release(special[key])
            return
        if len(key) == 1:
            kb.press(key)
            kb.release(key)

    def move_mouse_path(self, my_run_id, points, speed):
        # Startpunkt EINMAL speichern
        base_x, base_y = mouse.position

        while self.running and my_run_id == self.run_id:

            for dx, dy in points:
                if not self.running or my_run_id != self.run_id:
                    return

                # EXAKT relativ zum Startpunkt der Bewegung
                mouse.position = (base_x + dx, base_y + dy)
                time.sleep(speed)

            # WICHTIG: Startpunkt NICHT neu setzen!!
            # Dadurch bleibt die Form stabil an der ursprünglichen Stelle.

    def alternating_loop(self, my_run_id, keys1, outer1, inner1,
                         keys2, outer2, inner2,
                         total_seconds, immediate_back):
        while self.running and my_run_id == self.run_id:

            end = time.time() + total_seconds
            while self.running and my_run_id == self.run_id and time.time() < end:
                for k in keys1:
                    if not self.running or my_run_id != self.run_id:
                        return
                    self.press_single_key(k)
                    time.sleep(inner1 / 1000)
                time.sleep(outer1 / 1000)

            if not self.running:
                return

            if immediate_back:
                for k in keys2:
                    if not self.running or my_run_id != self.run_id:
                        return
                    self.press_single_key(k)
                    time.sleep(inner2 / 1000)
                continue

            end = time.time() + total_seconds
            while self.running and time.time() < end:
                for k in keys2:
                    if not self.running or my_run_id != self.run_id:
                        return
                    self.press_single_key(k)
                    time.sleep(inner2 / 1000)
                time.sleep(outer2 / 1000)

    # ---------------- START / STOP ----------------

    def start(self):
        if self.running:
            return

        self.running = True
        self.run_id += 1
        my_run_id = self.run_id
        self.current_run_id = my_run_id

        keys1 = [k.strip().lower() for k in self.key_input1.text().split(",") if k.strip()]
        if not keys1:
            QMessageBox.warning(self, "Fehler", "Bitte mindestens eine Taste in Set 1 eintragen!")
            self.running = False
            return

        outer1 = self.interval1.value()
        inner1 = self.inner1.value()

        # Autoklicker
        if self.cb_mouse.isChecked():
            self.mouse_enabled = True
            self.click_thread = Thread(
                target=self.mouse_click_loop,
                args=(my_run_id, self.mouse_interval.value()),
                daemon=True
            )
            self.click_thread.start()
        else:
            self.mouse_enabled = False

        shape = self.combo_movement.currentText()
        size = self.movement_size_slider.value()  # <<< Sliderwert holen
        raw_speed = self.movement_speed_slider.value()
        speed = (21 - raw_speed) / 1000

        if shape != "Keine":
            if shape == "Kreis":
                pts = generate_circle_points(radius=size)
            elif shape == "Dreieck":
                pts = generate_triangle_points(size=size)
            elif shape == "Quadrat":
                pts = generate_square_points(size=size)
            elif shape == "Horizontale 8":
                pts = generate_eight_points(radius=size)
            elif shape == "Eigenes Muster":
                if not self.custom_path_points:
                    QMessageBox.warning(self, "Fehler", "Bitte zuerst ein Muster zeichnen!")
                    self.running = False
                    return

                # Eigenes Muster skalieren
                pts = [(x * (size / 150), y * (size / 150)) for x, y in self.custom_path_points]
            else:
                pts = []

            if pts:
                self.movement_thread = Thread(
                    target=self.move_mouse_path,
                    args=(my_run_id, pts, speed),
                    daemon=True
                )
                self.movement_thread.start()

        # Alternation
        if self.cb_switch.isChecked() and self.cb_set2.isChecked():
            keys2 = [k.strip().lower() for k in self.key_input2.text().split(",") if k.strip()]
            if not keys2:
                QMessageBox.warning(self, "Fehler", "Set 2 ist aktiviert, aber leer!")
                self.running = False
                return

            outer2 = self.interval2.value()
            inner2 = self.inner2.value()
            total_seconds = self.sw_min.value() * 60 + self.sw_sec.value()
            immediate = self.cb_immediate.isChecked()

            self.alternate_thread = Thread(
                target=self.alternating_loop,
                args=(my_run_id, keys1, outer1, inner1,
                      keys2, outer2, inner2,
                      total_seconds, immediate),
                daemon=True
            )
            self.alternate_thread.start()
            return

        self.key_thread = Thread(
            target=self.press_keys_loop,
            args=(my_run_id, keys1, outer1, inner1),
            daemon=True
        )
        self.key_thread.start()

    def stop(self):
        self.running = False
        self.mouse_enabled = False
        self.run_id += 1
        print(f"[{self.profile_name}] STOP – Threads gekillt")

    # ---------------- SPEICHERN / LADEN ----------------

    def on_save_clicked(self):
        self.main_window.save_profiles()

    def on_load_clicked(self):
        self.main_window.load_profiles_from_file()

    def collect_settings(self):
        return {
            "set1": {
                "keys": self.key_input1.text(),
                "outer": self.interval1.value(),
                "inner": self.inner1.value()
            },
            "set2": {
                "enabled": self.cb_set2.isChecked(),
                "keys": self.key_input2.text(),
                "outer": self.interval2.value(),
                "inner": self.inner2.value()
            },
            "switch": {
                "enabled": self.cb_switch.isChecked(),
                "minutes": self.sw_min.value(),
                "seconds": self.sw_sec.value(),
                "immediate": self.cb_immediate.isChecked()
            },
            "mouse": {
                "enabled": self.cb_mouse.isChecked(),
                "interval": self.mouse_interval.value(),
                "movement": self.combo_movement.currentText()
            },
            "hotkeys": {
                "custom_enabled": self.cb_hotkeys.isChecked(),
                "start": self.start_hotkey_input.text(),
                "stop": self.stop_hotkey_input.text()
            },
            "pattern": {
                "save_pattern": self.cb_save_pattern.isChecked(),
                "points": self.custom_path_points if self.cb_save_pattern.isChecked() else None,
                "movement_size": self.movement_size_slider.value()
            }
        }

    def apply_settings(self, data: dict):
        # Set 1
        set1 = data.get("set1", {})
        self.key_input1.setText(set1.get("keys", ""))
        self.interval1.setValue(set1.get("outer", 150))
        self.inner1.setValue(set1.get("inner", 50))

        # Set 2
        set2 = data.get("set2", {})
        self.cb_set2.setChecked(set2.get("enabled", False))
        self.toggle_set2()
        self.key_input2.setText(set2.get("keys", ""))
        self.interval2.setValue(set2.get("outer", 300))
        self.inner2.setValue(set2.get("inner", 50))

        # Switch
        sw = data.get("switch", {})
        self.cb_switch.setChecked(sw.get("enabled", False))
        self.toggle_switch()
        self.sw_min.setValue(sw.get("minutes", 0))
        self.sw_sec.setValue(sw.get("seconds", 0))
        self.cb_immediate.setChecked(sw.get("immediate", False))

        # Mouse
        mouse_conf = data.get("mouse", {})
        self.cb_mouse.setChecked(mouse_conf.get("enabled", False))
        self.toggle_mouse()
        self.mouse_interval.setValue(mouse_conf.get("interval", 200))
        pattern = data.get("pattern", {})
        self.movement_size_slider.setValue(pattern.get("movement_size", 150))

        movement = mouse_conf.get("movement", "Keine")
        if movement in [self.combo_movement.itemText(i) for i in range(self.combo_movement.count())]:
            self.combo_movement.setCurrentText(movement)
        else:
            self.combo_movement.setCurrentText("Keine")
        self.update_drawing_area()

        # Hotkeys
        hk = data.get("hotkeys", {})
        self.cb_hotkeys.setChecked(hk.get("custom_enabled", False))
        self.toggle_hotkeys()
        self.start_hotkey_input.setText(hk.get("start", ""))
        self.stop_hotkey_input.setText(hk.get("stop", ""))

        # Pattern
        patt = data.get("pattern", {})
        save_pattern = patt.get("save_pattern", False)
        self.cb_save_pattern.setChecked(save_pattern)
        pts = patt.get("points")
        if save_pattern and isinstance(pts, list):
            try:
                self.custom_path_points = [(float(x), float(y)) for x, y in pts]
            except Exception:
                self.custom_path_points = []


# ---------------------------------------------------------
#                     MAIN WINDOW MIT TABS
# ---------------------------------------------------------

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWindowTitle("Button Masher Pro 6.1 – Multi-Profil")
        self.setMinimumWidth(600)

        self.tabs = QTabWidget()

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)

        control_layout = QHBoxLayout()
        self.btn_add_profile = QPushButton("Neues Profil")
        self.btn_add_profile.clicked.connect(self.add_profile)
        control_layout.addWidget(self.btn_add_profile)

        self.btn_rename_profile = QPushButton("Profil umbenennen")
        self.btn_rename_profile.clicked.connect(self.rename_current_profile)
        control_layout.addWidget(self.btn_rename_profile)

        self.btn_delete_profile = QPushButton("Profil löschen")
        self.btn_delete_profile.clicked.connect(self.delete_current_profile)
        control_layout.addWidget(self.btn_delete_profile)

        main_layout.addLayout(control_layout)
        self.setLayout(main_layout)

        # Profile laden oder Standard-Profil anlegen
        self.load_profiles()

        self.listener = keyboard.Listener(on_press=self.on_hotkey)
        self.listener.start()

        # globaler Mouse Hotkey Listener
        from pynput import mouse
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.mouse_listener.start()

    def on_mouse_click(self, x, y, button, pressed):
        if not pressed:
            return

        widget = self.tabs.currentWidget()
        if not isinstance(widget, ProfileWidget):
            return

        raw = str(button).lower()

        # Doppelte Präfixe entfernen: "button.button8" → "button8"
        if raw.startswith("button.button"):
            raw = raw.replace("button.button", "button")

        # Logitech M650 + Linux Mapping
        map_btn = {
            "button8": "x1",
            "button9": "x2",
            "button.xbutton1": "x1",
            "button.xbutton2": "x2",
            "button.left": "left",
            "button.right": "right",
            "button.middle": "middle"
        }

        name = map_btn.get(raw, raw.replace("button.", ""))

        print("Maus-Hotkey gedrückt:", name)

        if widget.custom_hotkeys_enabled:

            if widget.start_hotkey == name:
                print(" → Start-Hotkey erkannt!")
                widget.start()
                return

            if widget.stop_hotkey == name:
                print(" → Stop-Hotkey erkannt!")
                widget.stop()
                return

    # ---------------------------------------------------------
    # PROFIL LADEN BEIM START ODER RELOAD
    # ---------------------------------------------------------
    def load_profiles(self, force_reload=False):

        # Falls Reload: Tabs komplett entfernen
        if force_reload:
            while self.tabs.count() > 0:
                self.tabs.removeTab(0)

        # Datei prüfen
        if not SETTINGS_PATH.exists():
            if self.tabs.count() == 0:
                self.add_profile("Profil 1")
            return

        # Datei laden
        try:
            raw = SETTINGS_PATH.read_text(encoding="utf-8")
            cfg = json.loads(raw)
        except Exception as e:
            QMessageBox.critical(self, "Ladefehler",
                                 f"Profile konnten nicht geladen werden:\n{e}")
            if self.tabs.count() == 0:
                self.add_profile("Profil 1")
            return

        profiles = cfg.get("profiles", [])

        if not profiles:
            if self.tabs.count() == 0:
                self.add_profile("Profil 1")
            return

        # Profile neu erzeugen
        for p in profiles:
            name = p.get("name", "Profil")
            data = p.get("data", {})
            self.add_profile(name=name, data=data)

    # ---------------------------------------------------------
    # MANUELLES LADEN EINER JSON-DATEI
    # ---------------------------------------------------------
    def load_profiles_from_file(self):
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Profil-Datei laden",
            str(Path.home()),
            "JSON-Dateien (*.json)"
        )

        if not path:
            return  # Abbrechen

        # Datei einlesen
        try:
            raw = Path(path).read_text(encoding="utf-8")
            cfg = json.loads(raw)
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Laden",
                                 f"Die Datei konnte nicht geladen werden:\n{e}")
            return

        profiles = cfg.get("profiles", [])

        if not profiles:
            QMessageBox.warning(self, "Keine Profile",
                                "Die Datei enthält keine Profile.")
            return

        # alle Tabs löschen
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)

        # importierte Profile laden
        for p in profiles:
            name = p.get("name", "Profil")
            data = p.get("data", {})
            self.add_profile(name=name, data=data)

        QMessageBox.information(self, "Profile geladen",
                                "Profile wurden erfolgreich geladen.")

    # ---------------------------------------------------------
    # PROFILVERWALTUNG
    # ---------------------------------------------------------
    def add_profile(self, name=None, data=None):
        if isinstance(name, dict) and data is None:
            data = name
            name = None

        if not isinstance(name, str) or not name.strip():
            name = f"Profil {self.tabs.count() + 1}"

        pw = ProfileWidget(self, initial_name=name)
        if isinstance(data, dict):
            pw.apply_settings(data)

        idx = self.tabs.addTab(pw, name)
        self.tabs.setCurrentIndex(idx)

    def rename_current_profile(self):
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        old_name = self.tabs.tabText(idx)
        text, ok = QInputDialog.getText(self, "Profil umbenennen", "Neuer Name:", text=old_name)
        if ok and text.strip():
            new_name = text.strip()
            self.tabs.setTabText(idx, new_name)
            widget = self.tabs.widget(idx)
            if isinstance(widget, ProfileWidget):
                widget.profile_name = new_name

    def delete_current_profile(self):
        idx = self.tabs.currentIndex()
        if idx < 0:
            return

        if self.tabs.count() == 1:
            QMessageBox.warning(self, "Löschen nicht möglich",
                                "Es muss mindestens ein Profil bestehen bleiben.")
            return

        name = self.tabs.tabText(idx)
        reply = QMessageBox.question(
            self,
            "Profil löschen",
            f"Soll das Profil „{name}“ wirklich gelöscht werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.tabs.removeTab(idx)

    def save_profiles(self):
        profiles = []
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, ProfileWidget):
                name = self.tabs.tabText(i)
                data = widget.collect_settings()
                profiles.append({"name": name, "data": data})

        try:
            SETTINGS_PATH.write_text(json.dumps({"profiles": profiles}, indent=2),
                                     encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Speicherfehler",
                                 f"Profile konnten nicht gespeichert werden:\n{e}")

    # ---------------------------------------------------------
    # HOTKEYS
    # ---------------------------------------------------------
    def on_hotkey(self, key):
        widget = self.tabs.currentWidget()
        if not isinstance(widget, ProfileWidget):
            return

        try:
            if widget.custom_hotkeys_enabled:
                if widget.start_hotkey:
                    if isinstance(key, Key) and hasattr(Key, widget.start_hotkey):
                        if key == getattr(Key, widget.start_hotkey):
                            widget.start()
                            return

                if widget.stop_hotkey:
                    if isinstance(key, Key) and hasattr(Key, widget.stop_hotkey):
                        if key == getattr(Key, widget.stop_hotkey):
                            widget.stop()
                            return

            if key == Key.f5:
                widget.start()
            elif key == Key.f6:
                widget.stop()

        except Exception:
            pass


# ---------------------------------------------------------
#                        MAIN
# ---------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
