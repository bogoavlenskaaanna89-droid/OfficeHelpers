# -*- coding: utf-8 -*-
"""Офисные помощники — версия 4, один файл, PyQt5, Windows 10/11.

Все стандартные рисунки создаются программно. Настройки и диагностический журнал
находятся в LOCALAPPDATA/OfficeHelpers. Никаких внешних ресурсов для старта нет.
"""
import json
import math
import os
import random
import shutil
import subprocess
import base64
import sys
import traceback
import logging
import atexit
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
LOG_FILE = APP_DIR / 'officehelpers.log'


def write_failure(exc_type, exc, tb):
    """Даже у --noconsole версии остаётся понятная запись о сбое."""
    try:
        import datetime as _dt
        with LOG_FILE.open('a', encoding='utf-8') as f:
            f.write('\n' + _dt.datetime.now().isoformat() + ' — ОШИБКА\n')
            traceback.print_exception(exc_type, exc, tb, file=f)
    except Exception:
        pass
    try:
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(None, 'OfficeHelpers — ошибка',
                'Программа столкнулась с ошибкой.\n'
                'Журнал: ' + str(LOG_FILE) + '\n\n' + str(exc))
    except Exception:
        pass


sys.excepthook = write_failure
SLOTS = {'happy': 'Главный — добрый', 'angry': 'Главный — злой',
         'happy_open': 'Главный — добрый, рот открыт (необязательно)',
         'angry_open': 'Главный — злой, рот открыт (необязательно)',
         'walker': 'Маленький — стоит',
         'walker_walk': 'Маленький — идёт (необязательно)',
         'walker_dance': 'Маленький — танцует (необязательно)',
         'observer': 'Наблюдатель'}
FEATURES = {'main': 'Главный персонаж', 'fridge': 'Холодильник',
            'walker': 'Маленький ходячий персонаж', 'observer': 'Наблюдатель',
            'weather': 'Время и погода в Омске'}
DEFAULTS = {'enabled': {k: True for k in FEATURES}, 'images': {k: '' for k in SLOTS},
            'mood': 'happy', 'daily': {}, 'last_praise': 0, 'autostart': False,
            'positions': {}, 'desktop_shortcut_created': False, 'first_settings_opened': False}


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
            for key in ('mood', 'daily', 'last_praise', 'autostart', 'desktop_shortcut_created', 'first_settings_opened'):
                if key in data:
                    obj[key] = data[key]
            for key in ('enabled', 'images'):
                if isinstance(data.get(key), dict):
                    for k in obj[key]:
                        if k in data[key]:
                            obj[key][k] = data[key][k]
            # Позиции не имеют заранее заданных ключей — копируем их отдельно.
            if isinstance(data.get('positions'), dict):
                obj['positions'] = {k: v for k, v in data['positions'].items()
                                    if k in ('walker', 'fridge')}
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


def draw_person(p, rect, mood='happy', legs=False, miniature=False, mouth_open=False):
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
        if not mouth_open:
            p.setPen(QPen(QColor('#9f433a'), 4, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRect(60, 68, 44, 28), 195 * 16, 150 * 16)
    if mouth_open:
        p.setPen(QPen(QColor('#983b38'), 3))
        p.setBrush(QColor('#4b1d31'))
        p.drawEllipse(QRect(66, 72, 30, 31))
        p.setBrush(QColor('#ee7791'))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRect(72, 93, 18, 6))
    p.restore()


class DesktopWidget(QWidget):
    """Непрозрачные части поверх ОБОЕВ, но не поверх других приложений."""
    def __init__(self, controller, size):
        # Важно: WindowStaysOnTopHint здесь НЕТ. Настройки — отдельное обычное окно.
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.ctrl = controller
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(*size)
        self._drag_origin = None
        self._drag_window_origin = None
        self._moved_by_drag = False
        self.drag_key = None
        self.drag_horizontal_only = False
        self.setToolTip('Правая кнопка мыши — настройки')

    def set_hit_region(self, *regions):
        mask = QRegion()
        for r in regions:
            mask = mask.united(QRegion(r))
        self.setMask(mask)

    def send_behind_applications(self):
        # Никакого WindowStaysOnTopHint. Это виджет на рабочем столе,
        # обычные приложения по-прежнему могут его перекрывать.
        return

    def show_desktop(self):
        self.show()
        # Персонаж останется позади активных приложений после смены фокуса.

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.ctrl.open_settings()
            event.accept()
        elif event.button() == Qt.LeftButton and self.drag_key:
            self._drag_origin = event.globalPos()
            self._drag_window_origin = self.pos()
            self._moved_by_drag = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and (event.buttons() & Qt.LeftButton):
            delta = event.globalPos() - self._drag_origin
            if delta.manhattanLength() >= QApplication.startDragDistance():
                self._moved_by_drag = True
            if self._moved_by_drag:
                destination = self._drag_window_origin + delta
                if self.drag_horizontal_only:
                    destination.setY(self.ctrl.walker_track_y())
                self.move(destination)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_origin is not None:
            was_drag = self._moved_by_drag
            self._drag_origin = None
            self._drag_window_origin = None
            self._moved_by_drag = False
            if was_drag:
                self.ctrl.save_position(self.drag_key, self.pos())
            else:
                self.on_simple_click()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def on_simple_click(self):
        pass


class MainCharacter(DesktopWidget):
    """Большой бюст справа: верх на середине экрана, низ строго у панели задач."""
    def __init__(self, controller):
        area = QApplication.desktop().availableGeometry()
        width = max(300, min(520, int(area.width() * 0.36)))
        height = max(260, int(area.height() * 0.5))
        super().__init__(controller, (width, height))
        self.message = ''
        self.question = False
        self.shake = 0
        self.mouth_open = False
        self.setAcceptDrops(True)
        self.yes = QPushButton('Да', self)
        self.no = QPushButton('Нет', self)
        for b in (self.yes, self.no):
            b.setStyleSheet('QPushButton {background: #ffffff; border: 1px solid #b7c7e1; border-radius: 12px; padding: 5px; font-weight: bold;} QPushButton:hover {background: #d9f0ff;}')
            b.resize(74, 31)
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

    def figure_rect(self):
        # Центр тела справа, высота больше видимой части: низ рисунка обрезается по пояс.
        return QRect(int(self.width()*.22), int(self.height()*.14),
                     int(self.width()*.77), int(self.height()*1.20))

    def mouth_point(self):
        r = self.figure_rect()
        # Координаты рта совпадают с расположением рта в векторном персонаже.
        return QPoint(r.x()+int(r.width()*0.50), r.y()+int(r.height()*0.47))

    def mouth_zone(self):
        c = self.mouth_point()
        radius = max(42, int(self.width()*.115))
        return QRect(c.x()-radius, c.y()-radius, radius*2, radius*2)

    def update_mask(self):
        r = self.figure_rect()
        # Окно визуально прозрачное, не блокирует клики в остальных областях.
        mask = QRegion(QRect(r.x(), r.y(), r.width(), self.height()-r.y()))
        mask = mask.united(QRegion(self.mouth_zone()))
        if self.message:
            mask = mask.united(QRegion(self.bubble_rect()))
        self.setMask(mask)

    def bubble_rect(self):
        return QRect(4, 5, int(self.width()*.76), max(118, int(self.height()*.29)))

    def show_bubble(self, msg, duration=11000, question=False):
        self.message = msg
        self.question = question
        bubble = self.bubble_rect()
        self.yes.move(bubble.x()+int(bubble.width()*.18), bubble.bottom()-39)
        self.no.move(bubble.x()+int(bubble.width()*.59), bubble.bottom()-39)
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
            bubble = self.bubble_rect()
            rounded(p, bubble, 20, '#fffef6', '#6d94d1')
            p.setPen(QColor('#263752'))
            p.setFont(QFont('Segoe UI', max(10, min(14, self.width()//32)), QFont.DemiBold))
            text_rect = bubble.adjusted(12, 8, -12, -42 if self.question else -8)
            p.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.message)
        displacement = random.choice([-7, 7]) if self.shake else 0
        slot = self.ctrl.cfg['mood']
        rect = self.figure_rect().translated(displacement, 0)
        mouth_slot = slot + '_open' if self.mouth_open else slot
        pix = image_for(self.ctrl.cfg, mouth_slot, rect.size()) if self.mouth_open else None
        if pix is None:
            pix = image_for(self.ctrl.cfg, slot, rect.size())
        natural_open_image = bool(self.mouth_open and self.ctrl.cfg['images'].get(mouth_slot))
        if pix:
            p.drawPixmap(rect.x()+(rect.width()-pix.width())//2,
                         rect.y(), pix)
            # Для собственных статичных изображений рисуем условно открытый рот сверху.
            if self.mouth_open and not natural_open_image:
                c = self.mouth_point()
                p.setPen(QPen(QColor('#9e434a'), 3))
                p.setBrush(QColor('#4b2036'))
                p.drawEllipse(QRect(c.x()-17, c.y()-15, 34, 36))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor('#e97b91'))
                p.drawEllipse(QRect(c.x()-11, c.y()+11, 22, 8))
        else:
            draw_person(p, rect, slot, mouth_open=self.mouth_open)
        if self.shake:
            p.setPen(QPen(QColor('#fa364b'), 5))
            for i in range(4):
                x = 25+i*int(self.width()*.21)
                p.drawLine(x, self.height()//2, x+14, self.height()//2-20)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-office-chocolate'):
            self.mouth_open = self.mouth_zone().contains(event.pos())
            self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat('application/x-office-chocolate'):
            self.mouth_open = self.mouth_zone().contains(event.pos())
            self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.mouth_open = False
        self.update()

    def dropEvent(self, event):
        hit = (event.mimeData().hasFormat('application/x-office-chocolate')
               and self.mouth_zone().contains(event.pos()))
        self.mouth_open = False
        self.update()
        if hit:
            event.acceptProposedAction()
            self.ctrl.feed()
        else:
            event.ignore()

class Chocolate(QLabel):
    def __init__(self, parent=None):
        super().__init__('🍫  Шоколадка', parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(150, 43)
        self.setStyleSheet('background: #75402b; color: white; border-radius: 10px; font-size: 14px; font-weight: bold;')
        self._start = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._start = e.pos()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self._start is not None and (e.pos()-self._start).manhattanLength() >= QApplication.startDragDistance():
            drag = QDrag(self)
            data = QMimeData()
            data.setData('application/x-office-chocolate', b'chocolate')
            drag.setMimeData(data)
            pix = self.grab()  # шоколадка видна под курсором во время перетаскивания
            drag.setPixmap(pix)
            drag.setHotSpot(QPoint(pix.width()//2, pix.height()//2))
            drag.exec_(Qt.MoveAction)
            self._start = None

    def mouseReleaseEvent(self, e):
        self._start = None

class Fridge(DesktopWidget):
    def __init__(self, controller):
        super().__init__(controller, (86, 111))
        self.drag_key = 'fridge'
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

    def on_simple_click(self):
        self.toggle_shelf()

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
        self.drag_key = 'walker'
        self.drag_horizontal_only = True
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
        if self._drag_origin is not None:
            return
        if self.mode == 'idle' and now - self.last_walk >= 300:
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

    def on_simple_click(self):
        self.mode = 'dance'
        self.started = time.monotonic()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bounce = int(abs(math.sin(self.step * .2)) * 13) if self.mode == 'dance' else (int(abs(math.sin(self.step * .14)) * 4) if self.mode == 'walk' else 0)
        r = QRect(17, 7 + bounce, 68, 139 - bounce)
        variant = 'walker_dance' if self.mode == 'dance' else ('walker_walk' if self.mode == 'walk' else 'walker')
        pix = image_for(self.ctrl.cfg, variant, r.size()) or image_for(self.ctrl.cfg, 'walker', r.size())
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
        # Временное появление должно быть видно даже при открытом браузере.
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
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
        p.drawText(QRect(18, 16, 218, 60), Qt.AlignCenter | Qt.TextWordWrap, 'Ку-ку! 👀')
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
        self.show_desktop()
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
        tip = QLabel('Маленький персонаж перетаскивается только вдоль нижнего края и ходит каждые 5 минут.\nХолодильник можно свободно двигать по экрану.\nЯрлык «Офисные помощники — настройки» появится на рабочем столе.')
        tip.setWordWrap(True)
        lay.addWidget(tip)
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
        hint = QLabel('PNG с прозрачностью лучше смотрится на рабочем столе.\nДополнительные картинки с открытым ртом и ходьбой необязательны: при их отсутствии работает стандартная анимация.\nИзображения автоматически масштабируются без искажения пропорций.')
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
        shortcut = QPushButton('Создать / обновить ярлык настроек на рабочем столе')
        shortcut.clicked.connect(self.ctrl.create_desktop_shortcut)
        al.addWidget(shortcut)
        lay.addWidget(actions)
        lay.addWidget(QLabel('Данные: ' + str(APP_DIR)))
        lay.addWidget(QLabel('Если окно не запускается, журнал ошибок: ' + str(LOG_FILE)))
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
        QTimer.singleShot(1000, self.ensure_desktop_shortcut)
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
        if '--settings' in sys.argv or not self.cfg.get('first_settings_opened'):
            QTimer.singleShot(1100, self.open_settings)
            self.cfg['first_settings_opened'] = True
            save_config(self.cfg)

    def make_icon(self):
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        draw_person(p, QRect(4, 1, 56, 65), 'happy')
        p.end()
        return QIcon(pm)

    def walker_track_y(self):
        area = QApplication.desktop().availableGeometry()
        return area.bottom() - self.walker.height() + 1

    def place_windows(self):
        area = QApplication.desktop().availableGeometry()
        self.main.move(area.right()-self.main.width()+1, area.bottom()-self.main.height()+1)
        self.fridge.move(area.left()+max(35, area.width()//4), area.bottom()-self.fridge.height()+1)
        self.walker.move(area.left()+max(15, area.width()//8), self.walker_track_y())
        self.weather.move(area.left()+20, area.top()+20)
        for key in ('walker', 'fridge'):
            xy = self.cfg.get('positions', {}).get(key)
            if isinstance(xy, list) and len(xy) == 2 and all(isinstance(n, int) for n in xy):
                win = self.windows[key]
                x = max(area.left(), min(xy[0], area.right()-win.width()+1))
                y = self.walker_track_y() if key == 'walker' else max(area.top(), min(xy[1], area.bottom()-win.height()+1))
                win.move(x, y)

    def save_position(self, key, pos):
        if key not in ('walker', 'fridge'):
            return
        area = QApplication.desktop().availableGeometry()
        win = self.windows[key]
        x = max(area.left(), min(pos.x(), area.right()-win.width()+1))
        y = self.walker_track_y() if key == 'walker' else max(area.top(), min(pos.y(), area.bottom()-win.height()+1))
        win.move(x, y)
        self.cfg['positions'][key] = [x, y]
        save_config(self.cfg)
        win.send_behind_applications()

    def ensure_desktop_shortcut(self):
        if sys.platform == 'win32' and getattr(sys, 'frozen', False):
            self.create_desktop_shortcut(silent=True)

    def create_desktop_shortcut(self, silent=False):
        """Ярлык Windows запускает единственный EXE с флагом --settings."""
        if sys.platform != 'win32':
            if not silent:
                QMessageBox.information(self.settings, 'Windows', 'Ярлык создаётся на рабочем столе Windows.')
            return
        try:
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                    r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                    desktop, _ = winreg.QueryValueEx(key, 'Desktop')
                    desktop = Path(os.path.expandvars(desktop))
            except OSError:
                desktop = Path.home() / 'Desktop'
            desktop.mkdir(parents=True, exist_ok=True)
            target = sys.executable if getattr(sys, 'frozen', False) else str(Path(__file__).resolve())
            args = '--settings' if getattr(sys, 'frozen', False) else '"' + str(Path(__file__).resolve()) + '" --settings'
            # Windows COM WScript.Shell, без сторонних библиотек.
            def psquote(value):
                return "'" + str(value).replace("'", "''") + "'"
            shortcut_path = desktop / 'Офисные помощники — настройки.lnk'
            script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut("+psquote(shortcut_path)+");"
                      "$s.TargetPath="+psquote(target)+";"
                      "$s.Arguments="+psquote(args)+";"
                      "$s.WorkingDirectory="+psquote(str(Path(target).parent))+";"
                      "$s.Description='Открыть настройки офисных помощников';"
                      "$s.IconLocation="+psquote(target)+";"
                      "$s.Save()")
            subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',
                            base64.b64encode(script.encode('utf-16le')).decode('ascii')],
                           check=True, timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.cfg['desktop_shortcut_created'] = True
            save_config(self.cfg)
            if not silent:
                QMessageBox.information(self.settings, 'Готово', 'Ярлык настроек создан на рабочем столе.')
        except Exception as exc:
            if not silent:
                QMessageBox.warning(self.settings, 'Ярлык', 'Не удалось создать ярлык: '+str(exc))

    def tray_click(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_settings()

    def open_settings(self):
        if self.settings is None:
            self.settings = Settings(self)
        self.settings.showNormal()
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
            if value:
                win.show_desktop()
            else:
                win.hide()
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
        self.main.mouth_open = False
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
    if '--diagnose' in sys.argv:
        print('OfficeHelpers v4: Python / PyQt5 импортированы успешно')
        print('Папка данных:', APP_DIR)
        print('Файл конфигурации:', CONFIG_FILE)
        print('Журнал ошибок:', LOG_FILE)
        return 0
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('OfficeHelpers.Desktop.1')
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('Офисные помощники')
    # Не запускать второй набор персонажей при двойном щелчке ярлыка.
    server_name = 'OfficeHelpers_' + ''.join(c if c.isalnum() else '_' for c in (os.getenv('USERNAME') or 'user'))
    client = QLocalSocket()
    client.connectToServer(server_name)
    if client.waitForConnected(650):
        client.write(b'open_settings')
        client.flush()
        client.waitForBytesWritten(700)
        client.disconnectFromServer()
        return 0
    server = QLocalServer(app)
    # Старые сокеты от аварийно закрытого процесса можно безопасно сбросить.
    QLocalServer.removeServer(server_name)
    server.listen(server_name)
    ctrl = Controller(app)
    def on_connection():
        while server.hasPendingConnections():
            socket = server.nextPendingConnection()
            socket.waitForReadyRead(500)
            message = bytes(socket.readAll())
            if b'open_settings' in message:
                ctrl.open_settings()
            socket.disconnectFromServer()
            socket.deleteLater()
    server.newConnection.connect(on_connection)
    app.local_server = server

    # Явная ссылка, чтобы Python не освободил контроллер до выхода.
    app.controller = ctrl
    return app.exec_()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        et, ex, tb = sys.exc_info()
        write_failure(et, ex, tb)
        sys.exit(1)

