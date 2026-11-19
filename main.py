# -*- coding: utf-8 -*-
"""Офисные помощники — один файл, PyQt5, Windows 10/11."""
import json
import math
import os
import random
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PyQt5.QtCore import (Qt, QTimer, QPoint, QRect, QSize, QMimeData,
                          QPropertyAnimation, QEasingCurve, QThread, pyqtSignal)
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
            'mood': 'happy', 'daily': {}, 'last_praise': 0, 'autostart': False}


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


def load_config():
    obj = json.loads(json.dumps(DEFAULTS))
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            for key in ('mood', 'daily', 'last_praise', 'autostart'):
                if key in data:
                    obj[key] = data[key]
            for key in ('enabled', 'images'):
                if isinstance(data.get(key), dict):
                    for k in obj[key]:
                        if k in data[key]:
                            obj[key][k] = data[key][k]
    except (OSError, ValueError, TypeError):
        pass
    if obj['mood'] not in ('happy', 'angry'):
        obj['mood'] = 'happy'
    if not isinstance(obj['daily'], dict):
        obj['daily'] = {}
    return obj


def save_config(cfg):
    temp = CONFIG_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(CONFIG_FILE)


def image_for(cfg, slot, size):
    path = cfg['images'].get(slot, '')
    if path and Path(path).is_file():
        pix = QPixmap(path)
        if not pix.isNull():
            return pix.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return None


def rounded(p, rect, radius, color, border=None):
    p.setPen(QPen(QColor(border), 2) if border else Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(rect, radius, radius)


def draw_person(p, rect, mood='happy', legs=False, miniature=False):
    """Стандартный рисованный персонаж, без файлов картинок."""
    p.save()
    p.translate(rect.x(), rect.y())
    p.scale(rect.width() / 160.0, rect.height() / 190.0)
    p.setRenderHint(QPainter.Antialiasing)
    # руки и ноги
    p.setPen(QPen(QColor('#324b7e'), 11, Qt.SolidLine, Qt.RoundCap))
    if legs:
        p.drawLine(64, 139, 57, 183)
        p.drawLine(98, 139, 105, 183)
    p.drawLine(45, 104, 22, 130)
    p.drawLine(115, 104, 138, 125)
    # рубашка
    rounded(p, QRect(40, 91, 80, 69), 25, '#488be8', '#204c96')
    p.setPen(QPen(QColor('#ffffff'), 3))
    p.drawLine(80, 94, 80, 155)
    # лицо
    p.setPen(QPen(QColor('#794c37'), 3))
    p.setBrush(QColor('#ffd4a3'))
    p.drawEllipse(QRect(25, 8, 110, 106))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor('#573b30'))
    p.drawPie(QRect(27, 2, 106, 58), 0, 180 * 16)
    # глаза, брови
    p.setPen(QPen(QColor('#302d39'), 5, Qt.SolidLine, Qt.RoundCap))
    p.drawPoint(59, 62)
    p.drawPoint(102, 62)
    if mood == 'angry':
        p.drawLine(44, 43, 69, 52)
        p.drawLine(92, 52, 117, 43)
        p.setBrush(QColor('#a62939'))
        p.setPen(QPen(QColor('#72222c'), 2))
        p.drawEllipse(QRect(68, 76, 25, 23))
    else:
        p.drawLine(49, 43, 66, 41)
        p.drawLine(95, 41, 112, 43)
        p.setPen(QPen(QColor('#9f433a'), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRect(60, 68, 44, 28), 195 * 16, 150 * 16)
    p.restore()


class DesktopWidget(QWidget):
    def __init__(self, controller, size):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.ctrl = controller
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(*size)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda _: self.ctrl.open_settings())

    def set_hit_region(self, *regions):
        mask = QRegion()
        for r in regions:
            mask = mask.united(QRegion(r))
        self.setMask(mask)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.ctrl.open_settings()
        else:
            super().mousePressEvent(event)


class MainCharacter(DesktopWidget):
    def __init__(self, controller):
        super().__init__(controller, (320, 370))
        self.message = ''
        self.question = False
        self.shake = 0
        self.setAcceptDrops(True)
        self.yes = QPushButton('Да', self)
        self.no = QPushButton('Нет', self)
        for b in (self.yes, self.no):
            b.setStyleSheet('QPushButton {background: #ffffff; border: 1px solid #b7c7e1; border-radius: 12px; padding: 5px; font-weight: bold;} QPushButton:hover {background: #d9f0ff;}')
            b.resize(78, 31)
        self.yes.move(65, 98)
        self.no.move(165, 98)
        self.yes.clicked.connect(lambda: self.ctrl.answer(True))
        self.no.clicked.connect(lambda: self.ctrl.answer(False))
        self.yes.hide()
        self.no.hide()
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.clear_bubble)
        self.shake_timer = QTimer(self)
        self.shake_timer.timeout.connect(self.shake_step)
        self.update_mask()

    def update_mask(self):
        body = QRegion(QRect(68, 160, 185, 205), QRegion.Ellipse)
        if self.message:
            body = body.united(QRegion(QRect(9, 10, 302, 138)))
        self.setMask(body)

    def show_bubble(self, msg, duration=11000, question=False):
        self.message = msg
        self.question = question
        self.yes.setVisible(question)
        self.no.setVisible(question)
        self.hide_timer.stop()
        if not question and duration > 0:
            self.hide_timer.start(duration)
        self.update_mask()
        self.update()

    def clear_bubble(self):
        self.message = ''
        self.question = False
        self.yes.hide()
        self.no.hide()
        self.update_mask()
        self.update()

    def shake_step(self):
        self.shake += 1
        self.update()
        if self.shake >= 18:
            self.shake_timer.stop()
            self.shake = 0
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.message:
            rounded(p, QRect(10, 12, 300, 131), 20, '#fffef6', '#6d94d1')
            p.setPen(QColor('#263752'))
            f = QFont('Segoe UI', 12, QFont.DemiBold)
            p.setFont(f)
            p.drawText(QRect(24, 24, 272, 68 if self.question else 98), Qt.AlignCenter | Qt.TextWordWrap, self.message)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#fffef6'))
            triangle = QPainterPath()
            triangle.moveTo(138, 140)
            triangle.lineTo(159, 158)
            triangle.lineTo(174, 140)
            p.drawPath(triangle)
        displacement = random.choice([-7, 7]) if self.shake else 0
        slot = self.ctrl.cfg['mood']
        sprite_rect = QRect(76 + displacement, 164, 170, 198)
        pix = image_for(self.ctrl.cfg, slot, sprite_rect.size())
        if pix:
            p.drawPixmap(sprite_rect.x() + (sprite_rect.width()-pix.width())//2,
                         sprite_rect.bottom()-pix.height(), pix)
        else:
            draw_person(p, sprite_rect, slot)
        if self.shake:
            p.setPen(QPen(QColor('#fa364b'), 5))
            for i in range(4):
                x = 40 + i * 65
                p.drawLine(x, 180, x + 14, 160)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-office-chocolate'):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat('application/x-office-chocolate'):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat('application/x-office-chocolate'):
            # Широкая зона приёма облегчает попадание в рот на небольших экранах.
            if QRect(63, 164, 204, 203).contains(event.pos()):
                event.acceptProposedAction()
                self.ctrl.feed()


class Chocolate(QLabel):
    def __init__(self, parent=None):
        super().__init__('🍫  Шоколадка', parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(150, 43)
        self.setStyleSheet('background: #75402b; color: white; border-radius: 10px; font-size: 14px; font-weight: bold;')

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            drag = QDrag(self)
            data = QMimeData()
            data.setData('application/x-office-chocolate', b'chocolate')
            drag.setMimeData(data)
            drag.exec_(Qt.MoveAction)


class Fridge(DesktopWidget):
    def __init__(self, controller):
        super().__init__(controller, (86, 111))
        self.shelf = None
        self.set_hit_region(QRect(8, 8, 70, 99))
        self.setToolTip('Холодильник: нажмите, чтобы взять шоколадку')

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rounded(p, QRect(12, 8, 61, 96), 11, '#dcecf6', '#558da7')
        p.setPen(QPen(QColor('#6a96a9'), 3))
        p.drawLine(13, 49, 72, 49)
        p.drawLine(62, 26, 62, 41)
        p.drawLine(62, 62, 62, 83)
        p.setPen(QColor('#338db7'))
        p.setFont(QFont('Segoe UI', 15, QFont.Bold))
        p.drawText(QRect(13, 10, 56, 42), Qt.AlignCenter, '❄')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_shelf()
        else:
            super().mousePressEvent(event)

    def toggle_shelf(self):
        if self.shelf and self.shelf.isVisible():
            self.shelf.hide()
            return
        if self.shelf is None:
            self.shelf = QWidget(None, Qt.Tool | Qt.WindowStaysOnTopHint)
            self.shelf.setWindowTitle('Шоколадки — перетащите к персонажу')
            layout = QVBoxLayout(self.shelf)
            layout.addWidget(QLabel('Перетащите шоколадку на рот персонажа:'))
            for _ in range(3):
                layout.addWidget(Chocolate())
            self.shelf.setStyleSheet('QWidget {background: #f9f4ea; color: #253751;}')
            self.shelf.adjustSize()
        area = QApplication.desktop().availableGeometry(self)
        x = min(self.x(), area.right() - self.shelf.width())
        y = max(area.top(), self.y() - self.shelf.height() - 8)
        self.shelf.move(x, y)
        self.shelf.show()
        self.shelf.raise_()


class Walker(DesktopWidget):
    def __init__(self, controller):
        super().__init__(controller, (100, 155))
        self.set_hit_region(QRect(13, 8, 74, 143,))
        self.mode = 'idle'
        self.started = 0
        self.last_walk = time.monotonic()
        self.direction = 1
        self.step = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(60)

    def tick(self):
        now = time.monotonic()
        if self.mode == 'idle' and now - self.last_walk >= 600:
            self.mode = 'walk'
            self.started = now
            self.direction = random.choice((-1, 1))
        if self.mode == 'walk':
            area = QApplication.desktop().availableGeometry(self)
            dx = self.direction * 3
            if self.x() + dx < area.left() or self.x() + self.width() + dx > area.right():
                self.direction *= -1
                dx = self.direction * 3
            self.move(self.x() + dx, self.y())
            if now - self.started > 28:
                self.mode = 'idle'
                self.last_walk = now
        elif self.mode == 'dance' and now - self.started > 9:
            self.mode = 'idle'
            self.last_walk = now
        self.step += 1
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mode = 'dance'
            self.started = time.monotonic()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bounce = int(abs(math.sin(self.step * .2)) * 13) if self.mode == 'dance' else (int(abs(math.sin(self.step * .14)) * 4) if self.mode == 'walk' else 0)
        r = QRect(17, 7 + bounce, 68, 139 - bounce)
        pix = image_for(self.ctrl.cfg, 'walker', r.size())
        if pix:
            p.drawPixmap(r.x()+(r.width()-pix.width())//2, r.bottom()-pix.height(), pix)
        else:
            draw_person(p, r, 'happy', legs=True, miniature=True)
        if self.mode == 'dance':
            p.setFont(QFont('Segoe UI Symbol', 15))
            p.setPen(QColor('#e04f86'))
            p.drawText(0, 35, '♥')
            p.drawText(81, 53, '♫')


class Observer(DesktopWidget):
    def __init__(self, controller):
        super().__init__(controller, (270, 250))
        self.set_hit_region(QRect(0, 10, 265, 235))
        self.anim = None
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.retract)
        self._shown_rect = None
        self._hidden_rect = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rounded(p, QRect(10, 10, 235, 75), 18, '#fffdf2', '#83a0ca')
        p.setPen(QColor('#273a54'))
        p.setFont(QFont('Segoe UI', 12, QFont.DemiBold))
        p.drawText(QRect(18, 16, 218, 60), Qt.AlignCenter | Qt.TextWordWrap, 'Я слежу за тобой!')
        r = QRect(117, 77, 134, 165)
        pix = image_for(self.ctrl.cfg, 'observer', r.size())
        if pix:
            p.drawPixmap(r.x()+(r.width()-pix.width())//2, r.bottom()-pix.height(), pix)
        else:
            draw_person(p, r, 'happy')

    def appear(self):
        if not self.ctrl.cfg['enabled']['observer']:
            return
        area = QApplication.desktop().availableGeometry()
        y = area.top() + max(35, (area.height() - self.height()) // 3)
        self._shown_rect = QRect(area.right() - self.width() + 26, y, self.width(), self.height())
        self._hidden_rect = QRect(area.right() + 2, y, self.width(), self.height())
        self.setGeometry(self._hidden_rect)
        self.show()
        self.anim_to(self._shown_rect)
        self.hide_timer.start(12500)

    def anim_to(self, rect):
        if self.anim:
            self.anim.stop()
        self.anim = QPropertyAnimation(self, b'geometry', self)
        self.anim.setDuration(700)
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(rect)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

    def retract(self):
        if self._hidden_rect:
            self.anim_to(self._hidden_rect)
            QTimer.singleShot(800, self.hide)


class WeatherFetch(QThread):
    received = pyqtSignal(str)

    def run(self):
        # Open-Meteo: Омск, широта 54.99, долгота 73.37, бесплатный API без ключа.
        url = ('https://api.open-meteo.com/v1/forecast?latitude=54.99&longitude=73.37'
               '&current=temperature_2m,weather_code&timezone=Asia%2FOmsk')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'OfficeHelpers/1.0'})
            with urllib.request.urlopen(req, timeout=9) as response:
                current = json.loads(response.read().decode('utf-8'))['current']
            code = int(current['weather_code'])
            if code == 0:
                label = 'Ясно'
            elif code <= 3:
                label = 'Облачно'
            elif code in (45, 48):
                label = 'Туман'
            elif 51 <= code <= 67 or 80 <= code <= 82:
                label = 'Дождь'
            elif 71 <= code <= 77 or 85 <= code <= 86:
                label = 'Снег'
            elif code >= 95:
                label = 'Гроза'
            else:
                label = 'Переменная погода'
            self.received.emit(f"{float(current['temperature_2m']):+.0f}°C · {label}")
        except Exception:
            self.received.emit('Погода недоступна')


class ClockWeather(DesktopWidget):
    def __init__(self, controller):
        super().__init__(controller, (240, 85))
        self.set_hit_region(QRect(2, 2, 236, 80))
        self.weather = 'Загрузка погоды…'
        self.fetcher = None
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.update)
        self.tick_timer.start(20000)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.fetch_weather)
        self.refresh_timer.start(30 * 60 * 1000)
        self.fetch_weather()

    def fetch_weather(self):
        if self.fetcher and self.fetcher.isRunning():
            return
        self.fetcher = WeatherFetch(self)
        self.fetcher.received.connect(self.set_weather)
        self.fetcher.start()

    def set_weather(self, text):
        self.weather = text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rounded(p, QRect(3, 3, 233, 78), 17, '#e8f1ff', '#6d9bcf')
        p.setPen(QColor('#23466d'))
        p.setFont(QFont('Segoe UI', 18, QFont.Bold))
        p.drawText(QRect(14, 5, 210, 39), Qt.AlignCenter, oms_now().strftime('%H:%M') + ' · Омск')
        p.setFont(QFont('Segoe UI', 10))
        p.drawText(QRect(10, 46, 219, 28), Qt.AlignCenter, self.weather)


class Settings(QDialog):
    def __init__(self, controller):
        super().__init__()
        self.ctrl = controller
        self.setWindowTitle('Офисные помощники — настройки')
        self.setWindowIcon(controller.icon)
        self.resize(530, 620)
        self.setMinimumWidth(460)
        self.setStyleSheet('QDialog {background: #f5f8fc;} QGroupBox {font-weight: bold; border: 1px solid #c9d7eb; border-radius: 9px; margin-top: 12px; padding-top: 13px;} QGroupBox::title {subcontrol-origin: margin; left: 11px; padding: 0 5px;} QPushButton {padding: 7px 11px; border: 1px solid #abc0db; border-radius: 7px; background: white;} QPushButton:hover {background: #e0edff;}')
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        panel = QWidget()
        scroll.setWidget(panel)
        lay = QVBoxLayout(panel)
        lay.addWidget(QLabel('Включайте помощников и заменяйте их изображения.'))
        group = QGroupBox('Что показывать на рабочем столе')
        checks = QVBoxLayout(group)
        for key, title in FEATURES.items():
            ch = QCheckBox(title)
            ch.setChecked(self.ctrl.cfg['enabled'][key])
            ch.toggled.connect(lambda checked, k=key: self.ctrl.set_enabled(k, checked))
            checks.addWidget(ch)
        lay.addWidget(group)
        files = QGroupBox('Изображения PNG / JPG')
        files_lay = QVBoxLayout(files)
        for slot, title in SLOTS.items():
            row = QHBoxLayout()
            lbl = QLabel(title)
            lbl.setMinimumWidth(175)
            btn = QPushButton('Загрузить картинку…')
            btn.clicked.connect(lambda _, s=slot: self.ctrl.select_image(s))
            row.addWidget(lbl)
            row.addWidget(btn)
            files_lay.addLayout(row)
        hint = QLabel('Совет: прозрачный PNG лучше смотрится на рабочем столе.\nИзображение автоматически масштабируется без искажения пропорций.')
        hint.setWordWrap(True)
        files_lay.addWidget(hint)
        reset = QPushButton('Сбросить картинки на стандартные')
        reset.clicked.connect(self.ctrl.reset_images)
        files_lay.addWidget(reset)
        lay.addWidget(files)
        actions = QGroupBox('Действия')
        al = QVBoxLayout(actions)
        summon = QPushButton('Вызвать наблюдателя сейчас')
        summon.clicked.connect(self.ctrl.summon_observer)
        al.addWidget(summon)
        question = QPushButton('Спросить про заявку сейчас')
        question.clicked.connect(self.ctrl.ask_question)
        al.addWidget(question)
        auto = QCheckBox('Запускать вместе с Windows')
        auto.setChecked(self.ctrl.cfg['autostart'])
        auto.toggled.connect(self.ctrl.set_autostart)
        al.addWidget(auto)
        lay.addWidget(actions)
        lay.addWidget(QLabel('Данные: ' + str(APP_DIR)))
        lay.addStretch()
        close = QPushButton('Закрыть настройки')
        close.clicked.connect(self.close)
        outer.addWidget(close)


class Controller:
    def __init__(self, app):
        self.app = app
        self.cfg = load_config()
        self.icon = self.make_icon()
        self.app.setWindowIcon(self.icon)
        self.settings = None
        self.main = MainCharacter(self)
        self.fridge = Fridge(self)
        self.walker = Walker(self)
        self.observer = Observer(self)
        self.weather = ClockWeather(self)
        self.windows = {'main': self.main, 'fridge': self.fridge,
                        'walker': self.walker, 'observer': self.observer,
                        'weather': self.weather}
        self.place_windows()
        for key in FEATURES:
            self.set_enabled(key, self.cfg['enabled'][key], persist=False)
        self.tray = QSystemTrayIcon(self.icon, self.app)
        self.tray.setToolTip('Офисные помощники — настройки')
        menu = QMenu()
        open_act = menu.addAction('⚙ Настройки')
        open_act.triggered.connect(self.open_settings)
        ask_act = menu.addAction('Закрыта ли заявка?')
        ask_act.triggered.connect(self.ask_question)
        menu.addSeparator()
        quit_act = menu.addAction('Выход из приложения')
        quit_act.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_click)
        self.tray.show()
        self.scheduler = QTimer(self.app)
        self.scheduler.timeout.connect(self.check_schedule)
        self.scheduler.start(15000)
        QTimer.singleShot(2500, self.first_greeting)
        self.check_schedule()

    def make_icon(self):
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        draw_person(p, QRect(4, 1, 56, 65), 'happy')
        p.end()
        return QIcon(pm)

    def place_windows(self):
        area = QApplication.desktop().availableGeometry()
        self.main.move(area.left() + max(20, (area.width() - 320)//2), area.bottom() - 370 + 1)
        self.fridge.move(min(area.right()-88, self.main.x()+330), area.bottom()-113)
        self.walker.move(area.left()+max(15, area.width()//8), area.bottom()-154)
        self.weather.move(area.left()+20, area.top()+20)

    def tray_click(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_settings()

    def open_settings(self):
        if self.settings is None:
            self.settings = Settings(self)
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def set_enabled(self, key, value, persist=True):
        self.cfg['enabled'][key] = bool(value)
        win = self.windows[key]
        if key == 'observer':
            if not value:
                win.hide_timer.stop()
                win.hide()
        else:
            win.setVisible(bool(value))
        if key == 'fridge' and not value and self.fridge.shelf:
            self.fridge.shelf.hide()
        if persist:
            save_config(self.cfg)

    def select_image(self, slot):
        path, _ = QFileDialog.getOpenFileName(self.settings, 'Выбрать картинку', '',
            'Изображения (*.png *.jpg *.jpeg)')
        if not path:
            return
        pm = QPixmap(path)
        if pm.isNull():
            QMessageBox.warning(self.settings, 'Ошибка', 'Не удалось прочитать изображение.')
            return
        try:
            ext = Path(path).suffix.lower()
            dst = IMAGE_DIR / (slot + ext)
            temp = IMAGE_DIR / (slot + '.pending' + ext)
            shutil.copy2(path, temp)
            if dst.exists():
                dst.unlink()
            temp.rename(dst)
            self.cfg['images'][slot] = str(dst)
            save_config(self.cfg)
            self.main.update()
            self.walker.update()
            self.observer.update()
            QMessageBox.information(self.settings, 'Готово', 'Изображение сохранено и применено.')
        except OSError as exc:
            QMessageBox.warning(self.settings, 'Ошибка сохранения', str(exc))

    def reset_images(self):
        for slot in SLOTS:
            self.cfg['images'][slot] = ''
        save_config(self.cfg)
        self.main.update()
        self.walker.update()
        self.observer.update()

    def set_autostart(self, checked):
        if sys.platform != 'win32':
            QMessageBox.information(self.settings, 'Windows', 'Автозапуск доступен в Windows.')
            return
        try:
            import winreg
            name = 'OfficeHelpers'
            if getattr(sys, 'frozen', False):
                command = '"' + sys.executable + '"'
            else:
                command = '"' + sys.executable + '" "' + str(Path(__file__).resolve()) + '"'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Microsoft\Windows\CurrentVersion\Run',
                                0, winreg.KEY_SET_VALUE) as key:
                if checked:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
            self.cfg['autostart'] = bool(checked)
            save_config(self.cfg)
        except OSError as exc:
            QMessageBox.warning(self.settings, 'Ошибка автозапуска', str(exc))

    def first_greeting(self):
        if self.cfg['enabled']['main']:
            self.main.show_bubble('Привет, Аня!', 4500)
        # После приветствия предложим ежедневный вопрос, если ещё не отвечали.
        if self.cfg['daily'].get('question') != date_key():
            QTimer.singleShot(6500, self.ask_question)

    def ask_question(self):
        if not self.cfg['enabled']['main']:
            return
        self.main.show_bubble('Закрыта ли заявка?', duration=0, question=True)
        self.main.raise_()

    def answer(self, yes):
        self.cfg['daily']['question'] = date_key()
        if yes:
            self.cfg['mood'] = 'happy'
            self.main.show_bubble('Молодец! Отличная работа!')
            notify_sound()
        else:
            self.cfg['mood'] = 'angry'
            self.main.show_bubble('Аня! Срочно закрывай заявку! Я возмущён!')
            self.main.shake = 1
            self.main.shake_timer.start(70)
            notify_sound('angry')
        save_config(self.cfg)
        self.main.update()

    def feed(self):
        self.cfg['mood'] = 'happy'
        save_config(self.cfg)
        self.main.show_bubble('Хрум-хрум! Спасибо за шоколадку! ♥', 9000)
        notify_sound('crunch')
        self.fridge.shelf.hide() if self.fridge.shelf else None
        self.main.update()

    def summon_observer(self):
        if self.cfg['enabled']['observer']:
            self.observer.appear()
        else:
            QMessageBox.information(self.settings, 'Наблюдатель', 'Сначала включите наблюдателя в настройках.')

    def check_schedule(self):
        now = oms_now()
        today = now.date().isoformat()
        daily = self.cfg['daily']
        changed = False
        if now.hour == 10 and now.minute == 0 and daily.get('observer') != today:
            daily['observer'] = today
            if self.cfg['enabled']['observer']:
                self.observer.appear()
            changed = True
        if now.hour == 11 and now.minute == 0 and daily.get('avito') != today:
            daily['avito'] = today
            if self.cfg['enabled']['main']:
                self.main.show_bubble('Звонишь ли ты на Авито?', 14000)
                notify_sound()
            changed = True
        if self.cfg['enabled']['main'] and self.cfg['mood'] == 'happy':
            last = self.cfg.get('last_praise', 0)
            if not isinstance(last, (int, float)):
                last = 0
            if time.time() - last >= 7200:
                self.cfg['last_praise'] = time.time()
                # Не мешаем вопросу и приветствию; первый интервал идёт от запуска.
                if last != 0 and not self.main.question and not self.main.message:
                    self.main.show_bubble(random.choice([
                        'Ты отлично справляешься!', 'Так держать!',
                        'Аня, ты молодец!', 'Горжусь твоей работой!',
                        'У тебя всё получается!']), 10000)
                changed = True
        if changed:
            save_config(self.cfg)

    def quit(self):
        self.scheduler.stop()
        self.tray.hide()
        self.app.quit()


def main():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('OfficeHelpers.Desktop.1')
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('Офисные помощники')
    ctrl = Controller(app)
    # Явная ссылка, чтобы Python не освободил контроллер до выхода.
    app.controller = ctrl
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
