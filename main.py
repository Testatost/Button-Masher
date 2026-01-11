import os
import sys

# ===============================
# FORCE X11 (XWayland) FOR PYNPUT
# ===============================
if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import time
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Optional, List, Tuple
from PyQt6.QtGui import QPainter, QColor

from PyQt6.QtCore import (Qt, QSize, QTimer, QPoint, pyqtSignal, QPropertyAnimation, QEasingCurve)

try:
    from PyQt6.QtCore import pyqtProperty
except ImportError:
    from PyQt6.QtCore import Property as pyqtProperty



from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QCheckBox, QTabWidget, QMessageBox,
    QInputDialog, QFileDialog, QFrame, QDialog, QDialogButtonBox, QSlider
)

from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
from pynput.keyboard import Controller as KeyController, Key
from pynput.mouse import Controller as MouseController, Button


# ===============================
# Windows DPI Fix (WICHTIG)
# ===============================
if sys.platform.startswith("win"):
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# -------------------------------
# Global controllers (Simulation)
# -------------------------------
kb = KeyController()
ms = MouseController()

SETTINGS_PATH = Path(__file__).with_name("button_masher_profiles.json")
DEFAULT_WINDOW_SIZE = QSize(400, 400)


# -------------------------------
# Translation + Theme
# -------------------------------
LANG_DE = "de"
LANG_EN = "en"
LANG_TR = "tr"
LANG_AR = "ar"
LANG_RU = "ru"

def _tr_table():
    # Alle Texte (wirklich alles) zentral hier
    return {
        LANG_DE: {
            "name_prompt": "Name:",
            "yes": "Ja",
            "no": "Nein",
            "time_min": "Min",
            "time_sec": "Sek",
            "help_icon": "?",
            "help_tooltip": "Hilfe zu möglichen Tasten",
            "delete": "Löschen",
            "switch_each_cycle": "Nach jedem Durchlauf wechseln",
            "switch_target": "Ziel-Set:",

            "app_title": "Button Masher Pro — Funktionsfähig (Wayland/Fedora)",
            "save": "Speichern",
            "save_as": "Speichern unter…",
            "load": "Laden…",
            "settings": "Einstellungen",
            "ok": "OK",
            "cancel": "Abbrechen",
            "theme": "Design",
            "theme_light": "Hell",
            "theme_dark": "Dunkel",
            "language": "Sprache",
            "lang_ger": "Ger",
            "lang_eng": "Eng",
            "lang_tr": "Tr",
            "lang_ar": "عربي",
            "lang_ru": "Ru",
            "start": "Start",
            "stop": "Stop",

            "keys_to_press": "  zu drückende Tasten:",
            "keys_placeholder": "  Beispiel: enter,h,a,l,l,o,space,w,e,l,t,enter",
            "gap_between_keys": "  Abstand zw. Tasten (ms):",
            "repeat_after": "  Wiederholung nach (ms):",

            "switch_next_set": "Wechsel zum nächsten Set",
            "after_time": "nach Zeit",

            "min": "Minuten",
            "sec": "Sekunden zu Set",

            "jump_back": "Nach einmaligen Set-Durchlauf zu Set:",

            "click_enable": "Linksklick aktivieren",
            "click_interval_enable": "Allgemeines Intervall aktivieren",
            "ms_unit": "(ms):",
            "positions_enable": "Bis zu 8 Positionen speichern ({hotkey})",
            "positions_clear": "Positionen leeren",
            "positions_count": "Positionen: {cur}/8",
            "interval_label": "Intervall (ms):",
            "not_possible": "Nicht möglich",
            "need_one_set": "Es muss mindestens ein Set vorhanden sein.",
            "need_one_profile": "Es muss mindestens ein Profil bestehen bleiben.",
            "cannot_remove_set": "Es muss mindestens ein Set vorhanden sein.",
            "error": "Fehler",
            "no_set": "Kein Set vorhanden.",

            "rename_set_title": "Set umbenennen",
            "rename_set_prompt": "Neuer Set-Name:",
            "rename_profile_title": "Profil umbenennen",
            "rename_profile_prompt": "Neuer Profilname:",

            "delete_profile_title": "Profil löschen",
            "delete_profile_confirm": "Soll das Profil „{name}“ wirklich gelöscht werden?",

            "save_error_title": "Speicherfehler",
            "save_error_text": "Profile konnten nicht gespeichert werden:\n{err}",
            "load_error_title": "Ladefehler",
            "load_error_text": "Profile konnten nicht geladen werden:\n{err}",
            "no_profiles_title": "Keine Profile",
            "no_profiles_text": "Die Datei enthält keine Profile.",

            "load_file_title": "Profil-Datei laden",
            "save_file_title": "Profile speichern unter…",

            "files_json": "JSON-Dateien (*.json);;Alle Dateien (*)",
            "files_all_or_json": "Alle Dateien (*);;JSON-Dateien (*.json)",

            "set_prefix": "Set",
            "profile_prefix": "Profil",
            "plus_tab": "+",

            "keys_help_title": "Mögliche Tasten:",
            "keys_help_letters": "• Buchstaben:",
            "keys_help_numbers": "• Zahlen:",
            "keys_help_fn": "• Funktionstasten:",
            "keys_help_special": "• Sondertasten:",
            "keys_help_hint": "Mehrere Tasten mit Komma trennen. Keine Ganzen Wörter.",
            "keys_help_body": (
                "<b>Mögliche Tasten:</b><br><br>"
                "<b>• Buchstaben:</b><br> &nbsp;&nbsp;   a–z oder A-Z<br>"
                "<b>• Zahlen:</b><br> &nbsp;&nbsp;   0–9<br>"
                "<b>• Funktionstasten:</b><br> &nbsp;&nbsp;   f1–f12<br>"
                "<b>• Sondertasten:</b><br>"
                "&nbsp;&nbsp;   Eingabetaste (enter), Leertaste (space), Tabulator (tab), Escape (esc)<br>"
                "&nbsp;&nbsp;   Umschalt (shift), Steuerung (ctrl), Alt (alt)<br>"
                "&nbsp;&nbsp;   Pfeil hoch (up), runter (down), links (left), rechts (right)<br><br>"
                "<i>Mehrere Tasten mit Komma trennen. Keine Ganzen Wörter.</i>"
            ),
        },

        LANG_EN: {
            "name_prompt": "Name:",
            "yes": "Yes",
            "no": "No",
            "time_min": "min",
            "time_sec": "sec",
            "help_icon": "?",
            "help_tooltip": "Help about possible keys",
            "delete": "Delete",
            "switch_each_cycle": "Switch after each cycle",
            "switch_target": "Target set:",

            "app_title": "Button Masher Pro — Working (Wayland/Fedora)",
            "save": "Save",
            "save_as": "Save as…",
            "load": "Load…",
            "settings": "Settings",
            "ok": "OK",
            "cancel": "Cancel",
            "theme": "Theme",
            "theme_light": "Light",
            "theme_dark": "Dark",
            "language": "Language",
            "lang_ger": "Ger",
            "lang_eng": "Eng",
            "lang_tr": "Tr",
            "lang_ar": "عربي",
            "lang_ru": "Ru",
            "start": "Start",
            "stop": "Stop",

            "keys_to_press": "Keys to press:",
            "keys_placeholder": "Example: enter,h,e,l,l,o,space,w,o,r,l,d,enter",
            "gap_between_keys": "Delay between keys (ms):",
            "repeat_after": "Repeat after (ms):",

            "switch_next_set": "Switch to next set",
            "after_time": "after time",
            "after": "after",

            "jump_back": "After one full set cycle, jump back to set:",

            "click_enable": "Enable left click",
            "click_interval_enable": "Enable global interval",
            "ms_unit": "(ms):",
            "positions_enable": "Store up to 8 positions ({hotkey})",
            "positions_clear": "Clear positions",
            "positions_count": "Positions: {cur}/8",
            "interval_label": "Interval (ms):",
            "not_possible": "Not possible",
            "need_one_set": "At least one set must exist.",
            "need_one_profile": "At least one profile must remain.",
            "cannot_remove_set": "At least one set must exist.",
            "error": "Error",
            "no_set": "No set available.",

            "rename_set_title": "Rename set",
            "rename_set_prompt": "New set name:",
            "rename_profile_title": "Rename profile",
            "rename_profile_prompt": "New profile name:",

            "delete_profile_title": "Delete profile",
            "delete_profile_confirm": "Do you really want to delete the profile “{name}”?",

            "save_error_title": "Save error",
            "save_error_text": "Profiles could not be saved:\n{err}",
            "load_error_title": "Load error",
            "load_error_text": "Profiles could not be loaded:\n{err}",
            "no_profiles_title": "No profiles",
            "no_profiles_text": "The file contains no profiles.",

            "load_file_title": "Load profile file",
            "save_file_title": "Save profiles as…",

            "files_json": "JSON files (*.json);;All files (*)",
            "files_all_or_json": "All files (*);;JSON files (*.json)",

            "set_prefix": "Set",
            "profile_prefix": "Profile",
            "plus_tab": "+",

            "keys_help_body": (
                "<b>Possible keys:</b><br><br>"
                "<b>• Letters:</b><br> &nbsp;&nbsp;   a–z or A–Z<br>"
                "<b>• Numbers:</b><br> &nbsp;&nbsp;   0–9<br>"
                "<b>• Function keys:</b><br> &nbsp;&nbsp;   f1–f12<br>"
                "<b>• Special keys:</b><br>"
                "&nbsp;&nbsp;   Enter key (enter), Space bar (space), Tab (tab), Escape (esc)<br>"
                "&nbsp;&nbsp;   Shift (shift), Control (ctrl), Alt (alt)<br>"
                "&nbsp;&nbsp;   Arrow up (up), down (down), left (left), right (right)<br><br>"
                "<i>Separate multiple keys with commas. No whole words.</i>"
            ),
        },

        LANG_TR: {
            "name_prompt": "İsim:",
            "yes": "Evet",
            "no": "Hayır",
            "time_min": "dk",
            "time_sec": "sn",
            "help_icon": "?",
            "help_tooltip": "Olası tuşlar hakkında yardım",
            "delete": "Sil",
            "switch_each_cycle": "Her döngüden sonra değiştir",
            "switch_target": "Hedef set:",

            "app_title": "Button Masher Pro — Çalışıyor (Wayland/Fedora)",
            "save": "Kaydet",
            "save_as": "Farklı kaydet…",
            "load": "Yükle…",
            "settings": "Ayarlar",
            "ok": "Tamam",
            "cancel": "İptal",
            "theme": "Tema",
            "theme_light": "Açık",
            "theme_dark": "Koyu",
            "language": "Dil",
            "lang_ger": "Ger",
            "lang_eng": "Eng",
            "lang_tr": "Tr",
            "lang_ar": "عربي",
            "lang_ru": "Ru",
            "start": "Başlat",
            "stop": "Durdur",

            "keys_to_press": "Basılacak tuşlar:",
            "keys_placeholder": "Örnek: enter,m,e,r,h,a,b,a,space,d,ü,n,y,a,enter  (Enter=enter, Boşluk=space)",
            "gap_between_keys": "Tuşlar arası gecikme (ms):",
            "repeat_after": "Tekrar süresi (ms):",

            "switch_next_set": "Sonraki sete geç",
            "after_time": "süreye göre",
            "after": "sonra",

            "jump_back": "Bir set döngüsünden sonra şu sete dön:",

            "click_enable": "Sol tıklamayı etkinleştir",
            "click_interval_enable": "Genel aralığı etkinleştir",
            "ms_unit": "(ms):",
            "positions_enable": "En fazla 8 konum kaydet ({hotkey})",
            "positions_clear": "Konumları temizle",
            "positions_count": "Konumlar: {cur}/8",
            "interval_label": "Aralık (ms):",

            "not_possible": "Mümkün değil",
            "need_one_set": "En az bir set olmalı.",
            "need_one_profile": "En az bir profil kalmalı.",
            "cannot_remove_set": "En az bir set olmalı.",
            "error": "Hata",
            "no_set": "Set yok.",

            "rename_set_title": "Seti yeniden adlandır",
            "rename_set_prompt": "Yeni set adı:",
            "rename_profile_title": "Profili yeniden adlandır",
            "rename_profile_prompt": "Yeni profil adı:",

            "delete_profile_title": "Profili sil",
            "delete_profile_confirm": "“{name}” profili silinsin mi?",

            "save_error_title": "Kaydetme hatası",
            "save_error_text": "Profiller kaydedilemedi:\n{err}",
            "load_error_title": "Yükleme hatası",
            "load_error_text": "Profiller yüklenemedi:\n{err}",
            "no_profiles_title": "Profil yok",
            "no_profiles_text": "Dosyada profil yok.",

            "load_file_title": "Profil dosyası yükle",
            "save_file_title": "Profilleri farklı kaydet…",

            "files_json": "JSON dosyaları (*.json);;Tüm dosyalar (*)",
            "files_all_or_json": "Tüm dosyalar (*);;JSON dosyaları (*.json)",

            "set_prefix": "Set",
            "profile_prefix": "Profil",
            "plus_tab": "+",

            "keys_help_body": (
                "<b>Olası tuşlar:</b><br><br>"
                "<b>• Harfler:</b><br> &nbsp;&nbsp;   a–z veya A–Z<br>"
                "<b>• Sayılar:</b><br> &nbsp;&nbsp;   0–9<br>"
                "<b>• Fonksiyon tuşları:</b><br> &nbsp;&nbsp;   f1–f12<br>"
                "<b>• Özel tuşlar:</b><br>"
                "&nbsp;&nbsp;   Enter tuşu (enter), Boşluk (space), Tab (tab), Escape (esc)<br>"
                "&nbsp;&nbsp;   Shift (shift), Ctrl (ctrl), Alt (alt)<br>"
                "&nbsp;&nbsp;   Yukarı ok (up), aşağı (down), sol (left), sağ (right)<br><br>"
                "<i>Birden fazla tuşu virgülle ayır. Tam kelime yazma.</i>"
            ),
        },

        LANG_AR: {
            "name_prompt": "الاسم:",
            "yes": "نعم",
            "no": "لا",
            "time_min": "د",
            "time_sec": "ث",
            "help_icon": "?",
            "help_tooltip": "مساعدة حول المفاتيح الممكنة",
            "delete": "حذف",
            "switch_each_cycle": "التبديل بعد كل دورة",
            "switch_target": "المجموعة الهدف:",

            "app_title": "Button Masher Pro — يعمل (Wayland/Fedora)",
            "save": "حفظ",
            "save_as": "حفظ باسم…",
            "load": "تحميل…",
            "settings": "الإعدادات",
            "ok": "موافق",
            "cancel": "إلغاء",
            "theme": "المظهر",
            "theme_light": "فاتح",
            "theme_dark": "داكن",
            "language": "اللغة",
            "lang_ger": "Ger",
            "lang_eng": "Eng",
            "lang_tr": "Tr",
            "lang_ar": "عربي",
            "lang_ru": "Ru",
            "start": "ابدأ ",
            "stop": "إيقاف ",

            "keys_to_press": "المفاتيح المراد ضغطها:",
            "keys_placeholder": "مثال: enter,h,e,l,l,o,space,w,o,r,l,d,enter  (إدخال=enter، مسافة=space)",
            "gap_between_keys": "الزمن بين المفاتيح (ms):",
            "repeat_after": "إعادة بعد (ms):",

            "switch_next_set": "الانتقال إلى المجموعة التالية",
            "after_time": "حسب الوقت",
            "after": "بعد",

            "jump_back": "بعد دورة واحدة للمجموعة، ارجع إلى المجموعة:",

            "click_enable": "تفعيل النقر الأيسر",
            "click_interval_enable": "تفعيل الفاصل العام",
            "ms_unit": "(ms):",
            "positions_enable": "حفظ حتى 8 مواقع ({hotkey})",
            "positions_clear": "مسح المواقع",
            "positions_count": "المواقع: {cur}/8",
            "interval_label": "الفاصل (ms):",

            "not_possible": "غير ممكن",
            "need_one_set": "يجب وجود مجموعة واحدة على الأقل.",
            "need_one_profile": "يجب بقاء ملف واحد على الأقل.",
            "cannot_remove_set": "يجب وجود مجموعة واحدة على الأقل.",
            "error": "خطأ",
            "no_set": "لا توجد مجموعة.",

            "rename_set_title": "إعادة تسمية المجموعة",
            "rename_set_prompt": "اسم المجموعة الجديد:",
            "rename_profile_title": "إعادة تسمية الملف",
            "rename_profile_prompt": "اسم الملف الجديد:",

            "delete_profile_title": "حذف الملف",
            "delete_profile_confirm": "هل تريد حذف الملف “{name}”؟",

            "save_error_title": "خطأ في الحفظ",
            "save_error_text": "تعذر حفظ الملفات:\n{err}",
            "load_error_title": "خطأ في التحميل",
            "load_error_text": "تعذر تحميل الملفات:\n{err}",
            "no_profiles_title": "لا توجد ملفات",
            "no_profiles_text": "الملف لا يحتوي على ملفات شخصية.",

            "load_file_title": "تحميل ملف",
            "save_file_title": "حفظ الملفات باسم…",

            "files_json": "ملفات JSON (*.json);;كل الملفات (*)",
            "files_all_or_json": "كل الملفات (*);;ملفات JSON (*.json)",

            "set_prefix": "مجموعة",
            "profile_prefix": "ملف",
            "plus_tab": "+",

            "keys_help_body": (
                "<b>المفاتيح الممكنة:</b><br><br>"
                "<b>• حروف:</b><br> &nbsp;&nbsp;   a–z أو A–Z<br>"
                "<b>• أرقام:</b><br> &nbsp;&nbsp;   0–9<br>"
                "<b>• مفاتيح الوظائف:</b><br> &nbsp;&nbsp;   f1–f12<br>"
                "<b>• مفاتيح خاصة:</b><br>"
                "&nbsp;&nbsp;   مفتاح الإدخال (enter)، المسافة (space)، تبويب (tab)، خروج (esc)<br>"
                "&nbsp;&nbsp;   تبديل (shift)، تحكم (ctrl)، Alt (alt)<br>"
                "&nbsp;&nbsp;   سهم للأعلى (up)، للأسفل (down)، لليسار (left)، لليمين (right)<br><br>"
                "<i>افصل بين المفاتيح بفاصلة. بدون كلمات كاملة.</i>"
            ),
        },

        LANG_RU: {
            "name_prompt": "Имя:",
            "yes": "Да",
            "no": "Нет",
            "time_min": "мин",
            "time_sec": "сек",
            "help_icon": "?",
            "help_tooltip": "Справка по возможным клавишам",
            "delete": "Удалить",

            "app_title": "Button Masher Pro — Работает (Wayland/Fedora)",
            "save": "Сохранить",
            "save_as": "Сохранить как…",
            "load": "Загрузить…",
            "settings": "Настройки",
            "ok": "ОК",
            "cancel": "Отмена",
            "theme": "Тема",
            "theme_light": "Светлая",
            "theme_dark": "Тёмная",
            "language": "Язык",
            "lang_ger": "Ger",
            "lang_eng": "Eng",
            "lang_tr": "Tr",
            "lang_ar": "عربي",
            "lang_ru": "Ru",
            "start": "Старт",
            "stop": "Стоп",

            "keys_to_press": "Клавиши для нажатия:",
            "keys_placeholder": "Пример: enter,h,e,l,l,o,space,w,o,r,l,d,enter  (Ввод=enter, Пробел=space)",
            "gap_between_keys": "Пауза между клавишами (мс):",
            "repeat_after": "Повтор через (мс):",

            "switch_next_set": "Переключиться на следующий набор",
            "after_time": "по времени",
            "after": "через",

            "jump_back": "После одного цикла набора перейти к набору:",

            "click_enable": "Включить левый клик",
            "click_interval_enable": "Включить общий интервал",
            "ms_unit": "(мс):",
            "positions_enable": "Сохранить до 8 позиций ({hotkey})",
            "positions_clear": "Очистить позиции",
            "positions_count": "Позиции: {cur}/8",
            "interval_label": "Интервал (мс):",

            "not_possible": "Невозможно",
            "need_one_set": "Должен быть хотя бы один набор.",
            "need_one_profile": "Должен остаться хотя бы один профиль.",
            "cannot_remove_set": "Должен быть хотя бы один набор.",
            "error": "Ошибка",
            "no_set": "Нет набора.",

            "rename_set_title": "Переименовать набор",
            "rename_set_prompt": "Новое имя набора:",
            "rename_profile_title": "Переименовать профиль",
            "rename_profile_prompt": "Новое имя профиля:",

            "delete_profile_title": "Удалить профиль",
            "delete_profile_confirm": "Удалить профиль “{name}”?",

            "save_error_title": "Ошибка сохранения",
            "save_error_text": "Не удалось сохранить профили:\n{err}",
            "load_error_title": "Ошибка загрузки",
            "load_error_text": "Не удалось загрузить профили:\n{err}",
            "no_profiles_title": "Нет профилей",
            "no_profiles_text": "Файл не содержит профилей.",

            "load_file_title": "Загрузить файл профилей",
            "save_file_title": "Сохранить профили как…",

            "files_json": "Файлы JSON (*.json);;Все файлы (*)",
            "files_all_or_json": "Все файлы (*);;Файлы JSON (*.json)",

            "set_prefix": "Набор",
            "profile_prefix": "Профиль",
            "plus_tab": "+",

            "keys_help_body": (
                "<b>Возможные клавиши:</b><br><br>"
                "<b>• Буквы:</b><br> &nbsp;&nbsp;   a–z или A–Z<br>"
                "<b>• Цифры:</b><br> &nbsp;&nbsp;   0–9<br>"
                "<b>• Функциональные:</b><br> &nbsp;&nbsp;   f1–f12<br>"
                "<b>• Спец. клавиши:</b><br>"
                "&nbsp;&nbsp;   Клавиша Enter (enter), Пробел (space), Tab (tab), Escape (esc)<br>"
                "&nbsp;&nbsp;   Shift (shift), Control (ctrl), Alt (alt)<br>"
                "&nbsp;&nbsp;   Стрелка вверх (up), вниз (down), влево (left), вправо (right)<br><br>"
                "<i>Разделяйте клавиши запятыми. Не вводите целые слова.</i>"
            ),
        },
    }

TR = _tr_table()

def tr(lang: str, key: str, **kwargs) -> str:
    d = TR.get(lang) or TR[LANG_DE]
    s = d.get(key) or TR[LANG_DE].get(key) or key
    try:
        return s.format(**kwargs)
    except Exception:
        return s

def apply_theme(app: QApplication, theme: str):
    if theme == "dark":
        app.setStyleSheet("""
QWidget { background: #1e1f22; color: #e6e6e6; }

QLineEdit, QSpinBox, QComboBox {
    background: #2b2d31;
    color: #e6e6e6;
}

QPushButton {
    background: #3a3d44;
    border: 1px solid #4b4f57;
    border-radius: 6px;
    padding: 4px 8px;
}

QPushButton:hover { background: #454954; }
QPushButton:disabled { background: #2b2d31; color: #777; }

QCheckBox:disabled { color: #777; }
QFrame[tooltipFrame="true"] {
    background-color: rgba(255, 243, 170, 230);
    border: 1px solid #c9a500;
    border-radius: 6px;
}

QTabBar::close-button {
    border-radius: 8px;
    background: transparent;
}

QTabBar::close-button:hover {
    background: #555;
}

""")
    else:
        app.setStyleSheet("""
QWidget {
    background-color: #f5f5f5;
    color: #111;
}


QLineEdit, QSpinBox, QComboBox {
    background: #ffffff;
    color: #111111;
}

QPushButton {
    background: #efefef;
    border: 1px solid #cfcfcf;
    border-radius: 6px;
    padding: 4px 8px;
}

QPushButton:hover { background: #e6e6e6; }
QPushButton:disabled { background: #f3f3f3; color: #999; }

QCheckBox:disabled { color: #999; }
QFrame[tooltipFrame="true"] {
    background-color: rgba(255, 225, 130, 210);
    border: 1px solid #9e8b00;
    border-radius: 6px;
}
""")

class ThemeToggle(QPushButton):
    def __init__(self, checked: bool):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(52, 26)

        self._circle_x = 26 if checked else 2

        self._anim = QPropertyAnimation(self, b"circle_x", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.clicked.connect(self._animate)

    def _animate(self):
        start = self._circle_x
        end = 26 if self.isChecked() else 2
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

    @pyqtProperty(int)
    def circle_x(self):
        return self._circle_x

    @circle_x.setter
    def circle_x(self, value):
        self._circle_x = value
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = QColor("#4f46e5") if self.isChecked() else QColor("#cccccc")
        p.setBrush(bg)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 13, 13)

        p.setBrush(QColor("white"))
        p.drawEllipse(self._circle_x, 2, 22, 22)

    def get_theme(self):
        return "dark" if self.isChecked() else "light"

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
from PyQt6.QtWidgets import QSizePolicy

def make_button_big(btn: QPushButton, min_w: int = 160, min_h: int = 38, font_pt: int = 11):
    f = btn.font()
    f.setPointSize(font_pt)
    btn.setFont(f)

    btn.setMinimumSize(min_w, min_h)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

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

def move_and_left_click(x: int, y: int, settle_ms: int = 10) -> bool:
    """
    Bewegt die Maus und klickt.
    Gibt False zurück, wenn Wayland/X11 das verhindert.
    """
    try:
        ms.position = (int(x), int(y))
        time.sleep(settle_ms / 1000.0)
        ms.click(Button.left)
        return True
    except Exception as e:
        print("[Mouse ERROR]", repr(e))
        return False

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
# Settings dialog
# -------------------------------
class SettingsDialog(QDialog):
    def __init__(self, main_window, lang: str, theme: str):
        super().__init__(main_window)
        self.main_window = main_window
        self.lang = lang
        self.theme = theme

        self.setWindowTitle(tr(self.lang, "settings"))
        self.setModal(True)

        root = QVBoxLayout(self)

        # Theme row
        theme_row = QHBoxLayout()

        self.lbl_theme = QLabel(tr(self.lang, "theme"))
        theme_row.addWidget(self.lbl_theme)

        self.lbl_light = QLabel(tr(self.lang, "theme_light"))
        theme_row.addWidget(self.lbl_light)

        self.theme_toggle = ThemeToggle(theme == "dark")
        theme_row.addWidget(self.theme_toggle)

        self.lbl_dark = QLabel(tr(self.lang, "theme_dark"))
        theme_row.addWidget(self.lbl_dark)

        theme_row.addStretch()
        root.addLayout(theme_row)

        # Language row
        lang_row = QHBoxLayout()
        self.lbl_lang = QLabel(tr(self.lang, "language"))
        lang_row.addWidget(self.lbl_lang)

        self.btn_de = QPushButton(tr(self.lang, "lang_ger"))
        self.btn_en = QPushButton(tr(self.lang, "lang_eng"))
        self.btn_tr = QPushButton(tr(self.lang, "lang_tr"))
        self.btn_ar = QPushButton(tr(self.lang, "lang_ar"))
        self.btn_ru = QPushButton(tr(self.lang, "lang_ru"))

        for b in (self.btn_de, self.btn_en, self.btn_tr, self.btn_ar, self.btn_ru):
            b.setFixedSize(64, 28)

            lang_row.addWidget(b)

        lang_row.addStretch()
        root.addLayout(lang_row)

        self.btn_de.clicked.connect(lambda: self._set_lang(LANG_DE))
        self.btn_en.clicked.connect(lambda: self._set_lang(LANG_EN))
        self.btn_tr.clicked.connect(lambda: self._set_lang(LANG_TR))
        self.btn_ar.clicked.connect(lambda: self._set_lang(LANG_AR))
        self.btn_ru.clicked.connect(lambda: self._set_lang(LANG_RU))

        root.addWidget(self._hline())

        root.addWidget(self._hline())

        # Hotkeys
        hk_row = QVBoxLayout()

        self.lbl_hotkeys = QLabel("Hotkeys")
        hk_row.addWidget(self.lbl_hotkeys)

        def hk_line(label, default):
            row = QHBoxLayout()
            lbl = QLabel(label)
            edit = QLineEdit()
            edit.setPlaceholderText(default)
            edit.setFixedWidth(120)
            row.addWidget(lbl)
            row.addWidget(edit)
            row.addStretch()
            return edit, row

        self.hk_start, row1 = hk_line("Start:", "F5")
        self.hk_stop, row2 = hk_line("Stop:", "F6")
        self.hk_pos, row3 = hk_line("Position speichern:", "F7")

        hk_row.addLayout(row1)
        hk_row.addLayout(row2)
        hk_row.addLayout(row3)

        root.addLayout(hk_row)

        # Ok/Cancel
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        # Texte explizit setzen (damit wirklich überall übersetzt ist)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr(self.lang, "ok"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr(self.lang, "cancel"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._sync_active_lang_buttons()

    def _hline(self):
        line = QFrame()
        line.setFixedHeight(8)
        line.setStyleSheet("background: transparent;")

        return line

    def _set_lang(self, lang_code: str):
        self.lang = lang_code
        self.setWindowTitle(tr(self.lang, "settings"))

        self.lbl_theme.setText(tr(self.lang, "theme"))
        self.lbl_light.setText(tr(self.lang, "theme_light"))
        self.lbl_dark.setText(tr(self.lang, "theme_dark"))
        self.lbl_lang.setText(tr(self.lang, "language"))

        self.btn_de.setText(tr(self.lang, "lang_ger"))
        self.btn_en.setText(tr(self.lang, "lang_eng"))
        self.btn_tr.setText(tr(self.lang, "lang_tr"))
        self.btn_ar.setText(tr(self.lang, "lang_ar"))
        self.btn_ru.setText(tr(self.lang, "lang_ru"))

        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr(self.lang, "ok"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr(self.lang, "cancel"))

        self._sync_active_lang_buttons()

    def _sync_active_lang_buttons(self):
        # Visuelles Highlight ohne Größen zu verändern
        def mark(btn: QPushButton, active: bool):
            btn.setProperty("activeLang", active)
            if active:
                btn.setStyleSheet("font-weight: bold;")
            else:
                btn.setStyleSheet("")

        mark(self.btn_de, self.lang == LANG_DE)
        mark(self.btn_en, self.lang == LANG_EN)
        mark(self.btn_tr, self.lang == LANG_TR)
        mark(self.btn_ar, self.lang == LANG_AR)
        mark(self.btn_ru, self.lang == LANG_RU)

    def get_result(self) -> tuple[str, str]:
        return {
            "lang": self.lang,
            "theme": "dark" if self.theme_toggle.isChecked() else "light",
            "hotkeys": {
                "start": self.hk_start.text().strip() or "F5",
                "stop": self.hk_stop.text().strip() or "F6",
                "pos": self.hk_pos.text().strip() or "F7",
            }
        }



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
            interval_ms=clamp_int(d.get("interval_ms"), 0, 9999999, 0),
        )

class ClickPositionRow(QWidget):
    def __init__(self, main_window, pos: ClickPosition, on_remove):

        super().__init__()
        self.main_window = main_window
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

        self.lbl_interval = QLabel(tr(self.main_window.lang, "interval_label"))
        layout.addWidget(self.lbl_interval)

        self.sp_interval = QSpinBox()
        self.sp_interval.setRange(0, 9999999)
        self.sp_interval.setValue(pos.interval_ms)
        self.sp_interval.setFixedWidth(110)
        layout.addWidget(self.sp_interval)

        self.btn_del = QPushButton("×")
        self.btn_del.setObjectName("iconButton")
        self.btn_del.setFixedSize(28, 24)
        layout.addWidget(self.btn_del)

        self.btn_del.clicked.connect(lambda: self.on_remove(self))

        self.cb_enabled.stateChanged.connect(self._sync)
        self.sp_interval.valueChanged.connect(self._sync)

    def retranslate(self):
        lang = self.main_window.lang
        self.lbl_interval.setText(tr(lang, "interval_label"))
        self.btn_del.setToolTip(tr(lang, "delete"))

    def _sync(self):
        self.pos.enabled = self.cb_enabled.isChecked()
        self.pos.interval_ms = self.sp_interval.value()
# -------------------------------
# Set widget
# -------------------------------
class SetWidget(QWidget):
    def __init__(self, main_window, set_index: int, on_ui_changed, name: str | None = None):
        self.main_window = main_window
        self.custom_name = name
        super().__init__()
        self.set_index = set_index
        self.on_ui_changed = on_ui_changed

        self.positions: List[ClickPosition] = []
        self.position_rows: List[ClickPositionRow] = []

        self._build_ui()
        self.retranslate()

    def eventFilter(self, obj, event):
        if obj is self.keys_help:
            if event.type() == event.Type.Enter:
                pos = self.keys_help.mapToGlobal(self.keys_help.rect().bottomLeft())
                self.keys_help_popup.move(pos + QPoint(5, 5))
                self.keys_help_popup.show()

            elif event.type() == event.Type.Leave:
                self.keys_help_popup.hide()

        return super().eventFilter(obj, event)

    def _create_keys_help_popup(self):
        popup = QFrame(self, Qt.WindowType.ToolTip)
        popup.setProperty("tooltipFrame", True)
        popup.setFrameShape(QFrame.Shape.NoFrame)

        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        popup.setWindowFlags(popup.windowFlags() | Qt.WindowType.FramelessWindowHint)

        # Optik wird über Theme-Stylesheet geregelt; padding hier:
        popup.setStyleSheet("""
            QLabel { padding: 6px; }
        """)

        self.lbl_help_popup = QLabel("", popup)
        self.lbl_help_popup.setTextFormat(Qt.TextFormat.RichText)

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.lbl_help_popup)

        popup.adjustSize()
        popup.hide()
        return popup

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        # Keys
        row_keys_label = QHBoxLayout()

        self.lbl_keys = QLabel()
        row_keys_label.addWidget(self.lbl_keys)

        self.keys_help = QLabel(tr(self.main_window.lang, "help_icon"))
        self.keys_help.setToolTip(tr(self.main_window.lang, "help_tooltip"))
        self.keys_help.setStyleSheet("""
        QLabel {
            background-color: #b0b0b0;
            color: #111;
            border: 1px solid #888;
            border-radius: 7px;
            padding: 1px 2px;
            font-weight: bold;
        }
        """)

        self.keys_help.setCursor(Qt.CursorShape.PointingHandCursor)

        row_keys_label.addWidget(self.keys_help)
        row_keys_label.addStretch()

        layout.addLayout(row_keys_label)

        self.keys_input = QLineEdit()
        layout.addWidget(self.keys_input)

        row_t = QHBoxLayout()
        self.lbl_inner = QLabel("")
        row_t.addWidget(self.lbl_inner)

        self.inner_ms = QSpinBox()
        self.inner_ms.setRange(1, 9999999)
        self.inner_ms.setValue(150)
        row_t.addWidget(self.inner_ms)

        self.lbl_repeat = QLabel("")
        row_t.addWidget(self.lbl_repeat)

        self.repeat_ms = QSpinBox()
        self.repeat_ms.setRange(1, 9999999)
        self.repeat_ms.setValue(150)
        row_t.addWidget(self.repeat_ms)
        layout.addLayout(row_t)

        # Jump back after one full cycle
        row_jump = QHBoxLayout()

        self.cb_jump_back = QCheckBox("")
        row_jump.addWidget(self.cb_jump_back)

        self.jump_back_target = QSpinBox()
        self.jump_back_target.setRange(1, 999)
        self.jump_back_target.setValue(1)
        self.jump_back_target.setFixedWidth(35)
        row_jump.addWidget(self.jump_back_target)

        self.cb_jump_back.stateChanged.connect(self._toggle_jump_fields)
        self._toggle_jump_fields()

        row_jump.addStretch()
        layout.addLayout(row_jump)

        # Switch to next set after time
        row_switch = QHBoxLayout()

        self.cb_switch = QCheckBox("")
        row_switch.addWidget(self.cb_switch)

        # Ziel-Set DIREKT nach "Set"
        self.sw_target = QSpinBox()
        self.sw_target.setRange(1, 999)
        self.sw_target.setValue(1)
        self.sw_target.setFixedWidth(35)
        row_switch.addWidget(self.sw_target)

        # "nach Zeit"
        self.lbl_after_time = QLabel("")
        row_switch.addWidget(self.lbl_after_time)

        # "nach"
        self.lbl_after = QLabel("")
        row_switch.addWidget(self.lbl_after)

        self.sw_min = QSpinBox()
        self.sw_min.setRange(0, 180)
        self.sw_min.setFixedWidth(35)
        row_switch.addWidget(self.sw_min)

        self.lbl_min = QLabel("")
        row_switch.addWidget(self.lbl_min)

        self.sw_sec = QSpinBox()
        self.sw_sec.setRange(0, 59)
        self.sw_sec.setFixedWidth(35)
        row_switch.addWidget(self.sw_sec)

        self.lbl_sec_to_set = QLabel("")
        row_switch.addWidget(self.lbl_sec_to_set)

        row_switch.addStretch()
        layout.addLayout(row_switch)

        # Trennlinie vor Klick-Bereich
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #888;")
        layout.addWidget(line)

        # Click
        self.cb_click = QCheckBox()
        layout.addWidget(self.cb_click)

        # Row 1: interval
        row_c1 = QHBoxLayout()
        self.cb_click_interval = QCheckBox("")
        row_c1.addWidget(self.cb_click_interval)

        self.lbl_ms = QLabel("")
        row_c1.addWidget(self.lbl_ms)

        self.global_click_interval = QSpinBox()
        self.global_click_interval.setRange(10, 9999999)
        self.global_click_interval.setValue(200)
        self.global_click_interval.setEnabled(False)
        row_c1.addWidget(self.global_click_interval)

        layout.addLayout(row_c1)

        # Row 2: positions
        row_c2 = QHBoxLayout()
        self.cb_positions = QCheckBox("")
        self.cb_positions.setEnabled(False)
        row_c2.addWidget(self.cb_positions)

        self.lbl_pos_count = QLabel("")
        row_c2.addWidget(self.lbl_pos_count)

        self.btn_clear_positions = QPushButton("")
        self.btn_clear_positions.setEnabled(False)
        self.btn_clear_positions.clicked.connect(self.clear_positions)
        row_c2.addWidget(self.btn_clear_positions)

        layout.addLayout(row_c2)

        self.positions_container = QVBoxLayout()
        layout.addLayout(self.positions_container)

        self.cb_click.stateChanged.connect(self._toggle_click_fields)
        self.cb_click_interval.stateChanged.connect(self._toggle_click_fields)
        self.cb_positions.stateChanged.connect(self._toggle_click_fields)
        self._toggle_click_fields()

        self.keys_help_popup = self._create_keys_help_popup()
        self.keys_help.installEventFilter(self)

        layout.addWidget(self._hline())

    def retranslate(self):
        lang = self.main_window.lang
        self.lbl_keys.setText(tr(lang, "keys_to_press"))
        self.keys_input.setPlaceholderText(tr(lang, "keys_placeholder"))

        self.lbl_inner.setText(tr(lang, "gap_between_keys"))
        self.lbl_repeat.setText(tr(lang, "repeat_after"))

        self.cb_switch.setText(tr(lang, "switch_next_set"))
        self.lbl_after_time.setText(tr(lang, "after_time"))
        self.lbl_after.setText(tr(lang, "after"))
        self.lbl_min.setText(tr(lang, "time_min"))
        self.lbl_sec_to_set.setText(tr(lang, "time_sec"))

        self.cb_jump_back.setText(tr(lang, "jump_back"))

        self.cb_click.setText(tr(lang, "click_enable"))
        self.cb_click_interval.setText(tr(lang, "click_interval_enable"))
        self.lbl_ms.setText(tr(lang, "ms_unit"))
        hk = self.main_window.hotkeys
        self.cb_positions.setText(
            tr(lang, "positions_enable", hotkey=hk["pos"])
        )
        self.btn_clear_positions.setText(tr(lang, "positions_clear"))

        self._update_pos_label()

        # Help popup
        self.lbl_help_popup.setText(tr(lang, "keys_help_body"))
        self.keys_help_popup.adjustSize()

        # Rows
        for r in self.position_rows:
            r.retranslate()

        # 🔥 WICHTIG: Qt zwingen, neu zu layouten
        self.updateGeometry()
        if self.layout():
            self.layout().activate()

    def _hline(self):
        line = QFrame()
        line.setFixedHeight(8)
        line.setStyleSheet("background: transparent;")
        return line

    def _toggle_switch_fields(self):
        enabled = self.cb_switch.isChecked()
        self.sw_target.setEnabled(enabled)
        self.sw_min.setEnabled(enabled)
        self.sw_sec.setEnabled(enabled)

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
            row = ClickPositionRow(self.main_window, p, on_remove=self._remove_position_row)
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
        self.lbl_pos_count.setText(tr(self.main_window.lang, "positions_count", cur=len(self.positions)))

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
            }
        }

    def from_dict(self, data: dict):
        self.keys_input.setText(data.get("keys", ""))
        self.inner_ms.setValue(clamp_int(data.get("inner_ms"), 1, 9999999, 50))
        self.repeat_ms.setValue(clamp_int(data.get("repeat_ms"), 1, 9999999, 150))

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
        self.global_click_interval.setValue(clamp_int(ck.get("global_interval_ms"), 10, 9999999, 200))
        self.cb_positions.setChecked(bool(ck.get("positions_enabled", False)))

        self.positions = []
        pos_list = ck.get("positions", [])
        if isinstance(pos_list, list):
            for it in pos_list[:8]:
                if isinstance(it, dict):
                    self.positions.append(ClickPosition.from_dict(it))
        self._rebuild_positions_ui()
        self._toggle_click_fields()

        self.retranslate()
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
        self.runner_thread: Optional[Thread] = None

        self._build_ui()
        self.retranslate()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(6, 6, 6, 6)

        self.set_tabs = QTabWidget()
        self.set_tabs.setTabsClosable(True)
        self.set_tabs.tabCloseRequested.connect(self._on_close_set_tab)
        layout.addWidget(self.set_tabs)

        self._add_set_tab()  # Set 1
        self.set_tabs.addTab(QWidget(), tr(self.main_window.lang, "plus_tab"))
        self.set_tabs.tabBarClicked.connect(self._on_set_tab_clicked)
        self.set_tabs.tabBarDoubleClicked.connect(self._on_set_tab_double_clicked)

        from PyQt6.QtWidgets import QSizePolicy

        self.btn_start = QPushButton("")
        self.btn_stop = QPushButton("")

        make_button_big(self.btn_start, min_w=180, min_h=25, font_pt=12)
        make_button_big(self.btn_stop, min_w=180, min_h=25, font_pt=12)

        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)

        btns = QHBoxLayout()
        btns.setSpacing(12)

        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_stop)

        layout.addLayout(btns)

    def retranslate(self):
        lang = self.main_window.lang
        hk = self.main_window.hotkeys

        self.btn_start.setText(f"{tr(lang, 'start')} ({hk['start']})")
        self.btn_stop.setText(f"{tr(lang, 'stop')} ({hk['stop']})")

        # "+" Tab
        pi = self._plus_index()
        if pi is not None:
            self.set_tabs.setTabText(pi, tr(lang, "plus_tab"))

        # Sets retranslate
        for i in range(self._set_count()):
            w = self.set_tabs.widget(i)
            if isinstance(w, SetWidget):
                w.retranslate()

        self._refresh_default_set_titles()

    def _refresh_default_set_titles(self):
        lang = self.main_window.lang


        prefixes = [
            TR[LANG_DE].get("set_prefix", "Set"),
            TR[LANG_EN].get("set_prefix", "Set"),
            TR[LANG_TR].get("set_prefix", "Set"),
            TR[LANG_AR].get("set_prefix", "مجموعة"),
            TR[LANG_RU].get("set_prefix", "Набор"),
            "Set"
        ]
        for i in range(self._set_count()):
            title = self.set_tabs.tabText(i)
            # wenn es ein Standardname ist: "<prefix> <nummer>"
            for p in prefixes:
                if title.strip().startswith(p + " "):
                    # Nummer extrahieren
                    tail = title.strip()[len(p) + 1:]
                    if tail.isdigit():
                        self.set_tabs.setTabText(i, f"{tr(lang, 'set_prefix')} {tail}")
                    break

    def _on_set_tab_double_clicked(self, index):
        if index < 0:
            return

        # "+" darf nicht umbenannt werden
        if self.set_tabs.tabText(index) == tr(self.main_window.lang, "plus_tab"):
            return

        old_name = self.set_tabs.tabText(index)

        new_name, ok = QInputDialog.getText(
            self,
            tr(self.main_window.lang, "rename_set_title"),
            tr(self.main_window.lang, "rename_set_prompt"),
            text=old_name
        )

        if ok and new_name.strip():
            new_name = new_name.strip()
            self.set_tabs.setTabText(index, new_name)
            w = self.set_tabs.widget(index)
            if isinstance(w, SetWidget):
                w.custom_name = new_name

    def _on_close_set_tab(self, index: int):
        # "+" Tab darf NICHT geschlossen werden
        if self.set_tabs.tabText(index) == tr(self.main_window.lang, "plus_tab"):
            return

        # Mindestens ein Set muss bleiben
        if self._set_count() <= 1:
            QMessageBox.warning(
                self,
                tr(self.main_window.lang, "not_possible"),
                tr(self.main_window.lang, "cannot_remove_set")
            )
            return

        # Ziel-Index bestimmen
        new_index = index
        if index >= self.set_tabs.count() - 1:
            new_index = index - 1

        # Set entfernen
        self.set_tabs.removeTab(index)

        # "+"-Tab überspringen
        if new_index >= 0 and self.set_tabs.tabText(new_index) == tr(self.main_window.lang, "plus_tab"):
            new_index -= 1

        if new_index >= 0:
            self.set_tabs.setCurrentIndex(new_index)

        self._renumber_sets()
        self._on_ui_changed()

    def _plus_index(self):
        for i in range(self.set_tabs.count()):
            if self.set_tabs.tabText(i) == tr(self.main_window.lang, "plus_tab") or self.set_tabs.tabText(i) == "+":
                return i
        return None

    def _set_count(self):
        pi = self._plus_index()
        return pi if pi is not None else self.set_tabs.count()

    def _on_set_tab_clicked(self, idx: int):
        if self.set_tabs.tabText(idx) == tr(self.main_window.lang, "plus_tab") or self.set_tabs.tabText(idx) == "+":
            self._add_set_tab_auto()

    def _on_ui_changed(self):
        # nur Layout refreshen, kein resize controller
        self.main_window.updateGeometry()
        if self.main_window.layout():
            self.main_window.layout().activate()

    def _add_set_tab(self, data: Optional[dict] = None):
        insert_at = self._plus_index()
        if insert_at is None:
            insert_at = self.set_tabs.count()

        default_name = f"{tr(self.main_window.lang, 'set_prefix')} {insert_at + 1}"
        sw = SetWidget(
            self.main_window,
            insert_at + 1,
            on_ui_changed=self._on_ui_changed,
            name=default_name
        )
        if isinstance(data, dict):
            sw.from_dict(data)

        self.set_tabs.insertTab(insert_at, sw, default_name)

        self._renumber_sets()
        self.set_tabs.setCurrentIndex(insert_at)
        self._on_ui_changed()
    def _add_set_tab_auto(self):
        prefix = tr(self.main_window.lang, "set_prefix")

        used_numbers = set()

        # vorhandene Set-Tabs prüfen
        for i in range(self._set_count()):
            title = self.set_tabs.tabText(i)

            if title.startswith(prefix + " "):
                tail = title[len(prefix) + 1:].strip()
                if tail.isdigit():
                    used_numbers.add(int(tail))

        # kleinste freie Zahl suchen
        n = 1
        while n in used_numbers:
            n += 1

        name = f"{prefix} {n}"
        self._add_set_tab()
        self.set_tabs.setTabText(self.set_tabs.currentIndex(), name)

    def _renumber_sets(self):
        for i in range(self.set_tabs.count()):
            if self.set_tabs.tabText(i) == tr(self.main_window.lang, "plus_tab") or self.set_tabs.tabText(i) == "+":
                continue
            w = self.set_tabs.widget(i)

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

        self.set_tabs.addTab(QWidget(), tr(self.main_window.lang, "plus_tab"))
        self._renumber_sets()
        self.retranslate()
        self._on_ui_changed()

    # Start/Stop
    def start(self):
        if self.running:
            return
        if self._set_count() <= 0:
            QMessageBox.warning(self, tr(self.main_window.lang, "error"), tr(self.main_window.lang, "no_set"))
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
            if isinstance(sw, QFrame):
                sw = sw.layout().itemAt(0).widget()
            if not isinstance(sw, SetWidget):
                current_index = 0
                continue

            # wenn keine Keys vorhanden, trotzdem nicht blockieren
            keys = sw.get_keys()
            if not keys:
                time.sleep(0.01)

            # activate set token
            self.active_set_token += 1
            my_set_token = self.active_set_token

            # start per-set threads (Intervall-Klicks laufen hier!)
            self._start_set_threads(my_run_id, my_set_token, sw)

            # ✅ Positionen GENAU EINMAL pro Set
            # ❗ NUR wenn:
            #   - Linksklick AN
            #   - Intervall AUS
            #   - Positionen AN
            if (
                    sw.cb_click.isChecked()
                    and not sw.cb_click_interval.isChecked()
                    and sw.cb_positions.isChecked()
                    and sw.positions
            ):
                self._single_click_cycle(sw)

            set_start_time = time.time()

            # cycle loop (zyklisch)
            while (
                    self.running
                    and my_run_id == self.run_id
                    and my_set_token == self.active_set_token
            ):
                # press keys in order
                for k in sw.get_keys():
                    if not (
                            self.running
                            and my_run_id == self.run_id
                            and my_set_token == self.active_set_token
                    ):
                        break
                    press_key_text(k)
                    time.sleep(sw.inner_ms.value() / 1000.0)

                # repeat pause zwischen Zyklen (WICHTIG!)
                time.sleep(sw.repeat_ms.value() / 1000.0)

                # =====================================================
                # SET-WECHSEL NACH EINEM VOLLSTÄNDIGEN DURCHLAUF
                # =====================================================

                # 1️⃣ Jump-Back hat PRIORITÄT
                if sw.cb_jump_back.isChecked():
                    current_index = max(1, sw.jump_back_target.value()) - 1
                    self.active_set_token += 1
                    break

                # 2️⃣ Switch to target set (nach Zeit ODER sofort)
                if sw.cb_switch.isChecked():
                    dur = sw.sw_min.value() * 60 + sw.sw_sec.value()

                    # Zeit = 0  → sofort nach einem Durchlauf
                    # Zeit > 0  → nur wenn Zeit erreicht
                    if dur == 0 or (time.time() - set_start_time) >= dur:
                        current_index = max(1, sw.sw_target.value()) - 1
                        self.active_set_token += 1
                        break

    def _single_click_cycle(self, sw: SetWidget):
        try:
            if sw.cb_positions.isChecked() and sw.positions:
                active = [p for p in sw.positions if p.enabled]
                if active:
                    for p in active:
                        move_and_left_click(p.x, p.y, settle_ms=10)
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
                while (
                        self.running
                        and my_run_id == self.run_id
                        and my_set_token == self.active_set_token
                        and sw is self.current_set_widget()  # 🔥 DAS IST DER FIX
                        and sw.cb_click.isChecked()
                        and sw.cb_click_interval.isChecked()):
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
                                move_and_left_click(p.x, p.y, settle_ms=10)
                                iv = p.interval_ms if p.interval_ms > 0 else global_iv
                                time.sleep(iv / 1000.0)
                        else:
                            ms.click(Button.left)
                            time.sleep(global_iv / 1000.0)
                    except Exception:
                        time.sleep(0.05)

            self.click_thread = Thread(target=click_loop, daemon=True)
            self.click_thread.start()
# -------------------------------
# Main window
# -------------------------------
class MainWindow(QWidget):
    mouse_pos_signal = pyqtSignal(int, int)
    def __init__(self):
        super().__init__()

        self._ltr_fixed_size = QSize(DEFAULT_WINDOW_SIZE)

        # 🔒 WICHTIG: sofort initialisieren
        self._last_ltr_size = QSize(DEFAULT_WINDOW_SIZE)

        self._startup_size = QSize(DEFAULT_WINDOW_SIZE)
        self._last_used_path = SETTINGS_PATH


        # UI State
        self.lang = LANG_DE
        self.theme = "light"

        self.hotkeys = {
            "start": "F5",
            "stop": "F6",
            "pos": "F7",
        }
        self._awaiting_click_position = False
        self.resize(DEFAULT_WINDOW_SIZE)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 0)
        main_layout.setSpacing(1)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_close_profile_tab)
        self.tabs.tabBarClicked.connect(self._on_profile_tab_clicked)
        self.tabs.tabBarDoubleClicked.connect(self._on_profile_tab_double_clicked)
        main_layout.addWidget(self.tabs)

        controls = QHBoxLayout()

        controls.setSpacing(5)
        controls.setContentsMargins(6, 6, 6, 6)

        self.btn_save = QPushButton("")
        self.btn_save.setObjectName("badge")
        self.btn_save.clicked.connect(self.save_profiles_default)
        controls.addWidget(self.btn_save)

        self.btn_save_as = QPushButton("")
        self.btn_save_as.setObjectName("badge")
        self.btn_save_as.clicked.connect(self.save_profiles_as)
        controls.addWidget(self.btn_save_as)

        self.btn_load = QPushButton("")
        self.btn_load.setObjectName("badge")
        self.btn_load.clicked.connect(self.load_profiles_from_file)
        controls.addWidget(self.btn_load)

        make_button_big(self.btn_save, min_w=150, min_h=35, font_pt=11)
        make_button_big(self.btn_save_as, min_w=150, min_h=35, font_pt=11)
        make_button_big(self.btn_load, min_w=150, min_h=35, font_pt=11)

        # Zahnrad Button (Settings)
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setProperty("class", "badge")
        self.btn_settings.setFixedSize(32, 35)
        self.btn_settings.setStyleSheet("font-size: 30px;")

        self.btn_settings.setFixedWidth(40)  # Größe bewusst fix: vorhandene Buttons bleiben
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        controls.addWidget(self.btn_settings)

        controls.addStretch()
        main_layout.addLayout(controls)

        self.load_profiles_default()

        # Qt Shortcuts (immer zuverlässig, wenn Fokus)
        self._qt_shortcuts = {}
        self._rebuild_qt_shortcuts()


        # Global hotkeys attempt (pynput)
        try:
            self.listener = pynput_keyboard.Listener(on_press=self.on_hotkey)
            self.listener.start()
        except Exception as e:
            print("Global Hotkeys deaktiviert:", e)
            self.listener = None

        self.mouse_pos_signal.connect(self._on_mouse_pos_signal)

        # ✅ Globaler Maus-Listener: fängt den nächsten echten Linksklick ab
        try:
            self.mouse_listener = pynput_mouse.Listener(on_click=self._on_global_mouse_click)
            self.mouse_listener.start()
        except Exception as e:
            print("Global Mouse Listener deaktiviert:", e)
            self.mouse_listener = None

        # Apply initial UI
        apply_theme(QApplication.instance(), self.theme)
        self.retranslate_all()

        self.updateGeometry()
        if self.layout():
            self.layout().activate()

        self._apply_direction()
        self.setWindowTitle(tr(self.lang, "app_title"))

    def _on_global_mouse_click(self, x, y, button, pressed):
        if not pressed or button != Button.left:
            return

        # NUR Signal senden – KEINE GUI-Logik hier!
        self.mouse_pos_signal.emit(int(x), int(y))

    def _on_mouse_pos_signal(self, x: int, y: int):
        if not self._awaiting_click_position:
            return

        self._awaiting_click_position = False
        print(f"✅ Position gespeichert: x={x}, y={y}")

        self._ui_add_position((x, y))

    def _rebuild_qt_shortcuts(self):
        # alte entfernen
        for sc in self._qt_shortcuts.values():
            sc.setParent(None)

        self._qt_shortcuts.clear()

        self._qt_shortcuts["start"] = QShortcut(
            QKeySequence(self.hotkeys["start"]), self, activated=self._qt_start)
        self._qt_shortcuts["stop"] = QShortcut(
            QKeySequence(self.hotkeys["stop"]), self, activated=self._qt_stop
        )
        self._qt_shortcuts["pos"] = QShortcut(
            QKeySequence(self.hotkeys["pos"]), self, activated=self._qt_add_pos
        )

    def _apply_direction(self):
        is_rtl = (self.lang == LANG_AR)

        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if is_rtl
            else Qt.LayoutDirection.LeftToRight
        )

        if not is_rtl:
            QTimer.singleShot(0, self._restore_ltr_size)

    def _restore_ltr_size(self):
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)

        # letzte echte LTR-Größe wiederherstellen
        self.resize(self._last_ltr_size)

        # Layout wirklich neu berechnen lassen
        self.updateGeometry()
        if self.layout():
            self.layout().activate()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self, self.lang, self.theme)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            self.lang = result["lang"]
            self.theme = result["theme"]
            self.hotkeys = result["hotkeys"]

            self._rebuild_qt_shortcuts()

            apply_theme(QApplication.instance(), self.theme)
            self._apply_direction()
            self.retranslate_all()
            self.updateGeometry()
            if self.layout():
                self.layout().activate()

    def retranslate_all(self):
        self.setWindowTitle(tr(self.lang, "app_title"))

        self.btn_save.setText(tr(self.lang, "save"))
        self.btn_save_as.setText(tr(self.lang, "save_as"))
        self.btn_load.setText(tr(self.lang, "load"))
        self.btn_settings.setToolTip(tr(self.lang, "settings"))

        # "+" Tab
        self._ensure_profile_plus_tab()

        # Alle Profile / Sets retranslate
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, ProfileWidget):
                w.retranslate()

        # Default-Profilnamen an Sprache anpassen, wenn sie Standard sind
        self._refresh_default_profile_titles()

    def _refresh_default_profile_titles(self):
        lang = self.lang
        prefixes = [
            TR[LANG_DE].get("profile_prefix", "Profil"),
            TR[LANG_EN].get("profile_prefix", "Profile"),
            TR[LANG_TR].get("profile_prefix", "Profil"),
            TR[LANG_AR].get("profile_prefix", "ملف"),
            TR[LANG_RU].get("profile_prefix", "Профиль"),
            "Profil",
            "Profile"
        ]
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == tr(lang, "plus_tab") or self.tabs.tabText(i) == "+":
                continue
            title = self.tabs.tabText(i)
            for p in prefixes:
                if title.strip().startswith(p + " "):
                    tail = title.strip()[len(p) + 1:]
                    if tail.isdigit():
                        self.tabs.setTabText(i, f"{tr(lang, 'profile_prefix')} {tail}")
                    break

        plus_idx = self._profile_plus_index()
        if plus_idx is not None:
            self.tabs.setTabText(plus_idx, tr(lang, "plus_tab"))

    def _on_profile_tab_double_clicked(self, index):
        if index < 0:
            return
        if self.tabs.tabText(index) == tr(self.lang, "plus_tab") or self.tabs.tabText(index) == "+":
            return

        old_name = self.tabs.tabText(index)

        new_name, ok = QInputDialog.getText(
            self,
            tr(self.lang, "rename_profile_title"),
            tr(self.lang, "rename_profile_prompt"),
            text=old_name
        )

        if ok and new_name.strip():
            self.tabs.setTabText(index, new_name.strip())
            w = self.tabs.widget(index)
            if isinstance(w, ProfileWidget):
                w.profile_name = new_name.strip()

    def current_profile(self) -> Optional[ProfileWidget]:
        w = self.tabs.currentWidget()
        return w if isinstance(w, ProfileWidget) else None

    def _ui_add_position(self, pos):
        pw = self.current_profile()
        if not pw:
            return
        sw = pw.current_set_widget()
        if not sw:
            return
        if sw.cb_click.isChecked() and sw.cb_positions.isChecked():
            sw.add_position_from_mouse(pos)

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

        # ✅ Sofort speichern (wie im alten Code)
        sw.add_position_from_mouse(ms.position)

    # Global hotkey handler (pynput)
    def on_hotkey(self, key):
        try:
            pw = self.current_profile()
            if not pw:
                return

            # pynput-Key normalisieren
            if hasattr(key, "name"):
                key_name = key.name.upper()
            elif hasattr(key, "char") and key.char:
                key_name = key.char.upper()
            else:
                return

            if key_name == self.hotkeys["start"].upper():
                pw.start()

            elif key_name == self.hotkeys["stop"].upper():
                pw.stop()

            elif key_name == self.hotkeys["pos"].upper():
                sw = pw.current_set_widget()
                if sw and sw.cb_click.isChecked() and sw.cb_positions.isChecked():
                    self._awaiting_click_position = True
                    print("Warte auf nächsten Linksklick für Positionsspeicherung")

        except Exception as e:
            print("Hotkey-Fehler:", e)

    # Profiles
    def add_profile(self, name: str, data: Optional[dict] = None):
        pw = ProfileWidget(self, name)
        if isinstance(data, dict):
            pw.apply_settings(data)
        plus_index = self._profile_plus_index()
        insert_at = plus_index if plus_index is not None else self.tabs.count()

        idx = self.tabs.insertTab(insert_at, pw, name)

        self._ensure_profile_plus_tab()
        self.retranslate_all()

    def _add_profile_auto(self):
        prefix = tr(self.lang, "profile_prefix")

        used_numbers = set()

        # Alle bestehenden Profil-Tabs durchgehen
        for i in range(self.tabs.count()):
            title = self.tabs.tabText(i)

            # "+" überspringen
            if title == tr(self.lang, "plus_tab") or title == "+":
                continue

            # Standardnamen erkennen: "Profil X"
            if title.startswith(prefix + " "):
                tail = title[len(prefix) + 1:].strip()
                if tail.isdigit():
                    used_numbers.add(int(tail))

        # kleinste freie positive Zahl finden
        n = 1
        while n in used_numbers:
            n += 1

        name = f"{prefix} {n}"
        self.add_profile(name)

    def delete_current_profile(self):
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        if self.tabs.count() == 1:
            QMessageBox.warning(self, tr(self.lang, "not_possible"), tr(self.lang, "need_one_profile"))
            return
        name = self.tabs.tabText(idx)
        box = QMessageBox(self)
        box.setWindowTitle(tr(self.lang, "delete_profile_title"))
        box.setText(tr(self.lang, "delete_profile_confirm", name=name))

        btn_yes = box.addButton(tr(self.lang, "yes"), QMessageBox.ButtonRole.YesRole)
        btn_no = box.addButton(tr(self.lang, "no"), QMessageBox.ButtonRole.NoRole)

        box.exec()

        if box.clickedButton() is btn_yes:
            self.tabs.removeTab(idx)

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

        return {
            "window_size": {
                "width": self.width(),
                "height": self.height()
            },
            "ui": {
                "theme": self.theme
        },
            "last_active_profile": self.tabs.currentIndex(),
            "last_file_path": str(self._last_used_path) if self._last_used_path else None,
            "profiles": profiles
        }

    def apply_all_profiles(self, cfg: dict):
        # UI state restore
        ui = cfg.get("ui", {}) if isinstance(cfg, dict) else {}
        if "lang" in ui:
            self.lang = ui["lang"]

        if "theme" in ui:
            self.theme = ui["theme"]

        self.resize(DEFAULT_WINDOW_SIZE)
        apply_theme(QApplication.instance(), self.theme)
        self._apply_direction()

        # Fenstergröße wiederherstellen

        if not cfg.get("window_size"):
            self.resize(DEFAULT_WINDOW_SIZE)

        self.tabs.clear()

        profiles = cfg.get("profiles", []) if isinstance(cfg, dict) else []
        last_idx = cfg.get("last_active_profile", 0)
        last_path = cfg.get("last_file_path")

        if last_path:
            self._last_used_path = Path(last_path)

        if not profiles:
            self.add_profile(f"{tr(self.lang, 'profile_prefix')} 1")
            return

        for p in profiles:
            name = p.get("name", tr(self.lang, "profile_prefix"))
            data = p.get("data", {})
            self.add_profile(name, data if isinstance(data, dict) else None)

        # 🔥 NEU: letztes aktives Profil korrekt setzen
        profile_tabs = [
            i for i in range(self.tabs.count())
            if isinstance(self.tabs.widget(i), ProfileWidget)
        ]

        if profile_tabs:
            idx = profile_tabs[min(last_idx, len(profile_tabs) - 1)]
            self.tabs.setCurrentIndex(idx)

        self.retranslate_all()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.lang != LANG_AR:
            self._last_ltr_size = self.size()

    def save_profiles_default(self):
        path = self._last_used_path or SETTINGS_PATH
        try:
            Path(path).write_text(
                json.dumps(self.collect_all_profiles(), indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                tr(self.lang, "save_error_title"),
                tr(self.lang, "save_error_text", err=e)
            )

    def save_profiles_as(self):
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            tr(self.lang, "save_file_title"),
            str(self._last_used_path),
            tr(self.lang, "files_json")
        )

        if not path_str:
            return
        try:
            Path(path_str).write_text(json.dumps(self.collect_all_profiles(), indent=2), encoding="utf-8")
            self._last_used_path = Path(path_str)
        except Exception as e:
            QMessageBox.critical(self, tr(self.lang, "save_error_title"), tr(self.lang, "save_error_text", err=e))

    def load_profiles_default(self):
        self._last_used_path = SETTINGS_PATH

        if not SETTINGS_PATH.exists():
            self.add_profile(f"{tr(self.lang, 'profile_prefix')} 1")
            return

        try:
            cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.critical(self, tr(self.lang, "load_error_title"), tr(self.lang, "load_error_text", err=e))
            self.add_profile(f"{tr(self.lang, 'profile_prefix')} 1")
            return

        self.apply_all_profiles(cfg if isinstance(cfg, dict) else {})

    def load_profiles_from_file(self):
        start_dir = (
            str(self._last_used_path.parent)
            if self._last_used_path and self._last_used_path.exists()
            else str(Path.home())
        )

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            tr(self.lang, "load_file_title"),
            start_dir,
            tr(self.lang, "files_all_or_json")
        )

        if not path_str:
            return
        try:
            cfg = json.loads(Path(path_str).read_text(encoding="utf-8"))
            self._last_used_path = Path(path_str)
        except Exception as e:
            QMessageBox.critical(self, tr(self.lang, "load_error_title"), tr(self.lang, "load_error_text", err=e))
            return

        profiles = cfg.get("profiles", []) if isinstance(cfg, dict) else []
        if not profiles:
            QMessageBox.warning(self, tr(self.lang, "no_profiles_title"), tr(self.lang, "no_profiles_text"))
            return

        self.apply_all_profiles(cfg)

    def closeEvent(self, event):
        self.save_profiles_default()

        try:
            if getattr(self, "mouse_listener", None):
                self.mouse_listener.stop()
        except Exception:
            pass

        super().closeEvent(event)

    def _profile_plus_index(self):
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == tr(self.lang, "plus_tab") or self.tabs.tabText(i) == "+":
                return i
        return None

    def _ensure_profile_plus_tab(self):
        if self._profile_plus_index() is None:
            plus = QWidget()
            idx = self.tabs.addTab(plus, tr(self.lang, "plus_tab"))
            self.tabs.tabBar().setTabButton(
                idx,
                self.tabs.tabBar().ButtonPosition.RightSide,
                None
            )
            self.tabs.setTabEnabled(idx, True)
        else:
            idx = self._profile_plus_index()
            if idx is not None:
                self.tabs.setTabText(idx, tr(self.lang, "plus_tab"))
                self.tabs.tabBar().setTabButton(
                    idx,
                    self.tabs.tabBar().ButtonPosition.RightSide,
                    None
                )

    def _on_profile_tab_clicked(self, index):
        if self.tabs.tabText(index) == tr(self.lang, "plus_tab") or self.tabs.tabText(index) == "+":
            self._add_profile_auto()

    def _on_close_profile_tab(self, index):
        # "+" darf nicht geschlossen werden
        if self.tabs.tabText(index) == tr(self.lang, "plus_tab") or self.tabs.tabText(index) == "+":
            return

        # mindestens ein Profil behalten
        profile_count = self.tabs.count() - (1 if self._profile_plus_index() is not None else 0)
        if profile_count <= 1:
            QMessageBox.warning(
                self,
                tr(self.lang, "not_possible"),
                tr(self.lang, "need_one_profile")
            )
            return

        # Ziel-Index bestimmen
        new_index = index
        if index >= self.tabs.count() - 1:
            new_index = index - 1

        self.tabs.removeTab(index)

        # "+"-Tab überspringen
        if new_index >= 0 and (self.tabs.tabText(new_index) == tr(self.lang, "plus_tab") or self.tabs.tabText(new_index) == "+"):
            new_index -= 1

        if new_index >= 0:
            self.tabs.setCurrentIndex(new_index)


# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    from PyQt6.QtWidgets import QStyleFactory
    app.setStyle(QStyleFactory.create("Fusion"))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
