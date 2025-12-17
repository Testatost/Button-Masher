import sys
import time
import math
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Optional, List, Tuple

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QCheckBox, QComboBox, QTabWidget, QMessageBox,
    QInputDialog, QSlider, QFileDialog, QFrame, QSizePolicy
)

from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Controller as KeyController, Key
from pynput.mouse import Controller as MouseController, Button

# -------------------------------
# Global controllers (Simulation)
# -------------------------------
kb = KeyController()
ms = MouseController()

SETTINGS_PATH = Path(__file__).with_name("button_masher_profiles.json")

# -------------------------------
# Helpers
# -------------------------------
def clamp_int(val, lo, hi, default):
    try:
        v = int(val)
    except Exception:
        return default
    return max(lo, min(hi, v))

SPECIAL_KEYS = {
    "enter": Key.enter, "space": Key.space, "tab": Key.tab,
    "shift": Key.shift, "ctrl": Key.ctrl, "alt": Key.alt,
    "esc": Key.esc, "up": Key.up, "down": Key.down,
    "left": Key.left, "right": Key.right,
    **{f"f{i}": getattr(Key, f"f{i}") for i in range(1, 13)}
}

def press_key_text(key_text: str):
    k = (key_text or "").strip().lower()
    if not k:
        return
    if k in SPECIAL_KEYS:
        kb.press(SPECIAL_KEYS[k])
        kb.release(SPECIAL_KEYS[k])
        return
    if len(k) == 1:
        kb.press(k)
        kb.release(k)

def safe_float_pair_list(obj) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    if not isinstance(obj, list):
        return out
    for it in obj:
        try:
            x, y = it
            out.append((float(x), float(y)))
        except Exception:
            pass
    return out

# -------------------------------
# Shapes
# -------------------------------
def generate_circle_points(radius=150, steps=240):
    return [(math.cos(2*math.pi*i/steps)*radius,
             math.sin(2*math.pi*i/steps)*radius) for i in range(steps)]

def generate_square_points(size=200, steps=200):
    pts = []
    h = size // 2
    corners = [(-h, -h), (h, -h), (h, h), (-h, h), (-h, -h)]
    seg = steps // 4
    for i in range(4):
        x1, y1 = corners[i]
        x2, y2 = corners[i+1]
        for s in range(seg):
            t = s / seg
            pts.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return pts

def generate_eight_points(radius=150, steps=300):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        x = radius * math.sin(t)
        y = radius * math.sin(t) * math.cos(t)
        pts.append((x, y))
    return pts

def generate_horizontal_eight_points(radius=150, steps=300):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        x = radius * math.sin(t)
        y = radius * math.sin(t) * math.cos(t) * 1.6
        pts.append((x, y))
    return pts

# -------------------------------
# Window resize controller
# -------------------------------
class WindowResizeController:
    def __init__(self, window: QWidget, base_size: QSize):
        self.window = window
        self.base_size = QSize(base_size)
        self.timer = QTimer()
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._step)

    def nudge(self):
        if not self.timer.isActive():
            self.timer.start()

    def _step(self):
        cur = self.window.size()
        dx = self.base_size.width() - cur.width()
        dy = self.base_size.height() - cur.height()

        if abs(dx) < 2 and abs(dy) < 2:
            self.window.resize(self.base_size)
            self.timer.stop()
            return

        self.window.resize(
            cur.width() + int(dx * 0.15),
            cur.height() + int(dy * 0.15)
        )

# -------------------------------
# Click positions
# -------------------------------
@dataclass
class ClickPosition:
    enabled: bool
    x: int
    y: int
    interval_ms: int  # 0 => fallback

    def to_dict(self):
        return {
            "enabled": bool(self.enabled),
            "x": int(self.x),
            "y": int(self.y),
            "interval_ms": int(self.interval_ms),
        }

    @staticmethod
    def from_dict(d: dict) -> "ClickPosition":
        return ClickPosition(
            enabled=bool(d.get("enabled", True)),
            x=clamp_int(d.get("x"), -10_000_000, 10_000_000, 0),
            y=clamp_int(d.get("y"), -10_000_000, 10_000_000, 0),
            interval_ms=clamp_int(d.get("interval_ms"), 0, 60000, 0),
        )

class ClickPositionRow(QWidget):
    def __init__(self, pos: ClickPosition, on_remove):
        super().__init__()
        self.pos = pos
        self.on_remove = on_remove

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.cb_enabled = QCheckBox()
        self.cb_enabled.setChecked(pos.enabled)
        layout.addWidget(self.cb_enabled)

        self.lbl_xy = QLabel(f"x={pos.x}, y={pos.y}")
        self.lbl_xy.setMinimumWidth(160)
        layout.addWidget(self.lbl_xy)

        layout.addWidget(QLabel("Intervall (ms):"))
        self.sp_interval = QSpinBox()
        self.sp_interval.setRange(0, 60000)
        self.sp_interval.setValue(pos.interval_ms)
        self.sp_interval.setFixedWidth(110)
        layout.addWidget(self.sp_interval)

        btn_del = QPushButton("✕")
        btn_del.setFixedWidth(28)
        layout.addWidget(btn_del)

        self.cb_enabled.stateChanged.connect(self._sync)
        self.sp_interval.valueChanged.connect(self._sync)
        btn_del.clicked.connect(lambda: self.on_remove(self))

    def _sync(self):
        self.pos.enabled = self.cb_enabled.isChecked()
        self.pos.interval_ms = self.sp_interval.value()

# -------------------------------
# Drawing widget (250x250)
# -------------------------------
class DrawingWidget(QWidget):
    def __init__(self, target_points_list: List[Tuple[float, float]]):
        super().__init__()
        self.target_points_list = target_points_list
        self.path = []
        self.drawing = False
        self.setFixedSize(250, 250)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(250, 250)

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
            self.target_points_list.clear()
            self.target_points_list.extend(self._normalize_points(self.path))

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.fillRect(self.rect(), QColor(230, 230, 230))
        qp.setPen(QPen(QColor(0, 0, 0), 2))
        if len(self.path) >= 2:
            for i in range(len(self.path) - 1):
                qp.drawLine(self.path[i], self.path[i + 1])

    def _normalize_points(self, pts):
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

# -------------------------------
# Set widget
# -------------------------------
class SetWidget(QWidget):
    def __init__(self, set_index: int, on_ui_changed):
        super().__init__()
        self.set_index = set_index
        self.on_ui_changed = on_ui_changed

        self.positions: List[ClickPosition] = []
        self.position_rows: List[ClickPositionRow] = []
        self.custom_path_points: List[Tuple[float, float]] = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Keys
        layout.addWidget(QLabel(f"Set {self.set_index} – Tasten (kommagetrennt):"))
        self.keys_input = QLineEdit()
        layout.addWidget(self.keys_input)

        row_t = QHBoxLayout()
        row_t.addWidget(QLabel("Abstand zw. Tasten (ms):"))
        self.inner_ms = QSpinBox()
        self.inner_ms.setRange(1, 60000)
        self.inner_ms.setValue(50)
        row_t.addWidget(self.inner_ms)

        row_t.addWidget(QLabel("Wiederholung nach (ms):"))
        self.repeat_ms = QSpinBox()
        self.repeat_ms.setRange(1, 60000)
        self.repeat_ms.setValue(150)
        row_t.addWidget(self.repeat_ms)
        layout.addLayout(row_t)

        # Switch after time
        self.cb_switch = QCheckBox("Wechsel zum nächsten Set nach Zeit")
        layout.addWidget(self.cb_switch)

        row_sw = QHBoxLayout()
        row_sw.addWidget(QLabel("nach"))
        self.sw_min = QSpinBox()
        self.sw_min.setRange(0, 180)
        row_sw.addWidget(self.sw_min)
        row_sw.addWidget(QLabel("min"))
        self.sw_sec = QSpinBox()
        self.sw_sec.setRange(0, 59)
        row_sw.addWidget(self.sw_sec)
        row_sw.addWidget(QLabel("sek → Set"))
        self.sw_target = QSpinBox()
        self.sw_target.setRange(1, 999)
        self.sw_target.setValue(1)
        row_sw.addWidget(self.sw_target)
        layout.addLayout(row_sw)

        # Jump back after cycle
        row_back = QHBoxLayout()
        self.cb_jump_back = QCheckBox("Nach Set-Durchlauf zurück zu Set:")
        row_back.addWidget(self.cb_jump_back)
        self.jump_back_target = QSpinBox()
        self.jump_back_target.setRange(1, 999)
        self.jump_back_target.setValue(1)
        row_back.addWidget(self.jump_back_target)
        layout.addLayout(row_back)

        self.cb_switch.stateChanged.connect(self._toggle_switch_fields)
        self.cb_jump_back.stateChanged.connect(self._toggle_jump_fields)
        self._toggle_switch_fields()
        self._toggle_jump_fields()

        layout.addWidget(self._hline())

        # Click
        self.cb_click = QCheckBox("Linksklick aktivieren")
        layout.addWidget(self.cb_click)

        row_c1 = QHBoxLayout()
        self.cb_click_interval = QCheckBox("Intervall aktivieren")
        row_c1.addWidget(self.cb_click_interval)

        row_c1.addWidget(QLabel("Globales Fallback-Intervall (ms):"))
        self.global_click_interval = QSpinBox()
        self.global_click_interval.setRange(10, 60000)
        self.global_click_interval.setValue(200)
        self.global_click_interval.setEnabled(False)
        row_c1.addWidget(self.global_click_interval)

        self.cb_positions = QCheckBox("Bis zu 8 Positionen (F7 speichern)")
        self.cb_positions.setEnabled(False)
        row_c1.addWidget(self.cb_positions)

        self.lbl_pos_count = QLabel("Positionen: 0/8")
        row_c1.addWidget(self.lbl_pos_count)

        self.btn_clear_positions = QPushButton("Positionen leeren")
        self.btn_clear_positions.setEnabled(False)
        self.btn_clear_positions.clicked.connect(self.clear_positions)
        row_c1.addWidget(self.btn_clear_positions)

        layout.addLayout(row_c1)

        self.positions_container = QVBoxLayout()
        layout.addLayout(self.positions_container)

        self.cb_click.stateChanged.connect(self._toggle_click_fields)
        self.cb_click_interval.stateChanged.connect(self._toggle_click_fields)
        self.cb_positions.stateChanged.connect(self._toggle_click_fields)
        self._toggle_click_fields()

        layout.addWidget(self._hline())

        # Movement
        layout.addWidget(QLabel("Mausbewegung:"))
        self.movement_mode = QComboBox()
        self.movement_mode.addItems([
            "Keine",
            "Kreis",
            "Quadrat",
            "8",
            "Horizontale 8",
            "Eigenes Muster"
        ])
        layout.addWidget(self.movement_mode)

        row_size = QHBoxLayout()
        row_size.addWidget(QLabel("Bewegungsgröße:"))
        self.movement_size = QSlider(Qt.Orientation.Horizontal)
        self.movement_size.setRange(10, 500)
        self.movement_size.setValue(150)
        row_size.addWidget(self.movement_size)
        layout.addLayout(row_size)

        row_speed = QHBoxLayout()
        row_speed.addWidget(QLabel("Bewegungsgeschwindigkeit:"))
        self.movement_speed = QSlider(Qt.Orientation.Horizontal)
        self.movement_speed.setRange(1, 20)  # 1 schnell, 20 langsam
        self.movement_speed.setValue(10)
        row_speed.addWidget(self.movement_speed)
        layout.addLayout(row_speed)

        self.draw_container = QVBoxLayout()
        layout.addLayout(self.draw_container)

        self.movement_mode.currentTextChanged.connect(self._update_draw_area)
        self._update_draw_area()

    def _hline(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _toggle_switch_fields(self):
        enabled = self.cb_switch.isChecked()
        self.sw_min.setEnabled(enabled)
        self.sw_sec.setEnabled(enabled)
        self.sw_target.setEnabled(enabled)

    def _toggle_jump_fields(self):
        enabled = self.cb_jump_back.isChecked()
        self.jump_back_target.setEnabled(enabled)

    def _toggle_click_fields(self):
        click_on = self.cb_click.isChecked()
        self.cb_click_interval.setEnabled(click_on)
        self.cb_positions.setEnabled(click_on)

        interval_on = click_on and self.cb_click_interval.isChecked()
        self.global_click_interval.setEnabled(interval_on)

        pos_on = click_on and self.cb_positions.isChecked()
        self.btn_clear_positions.setEnabled(pos_on)
        self._set_positions_rows_enabled(pos_on)

        self._update_pos_label()
        self.on_ui_changed()

    def _set_positions_rows_enabled(self, enabled: bool):
        for row in self.position_rows:
            row.setEnabled(enabled)

    def _update_draw_area(self):
        for i in reversed(range(self.draw_container.count())):
            w = self.draw_container.itemAt(i).widget()
            if w:
                w.deleteLater()

        if self.movement_mode.currentText() == "Eigenes Muster":
            self.draw_container.addWidget(QLabel("Eigenes Muster zeichnen (250×250):"))
            self.draw_container.addWidget(DrawingWidget(self.custom_path_points))
        self.on_ui_changed()

    def get_keys(self) -> List[str]:
        return [k.strip().lower() for k in self.keys_input.text().split(",") if k.strip()]

    # Positions
    def clear_positions(self):
        self.positions.clear()
        self._rebuild_positions_ui()
        self._update_pos_label()
        self.on_ui_changed()

    def add_position_from_mouse(self, pos_xy: Tuple[int, int]):
        if len(self.positions) >= 8:
            return
        x, y = int(pos_xy[0]), int(pos_xy[1])
        self.positions.append(ClickPosition(enabled=True, x=x, y=y, interval_ms=0))
        self._rebuild_positions_ui()
        self._update_pos_label()
        self.on_ui_changed()

    def _rebuild_positions_ui(self):
        while self.positions_container.count() > 0:
            item = self.positions_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.position_rows.clear()
        for p in self.positions:
            row = ClickPositionRow(p, on_remove=self._remove_position_row)
            self.position_rows.append(row)
            self.positions_container.addWidget(row)

        self._set_positions_rows_enabled(self.cb_click.isChecked() and self.cb_positions.isChecked())

    def _remove_position_row(self, row_widget: ClickPositionRow):
        try:
            pos_obj = row_widget.pos
            self.positions = [p for p in self.positions if p is not pos_obj]
        except Exception:
            pass
        self._rebuild_positions_ui()
        self._update_pos_label()
        self.on_ui_changed()

    def _update_pos_label(self):
        self.lbl_pos_count.setText(f"Positionen: {len(self.positions)}/8")

    # Serialization
    def to_dict(self) -> dict:
        return {
            "keys": self.keys_input.text(),
            "inner_ms": self.inner_ms.value(),
            "repeat_ms": self.repeat_ms.value(),
            "switch": {
                "enabled": self.cb_switch.isChecked(),
                "min": self.sw_min.value(),
                "sec": self.sw_sec.value(),
                "target": self.sw_target.value(),
            },
            "jump_back": {
                "enabled": self.cb_jump_back.isChecked(),
                "target": self.jump_back_target.value(),
            },
            "click": {
                "enabled": self.cb_click.isChecked(),
                "interval_enabled": self.cb_click_interval.isChecked(),
                "global_interval_ms": self.global_click_interval.value(),
                "positions_enabled": self.cb_positions.isChecked(),
                "positions": [p.to_dict() for p in self.positions],
            },
            "movement": {
                "mode": self.movement_mode.currentText(),
                "size": self.movement_size.value(),
                "speed": self.movement_speed.value(),
                "custom_path": self.custom_path_points,
            }
        }

    def from_dict(self, data: dict):
        self.keys_input.setText(data.get("keys", ""))
        self.inner_ms.setValue(clamp_int(data.get("inner_ms"), 1, 60000, 50))
        self.repeat_ms.setValue(clamp_int(data.get("repeat_ms"), 1, 60000, 150))

        sw = data.get("switch", {})
        self.cb_switch.setChecked(bool(sw.get("enabled", False)))
        self.sw_min.setValue(clamp_int(sw.get("min"), 0, 180, 0))
        self.sw_sec.setValue(clamp_int(sw.get("sec"), 0, 59, 0))
        self.sw_target.setValue(clamp_int(sw.get("target"), 1, 999, 1))
        self._toggle_switch_fields()

        jb = data.get("jump_back", {})
        self.cb_jump_back.setChecked(bool(jb.get("enabled", False)))
        self.jump_back_target.setValue(clamp_int(jb.get("target"), 1, 999, 1))
        self._toggle_jump_fields()

        ck = data.get("click", {})
        self.cb_click.setChecked(bool(ck.get("enabled", False)))
        self.cb_click_interval.setChecked(bool(ck.get("interval_enabled", False)))
        self.global_click_interval.setValue(clamp_int(ck.get("global_interval_ms"), 10, 60000, 200))
        self.cb_positions.setChecked(bool(ck.get("positions_enabled", False)))

        self.positions = []
        pos_list = ck.get("positions", [])
        if isinstance(pos_list, list):
            for it in pos_list[:8]:
                if isinstance(it, dict):
                    self.positions.append(ClickPosition.from_dict(it))
        self._rebuild_positions_ui()
        self._toggle_click_fields()

        mv = data.get("movement", {})
        mode = mv.get("mode", "Keine")
        if mode in [self.movement_mode.itemText(i) for i in range(self.movement_mode.count())]:
            self.movement_mode.setCurrentText(mode)
        self.movement_size.setValue(clamp_int(mv.get("size"), 10, 500, 150))
        self.movement_speed.setValue(clamp_int(mv.get("speed"), 1, 20, 10))
        self.custom_path_points = safe_float_pair_list(mv.get("custom_path", []))
        self._update_draw_area()

        self.on_ui_changed()

# -------------------------------
# Profile widget (sets + runner)
# -------------------------------
class ProfileWidget(QWidget):
    def __init__(self, main_window, profile_name: str):
        super().__init__()
        self.main_window = main_window
        self.profile_name = profile_name

        self.running = False
        self.run_id = 0
        self.active_set_token = 0

        self.click_thread: Optional[Thread] = None
        self.move_thread: Optional[Thread] = None
        self.runner_thread: Optional[Thread] = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.set_tabs = QTabWidget()
        self.set_tabs.setTabsClosable(True)
        self.set_tabs.tabCloseRequested.connect(self._on_close_set_tab)
        layout.addWidget(self.set_tabs)

        self._add_set_tab()  # Set 1
        self.set_tabs.addTab(QWidget(), "+")
        self.set_tabs.tabBarClicked.connect(self._on_set_tab_clicked)

        btns = QHBoxLayout()
        self.btn_start = QPushButton("Start (F5)")
        self.btn_stop = QPushButton("Stop (F6)")
        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)
        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_stop)
        layout.addLayout(btns)

    def _on_close_set_tab(self, index: int):
        # "+" Tab darf NICHT geschlossen werden
        if self.set_tabs.tabText(index) == "+":
            return

        # Mindestens ein Set muss bleiben
        if self._set_count() <= 1:
            QMessageBox.warning(
                self,
                "Nicht möglich",
                "Es muss mindestens ein Set vorhanden sein."
            )
            return

        # Set entfernen
        self.set_tabs.removeTab(index)
        self._renumber_sets()
        self._on_ui_changed()

    def _on_ui_changed(self):
        try:
            self.main_window.resize_controller.nudge()
        except Exception:
            pass

    def _plus_index(self):
        for i in range(self.set_tabs.count()):
            if self.set_tabs.tabText(i) == "+":
                return i
        return None

    def _set_count(self):
        pi = self._plus_index()
        return pi if pi is not None else self.set_tabs.count()

    def _on_set_tab_clicked(self, idx: int):
        if self.set_tabs.tabText(idx) == "+":
            self._add_set_tab()

    def _add_set_tab(self, data: Optional[dict] = None):
        insert_at = self._plus_index()
        if insert_at is None:
            insert_at = self.set_tabs.count()

        sw = SetWidget(insert_at + 1, on_ui_changed=self._on_ui_changed)
        if isinstance(data, dict):
            sw.from_dict(data)

        self.set_tabs.insertTab(insert_at, sw, f"Set {insert_at + 1}")
        self._renumber_sets()
        self.set_tabs.setCurrentIndex(insert_at)
        self._on_ui_changed()

    def _renumber_sets(self):
        for i in range(self.set_tabs.count()):
            if self.set_tabs.tabText(i) == "+":
                continue
            w = self.set_tabs.widget(i)
            if isinstance(w, SetWidget):
                w.set_index = i + 1
                self.set_tabs.setTabText(i, f"Set {i + 1}")
        plus_idx = self._plus_index()
        if plus_idx is not None:
            self.set_tabs.tabBar().setTabButton(
                plus_idx,
                self.set_tabs.tabBar().ButtonPosition.RightSide,
                None
            )

    def current_set_widget(self) -> Optional[SetWidget]:
        w = self.set_tabs.currentWidget()
        return w if isinstance(w, SetWidget) else None

    # Save/Load
    def collect_settings(self) -> dict:
        sets = []
        for i in range(self._set_count()):
            w = self.set_tabs.widget(i)
            if isinstance(w, SetWidget):
                sets.append(w.to_dict())
        return {"sets": sets}

    def apply_settings(self, data: dict):
        self.set_tabs.clear()
        sets = data.get("sets", [])
        if isinstance(sets, list) and sets:
            for sdata in sets:
                self._add_set_tab(sdata if isinstance(sdata, dict) else None)
        else:
            self._add_set_tab()

        self.set_tabs.addTab(QWidget(), "+")
        self._renumber_sets()
        self._on_ui_changed()

    # Start/Stop
    def start(self):
        if self.running:
            return
        if self._set_count() <= 0:
            QMessageBox.warning(self, "Fehler", "Kein Set vorhanden.")
            return

        self.running = True
        self.run_id += 1
        my_run_id = self.run_id

        self.runner_thread = Thread(target=self._runner_loop, args=(my_run_id,), daemon=True)
        self.runner_thread.start()

    def stop(self):
        self.running = False
        self.run_id += 1
        self.active_set_token += 1

    # Runner
    def _runner_loop(self, my_run_id: int):
        current_index = 0  # immer Set 1 starten

        while self.running and my_run_id == self.run_id:
            set_count = self._set_count()
            if set_count <= 0:
                return

            if current_index < 0 or current_index >= set_count:
                current_index = 0

            sw = self.set_tabs.widget(current_index)
            if not isinstance(sw, SetWidget):
                current_index = 0
                continue

            # activate set token
            self.active_set_token += 1
            my_set_token = self.active_set_token

            # start per-set threads
            self._start_set_threads(my_run_id, my_set_token, sw)

            set_start_time = time.time()

            # cycle loop (zyklisch)
            while self.running and my_run_id == self.run_id and my_set_token == self.active_set_token:
                # press keys in order
                for k in sw.get_keys():
                    if not (self.running and my_run_id == self.run_id and my_set_token == self.active_set_token):
                        break
                    press_key_text(k)
                    time.sleep(sw.inner_ms.value() / 1000.0)

                # click-per-cycle if click enabled but interval NOT enabled
                if sw.cb_click.isChecked() and not sw.cb_click_interval.isChecked():
                    self._single_click_cycle(sw)

                # repeat
                time.sleep(sw.repeat_ms.value() / 1000.0)

                # switch after time
                if sw.cb_switch.isChecked():
                    dur = sw.sw_min.value() * 60 + sw.sw_sec.value()
                    if dur > 0 and (time.time() - set_start_time) >= dur:
                        current_index = max(1, sw.sw_target.value()) - 1
                        self.active_set_token += 1
                        break
                    continue

                # no timed switch -> next set OR jump back
                if sw.cb_jump_back.isChecked():
                    current_index = max(1, sw.jump_back_target.value()) - 1
                else:
                    current_index += 1
                    if current_index >= set_count:
                        current_index = 0

                self.active_set_token += 1
                break

    def _single_click_cycle(self, sw: SetWidget):
        try:
            if sw.cb_positions.isChecked() and sw.positions:
                active = [p for p in sw.positions if p.enabled]
                if active:
                    for p in active:
                        ms.position = (p.x, p.y)
                        ms.click(Button.left)
                else:
                    ms.click(Button.left)
            else:
                ms.click(Button.left)
        except Exception:
            pass

    def _start_set_threads(self, my_run_id: int, my_set_token: int, sw: SetWidget):
        # CLICK INTERVAL THREAD
        if sw.cb_click.isChecked() and sw.cb_click_interval.isChecked():
            def click_loop():
                while (self.running and my_run_id == self.run_id and my_set_token == self.active_set_token and
                       sw.cb_click.isChecked() and sw.cb_click_interval.isChecked()):
                    try:
                        global_iv = sw.global_click_interval.value()

                        if sw.cb_positions.isChecked() and sw.positions:
                            active_positions = [p for p in sw.positions if p.enabled]
                            if not active_positions:
                                ms.click(Button.left)
                                time.sleep(global_iv / 1000.0)
                                continue

                            for p in active_positions:
                                if not (self.running and my_run_id == self.run_id and my_set_token == self.active_set_token):
                                    return
                                ms.position = (p.x, p.y)
                                ms.click(Button.left)
                                iv = p.interval_ms if p.interval_ms > 0 else global_iv
                                time.sleep(iv / 1000.0)
                        else:
                            ms.click(Button.left)
                            time.sleep(global_iv / 1000.0)
                    except Exception:
                        time.sleep(0.05)

            self.click_thread = Thread(target=click_loop, daemon=True)
            self.click_thread.start()

        # MOVEMENT THREAD
        mode = sw.movement_mode.currentText()
        if mode != "Keine":
            size = sw.movement_size.value()
            raw_speed = sw.movement_speed.value()
            speed = (21 - raw_speed) / 1000.0

            pts = None
            if mode == "Kreis":
                pts = generate_circle_points(radius=size)
            elif mode == "Quadrat":
                pts = generate_square_points(size=size)
            elif mode == "8":
                pts = generate_eight_points(radius=size)
            elif mode == "Horizontale 8":
                pts = generate_horizontal_eight_points(radius=size)
            elif mode == "Eigenes Muster":
                if sw.custom_path_points:
                    pts = [(x * (size / 150), y * (size / 150)) for x, y in sw.custom_path_points]

            if pts:
                base_x, base_y = ms.position

                def move_loop():
                    while self.running and my_run_id == self.run_id and my_set_token == self.active_set_token:
                        for dx, dy in pts:
                            if not (self.running and my_run_id == self.run_id and my_set_token == self.active_set_token):
                                return
                            try:
                                ms.position = (base_x + dx, base_y + dy)
                            except Exception:
                                return
                            time.sleep(speed)

                self.move_thread = Thread(target=move_loop, daemon=True)
                self.move_thread.start()

# -------------------------------
# Main window
# -------------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Button Masher Pro — Funktionsfähig (Wayland/Fedora)")
        self.setMinimumWidth(720)

        self.resize_controller = WindowResizeController(self, base_size=QSize(1020, 560))
        self.resize(self.resize_controller.base_size)

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        controls = QHBoxLayout()

        self.btn_add = QPushButton("Neues Profil")
        self.btn_add.clicked.connect(self.add_profile_dialog)
        controls.addWidget(self.btn_add)

        self.btn_rename = QPushButton("Profil umbenennen")
        self.btn_rename.clicked.connect(self.rename_current_profile)
        controls.addWidget(self.btn_rename)

        self.btn_delete = QPushButton("Profil löschen")
        self.btn_delete.clicked.connect(self.delete_current_profile)
        controls.addWidget(self.btn_delete)

        self.btn_save = QPushButton("Speichern")
        self.btn_save.clicked.connect(self.save_profiles_default)
        controls.addWidget(self.btn_save)

        self.btn_save_as = QPushButton("Speichern unter…")
        self.btn_save_as.clicked.connect(self.save_profiles_as)
        controls.addWidget(self.btn_save_as)

        self.btn_load = QPushButton("Laden…")
        self.btn_load.clicked.connect(self.load_profiles_from_file)
        controls.addWidget(self.btn_load)

        main_layout.addLayout(controls)

        self.load_profiles_default()

        # Qt Shortcuts (immer zuverlässig, wenn Fokus)
        QShortcut(QKeySequence("F5"), self, activated=self._qt_start)
        QShortcut(QKeySequence("F6"), self, activated=self._qt_stop)
        QShortcut(QKeySequence("F7"), self, activated=self._qt_add_pos)

        # Global hotkeys attempt (pynput)
        try:
            self.listener = pynput_keyboard.Listener(on_press=self.on_hotkey)
            self.listener.start()
        except Exception:
            self.listener = None

    def current_profile(self) -> Optional[ProfileWidget]:
        w = self.tabs.currentWidget()
        return w if isinstance(w, ProfileWidget) else None

    # Qt shortcut handlers
    def _qt_start(self):
        pw = self.current_profile()
        if pw:
            pw.start()

    def _qt_stop(self):
        pw = self.current_profile()
        if pw:
            pw.stop()

    def _qt_add_pos(self):
        pw = self.current_profile()
        if not pw:
            return
        sw = pw.current_set_widget()
        if not sw:
            return
        if not (sw.cb_click.isChecked() and sw.cb_positions.isChecked()):
            return
        sw.add_position_from_mouse(ms.position)
        self.resize_controller.nudge()

    # Global hotkey handler (pynput)
    def on_hotkey(self, key):
        try:
            pw = self.current_profile()
            if not pw:
                return
            if key == Key.f5:
                pw.start()
            elif key == Key.f6:
                pw.stop()
            elif key == Key.f7:
                sw = pw.current_set_widget()
                if sw and (sw.cb_click.isChecked() and sw.cb_positions.isChecked()):
                    sw.add_position_from_mouse(ms.position)
                    self.resize_controller.nudge()
        except Exception:
            pass

    # Profiles
    def add_profile(self, name: str, data: Optional[dict] = None):
        pw = ProfileWidget(self, name)
        if isinstance(data, dict):
            pw.apply_settings(data)
        idx = self.tabs.addTab(pw, name)
        self.tabs.setCurrentIndex(idx)
        self.resize_controller.nudge()

    def add_profile_dialog(self):
        name, ok = QInputDialog.getText(self, "Neues Profil", "Name:")
        if not ok:
            return
        n = (name or "").strip()
        if not n:
            n = f"Profil {self.tabs.count() + 1}"
        self.add_profile(n)

    def rename_current_profile(self):
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        old = self.tabs.tabText(idx)
        text, ok = QInputDialog.getText(self, "Profil umbenennen", "Neuer Name:", text=old)
        if ok and text.strip():
            new_name = text.strip()
            self.tabs.setTabText(idx, new_name)
            w = self.tabs.widget(idx)
            if isinstance(w, ProfileWidget):
                w.profile_name = new_name

    def delete_current_profile(self):
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        if self.tabs.count() == 1:
            QMessageBox.warning(self, "Löschen nicht möglich", "Es muss mindestens ein Profil bestehen bleiben.")
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
            self.resize_controller.nudge()

    # Save/Load
    def collect_all_profiles(self) -> dict:
        profiles = []
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, ProfileWidget):
                profiles.append({
                    "name": self.tabs.tabText(i),
                    "data": w.collect_settings()
                })
        return {"profiles": profiles}

    def apply_all_profiles(self, cfg: dict):
        self.tabs.clear()
        profiles = cfg.get("profiles", []) if isinstance(cfg, dict) else []
        if not profiles:
            self.add_profile("Profil 1")
            return
        for p in profiles:
            name = p.get("name", "Profil")
            data = p.get("data", {})
            self.add_profile(name, data if isinstance(data, dict) else None)

    def save_profiles_default(self):
        try:
            SETTINGS_PATH.write_text(json.dumps(self.collect_all_profiles(), indent=2), encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Speicherfehler", f"Profile konnten nicht gespeichert werden:\n{e}")

    def save_profiles_as(self):
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Profile speichern unter…",
            str(Path.home() / "button_masher_profiles.json"),
            "JSON-Dateien (*.json)"
        )
        if not path_str:
            return
        try:
            Path(path_str).write_text(json.dumps(self.collect_all_profiles(), indent=2), encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Speicherfehler", f"Profile konnten nicht gespeichert werden:\n{e}")

    def load_profiles_default(self):
        if not SETTINGS_PATH.exists():
            self.add_profile("Profil 1")
            return
        try:
            cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.critical(self, "Ladefehler", f"Profile konnten nicht geladen werden:\n{e}")
            self.add_profile("Profil 1")
            return
        self.apply_all_profiles(cfg if isinstance(cfg, dict) else {})
        self.resize_controller.nudge()

    def load_profiles_from_file(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Profil-Datei laden",
            str(Path.home()),
            "JSON-Dateien (*.json)"
        )
        if not path_str:
            return
        try:
            cfg = json.loads(Path(path_str).read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.critical(self, "Ladefehler", f"Die Datei konnte nicht geladen werden:\n{e}")
            return

        profiles = cfg.get("profiles", []) if isinstance(cfg, dict) else []
        if not profiles:
            QMessageBox.warning(self, "Keine Profile", "Die Datei enthält keine Profile.")
            return

        self.apply_all_profiles(cfg)
        self.resize_controller.nudge()

    def closeEvent(self, event):
        self.save_profiles_default()
        super().closeEvent(event)

# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
