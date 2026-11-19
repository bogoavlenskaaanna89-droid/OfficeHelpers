# -*- coding: utf-8 -*-
"""Офисные помощники — один файл, PyQt5, Windows 10/11."""
import json
import math
import os
import random
import shutil
import subprocess
import base64
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PyQt5.QtCore import (Qt, QTimer, QPoint, QRect, QSize, QMimeData,
                          QPropertyAnimation, QEasingCurve, QThread, pyqtSignal)
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QPixmap,
                         QIcon, QRegion, QPainterPath, QDrag, QLinearGradient)
from PyQt5.QtWidgets import (QApplication, QWidget, QDialog, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QCheckBox,
                             QFileDialog, QMessageBox, QSystemTrayIcon, QMenu,
                             QGroupBox, QScrollArea)

OMS = timezone(timedelta(hours=6))
APP_DIR = Path(os.getenv('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local')) / 'OfficeHelpers'
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = APP_DIR / 'config.json'
IMAGE_DIR = APP_DIR / 'images'
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
SLOTS = {'happy': 'Главный — добрый', 'angry': 'Главный — злой',
         'walker': 'Маленький персонаж', 'observer': 'Наблюдатель'}
FEATURES = {'main': 'Главный персонаж', 'fridge': 'Холодильник',
            'walker': 'Маленький ходячий персонаж', 'observer': 'Наблюдатель',
            'weather': 'Время и погода в Омске'}
DEFAULTS = {'enabled': {k: True for k in FEATURES}, 'images': {k: '' for k in SLOTS},
            'mood': 'happy', 'daily': {}, 'last_praise': 0, 'autostart': False,
            'positions': {}, 'desktop_shortcut_created': False}


def oms_now():
    return datetime.now(OMS)


def date_key():
    return oms_now().date().isoformat()


def notify_sound(kind='notify'):
    try:
        if sys.platform == 'win32':
            import winsound
            if kind == 'crunch':
                winsound.MessageBeep(winsound.MB_OK)
            elif kind == 'angry':
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            else:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            QApplication.beep()
    except Exception:
        QApplication.beep()
