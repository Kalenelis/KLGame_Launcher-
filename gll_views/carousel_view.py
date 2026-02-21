# gll_views/carousel_view.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt


@dataclass(frozen=True)
class GameItem:
    id: str
    title: str
    poster_path: Optional[str] = None
    profile_name: str = ""
    tv_badge: str = ""


class LruPixmapCache:
    def __init__(self, capacity: int = 120) -> None:
        self.capacity = max(10, int(capacity))
        self._map: dict[str, QtGui.QPixmap] = {}
        self._order: List[str] = []

    def get(self, key: str) -> Optional[QtGui.QPixmap]:
        pm = self._map.get(key)
        if pm is None:
            return None
        try:
            self._order.remove(key)
        except ValueError:
            pass
        self._order.append(key)
        return pm

    def put(self, key: str, pm: QtGui.QPixmap) -> None:
        if key in self._map:
            self._map[key] = pm
            try:
                self._order.remove(key)
            except ValueError:
                pass
            self._order.append(key)
            return
        self._map[key] = pm
        self._order.append(key)
        while len(self._order) > self.capacity:
            old = self._order.pop(0)
            self._map.pop(old, None)


class CarouselView(QtWidgets.QWidget):
    """
    SAFE TV Carousel:
    - без hero background
    - без фоновых потоков
    - без наклонов
    - snap + анимация + HUD + бейджи
    """

    launchRequested = QtCore.pyqtSignal(object, str)  # (GameItem, mode: "normal"|"quick")
    indexChanged = QtCore.pyqtSignal(int)
    requestProfile = QtCore.pyqtSignal(object)
    requestOptions = QtCore.pyqtSignal(object)
    backRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None, items: Optional[List[GameItem]] = None, loop: bool = True) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self._items: List[GameItem] = items or []
        self._loop = loop

        self._current_index = 0
        self._scroll_offset = 0.0

        # mouse drag / wheel navigation
        self._drag_active = False
        self._drag_start_x = 0
        self._drag_accum = 0

        self._anim = QtCore.QPropertyAnimation(self, b"scrollOffset", self)
        self._anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._anim.setDuration(170)

        self._focus_pulse = 0.0
        self._pulse_anim = QtCore.QPropertyAnimation(self, b"focusPulse", self)
        self._pulse_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)
        self._pulse_anim.setDuration(140)

        # repeat
        self._repeat_timer = QtCore.QTimer(self)
        self._repeat_timer.setInterval(70)
        self._repeat_timer.timeout.connect(self._on_repeat)
        self._repeat_dir = 0
        self._repeat_phase = 0

        # hold-to-launch
        self._hold_timer = QtCore.QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold_fire)
        self._hold_pending = False

        self._pix_cache = LruPixmapCache(160)
        self._placeholder = self._make_placeholder(600, 900)

        # hints
        self._hint_left = "←/D-Pad"
        self._hint_a = "Enter/A: Запуск"
        self._hint_hold = "Hold Enter/A: Быстрый запуск"
        self._hint_y = "Y: Профиль"
        self._hint_x = "X: Параметры"
        self._hint_b = "Esc/B: Назад"

    # Qt properties
    def getScrollOffset(self) -> float:
        return self._scroll_offset

    def setScrollOffset(self, v: float) -> None:
        self._scroll_offset = float(v)
        self.update()

    scrollOffset = QtCore.pyqtProperty(float, fget=getScrollOffset, fset=setScrollOffset)

    def getFocusPulse(self) -> float:
        return self._focus_pulse

    def setFocusPulse(self, v: float) -> None:
        self._focus_pulse = float(v)
        self.update()

    focusPulse = QtCore.pyqtProperty(float, fget=getFocusPulse, fset=setFocusPulse)

    # API
    def setItems(self, items: List[GameItem]) -> None:
        self._items = items or []
        self._current_index = min(self._current_index, max(0, len(self._items) - 1))
        self._scroll_offset = 0.0

        # mouse drag / wheel navigation
        self._drag_active = False
        self._drag_start_x = 0
        self._drag_accum = 0
        self.update()

    def currentItem(self) -> Optional[GameItem]:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return None

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        cw, ch = self._card_size()
        self._placeholder = self._make_placeholder(cw, ch)
        super().resizeEvent(e)

    # Painting
    def paintEvent(self, e: QtGui.QPaintEvent) -> None:
        w = self.width()
        h = self.height()
        if w < 20 or h < 20:
            return

        p = QtGui.QPainter(self)
        p.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing
            | QtGui.QPainter.RenderHint.SmoothPixmapTransform
        )

        p.fillRect(self.rect(), QtGui.QColor(10, 10, 12))

        if not self._items:
            self._paint_empty(p)
            return

        center_x = w * 0.5
        center_y = h * 0.46

        card_w, card_h = self._card_size()
        step_x = card_w * 0.72

        radius = 4
        rels = list(range(-radius, radius + 1))
        rels.sort(key=lambda r: abs(r), reverse=True)

        for rel in rels:
            idx = self._index_at_relative(rel)
            if idx is None:
                continue

            t = rel - self._scroll_offset
            x = center_x + t * step_x
            y = center_y + (abs(t) ** 1.35) * (h * 0.03)

            base_scale = max(0.62, 1.0 - 0.18 * abs(t))
            alpha = max(0.25, 1.0 - 0.22 * abs(t))

            is_current = (rel == 0 and abs(self._scroll_offset) < 0.51)
            pop = 1.0 + (0.020 * self._focus_pulse if is_current else 0.0)
            scale = base_scale * pop

            it = self._items[idx]
            pm = self._load_pixmap(it.poster_path)

            self._paint_card(p, pm, it, x, y, card_w, card_h, scale, alpha, is_current)

        self._paint_hud(p)

    def _paint_empty(self, p: QtGui.QPainter) -> None:
        p.setPen(QtGui.QColor(230, 230, 235))
        f = self.font()
        f.setPointSize(max(12, int(self.height() * 0.018)))
        f.setWeight(QtGui.QFont.Weight.DemiBold)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет игр. Добавь игры в games.json")

    def _paint_card(
        self,
        p: QtGui.QPainter,
        pm: QtGui.QPixmap,
        item: GameItem,
        x: float,
        y: float,
        base_w: int,
        base_h: int,
        scale: float,
        alpha: float,
        is_current: bool,
    ) -> None:
        w = int(base_w * scale)
        h = int(base_h * scale)
        rect = QtCore.QRectF(x - w / 2, y - h / 2, w, h)

        radius = max(14.0, min(28.0, rect.width() * 0.04))

        if is_current:
            shadow = QtGui.QColor(0, 0, 0, 175)
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(8):
                r = rect.adjusted(-6 - i, -6 - i, 6 + i, 6 + i)
                p.setOpacity(0.055)
                p.setBrush(shadow)
                p.drawRoundedRect(r, radius, radius)
            p.restore()

        p.save()
        p.setOpacity(alpha)
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        p.setClipPath(clip)

        if not pm.isNull():
            src = self._center_crop_source(pm, rect.width(), rect.height())
            p.drawPixmap(rect, pm, src)
        else:
            p.fillRect(rect, QtGui.QColor(35, 35, 40))

        grad_h = rect.height() * 0.34
        grad = QtGui.QLinearGradient(rect.left(), rect.bottom() - grad_h, rect.left(), rect.bottom())
        grad.setColorAt(0.0, QtGui.QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QtGui.QColor(0, 0, 0, 210))
        p.fillRect(QtCore.QRectF(rect.left(), rect.bottom() - grad_h, rect.width(), grad_h), grad)

        p.restore()

        if is_current:
            p.save()
            thickness = max(3, int(rect.width() * 0.008))
            p.setPen(QtGui.QPen(QtGui.QColor(235, 235, 255, 235), thickness))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), radius, radius)
            p.restore()

            self._paint_badges(p, rect, item)

    def _paint_badges(self, p: QtGui.QPainter, rect: QtCore.QRectF, item: GameItem) -> None:
        badges: List[str] = []
        if item.profile_name:
            badges.append(item.profile_name)
        if item.tv_badge:
            badges.append(item.tv_badge)
        if not badges:
            return

        p.save()
        font = self.font()
        font.setPointSize(max(10, int(self.height() * 0.014)))
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        p.setFont(font)

        padding_x = rect.width() * 0.030
        padding_y = rect.height() * 0.018
        gap = rect.height() * 0.018

        x = rect.left() + rect.width() * 0.06
        y = rect.bottom() - rect.height() * 0.12

        fm = QtGui.QFontMetrics(font)
        for text in badges:
            tw = fm.horizontalAdvance(text)
            th = fm.height()
            pill_w = tw + int(padding_x * 2)
            pill_h = th + int(padding_y * 1.4)
            pill = QtCore.QRectF(x, y, pill_w, pill_h)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(0, 0, 0, 165))
            p.drawRoundedRect(pill, pill_h * 0.5, pill_h * 0.5)

            p.setPen(QtGui.QColor(245, 245, 250))
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)

            y += pill_h + gap

        p.restore()

    def _paint_hud(self, p: QtGui.QPainter) -> None:
        it = self.currentItem()
        if not it:
            return

        w = self.width()
        h = self.height()

        title_font, sub_font, hint_font = self._fonts()

        hud_h = int(h * 0.26)
        hud_rect = QtCore.QRect(0, h - hud_h, w, hud_h)

        grad = QtGui.QLinearGradient(0, hud_rect.top(), 0, hud_rect.bottom())
        grad.setColorAt(0.0, QtGui.QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QtGui.QColor(0, 0, 0, 220))
        p.fillRect(hud_rect, grad)

        left = int(w * 0.06)
        right = int(w * 0.06)
        top = hud_rect.top() + int(h * 0.02)

        p.setFont(title_font)
        p.setPen(QtGui.QColor(245, 245, 250))
        p.drawText(
            QtCore.QRect(left, top, w - left - right, int(h * 0.07)),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            it.title,
        )

        profile_line = ""
        if it.profile_name:
            profile_line += f"Профиль: {it.profile_name}"
        if it.tv_badge:
            if profile_line:
                profile_line += "   •   "
            profile_line += it.tv_badge

        if profile_line:
            p.setFont(sub_font)
            p.setPen(QtGui.QColor(210, 210, 220))
            p.drawText(
                QtCore.QRect(left, top + int(h * 0.05), w - left - right, int(h * 0.05)),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                profile_line,
            )

        p.setFont(hint_font)
        p.setPen(QtGui.QColor(220, 220, 230))
        hints = f"{self._hint_left}   {self._hint_a}   {self._hint_hold}   {self._hint_y}   {self._hint_x}   {self._hint_b}"
        p.drawText(
            QtCore.QRect(left, hud_rect.bottom() - int(h * 0.045), w - left - right, int(h * 0.04)),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            hints,
        )

    # Input
    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if not self._items:
            super().keyPressEvent(e)
            return

        k = e.key()
        if k in (Qt.Key.Key_Right, Qt.Key.Key_D):
            self._start_repeat(+1)
            self.step(+1)
            e.accept()
            return
        if k in (Qt.Key.Key_Left, Qt.Key.Key_A):
            self._start_repeat(-1)
            self.step(-1)
            e.accept()
            return

        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._hold_pending = True
            self._hold_timer.start(420)
            e.accept()
            return

        if k == Qt.Key.Key_Y:
            it = self.currentItem()
            if it:
                self.requestProfile.emit(it)
            e.accept()
            return

        if k == Qt.Key.Key_X:
            it = self.currentItem()
            if it:
                self.requestOptions.emit(it)
            e.accept()
            return

        if k in (Qt.Key.Key_Escape, Qt.Key.Key_Backspace):
            self.backRequested.emit()
            e.accept()
            return

        super().keyPressEvent(e)

    def wheelEvent(self, e: QtGui.QWheelEvent) -> None:
        if not self._items:
            super().wheelEvent(e)
            return
        delta = e.angleDelta().y()
        if delta == 0:
            return
        # wheel up -> prev, wheel down -> next
        self.step(-1 if delta > 0 else +1)
        e.accept()

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._drag_start_x = int(e.position().x())
            self._drag_accum = 0
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent) -> None:
        if self._drag_active:
            x = int(e.position().x())
            dx = x - self._drag_start_x
            self._drag_start_x = x
            self._drag_accum += dx
            # threshold in px
            if self._drag_accum > 80:
                self.step(-1)
                self._drag_accum = 0
            elif self._drag_accum < -80:
                self.step(+1)
                self._drag_accum = 0
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent) -> None:
        if self._drag_active and e.button() == Qt.MouseButton.LeftButton:
            self._drag_active = False
            self._drag_accum = 0
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def keyReleaseEvent(self, e: QtGui.QKeyEvent) -> None:
        k = e.key()

        if k in (Qt.Key.Key_Right, Qt.Key.Key_Left, Qt.Key.Key_A, Qt.Key.Key_D):
            self._stop_repeat()

        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._hold_timer.isActive():
                self._hold_timer.stop()
                if self._hold_pending:
                    self._hold_pending = False
                    it = self.currentItem()
                    if it:
                        self.launchRequested.emit(it, "normal")
            e.accept()
            return

        super().keyReleaseEvent(e)

    def _on_hold_fire(self) -> None:
        if not self._hold_pending:
            return
        self._hold_pending = False
        it = self.currentItem()
        if it:
            self.launchRequested.emit(it, "quick")

    # Animations
    def step(self, direction: int) -> None:
        if not self._items:
            return
        direction = 1 if direction > 0 else -1
        self._animate_step(direction)

    def _animate_step(self, direction: int) -> None:
        if self._anim.state() == QtCore.QAbstractAnimation.State.Running:
            self._anim.stop()

        self._anim.setStartValue(self._scroll_offset)
        self._anim.setEndValue(float(direction))
        self._anim.finished.connect(
            lambda: self._commit_step(direction),
            type=QtCore.Qt.ConnectionType.SingleShotConnection,
        )
        self._anim.start()

    def _commit_step(self, direction: int) -> None:
        self._current_index = self._clamp_index(self._current_index + direction)
        self._scroll_offset = 0.0

        # mouse drag / wheel navigation
        self._drag_active = False
        self._drag_start_x = 0
        self._drag_accum = 0
        self.indexChanged.emit(self._current_index)
        self._pulse()
        self.update()

    def _pulse(self) -> None:
        if self._pulse_anim.state() == QtCore.QAbstractAnimation.State.Running:
            self._pulse_anim.stop()
        self._pulse_anim.setStartValue(1.0)
        self._pulse_anim.setEndValue(0.0)
        self._pulse_anim.start()

    # Repeat
    def _start_repeat(self, direction: int) -> None:
        self._repeat_dir = 1 if direction > 0 else -1
        self._repeat_phase = 0
        if not self._repeat_timer.isActive():
            QtCore.QTimer.singleShot(320, self._repeat_timer.start)

    def _stop_repeat(self) -> None:
        self._repeat_timer.stop()
        self._repeat_dir = 0
        self._repeat_phase = 0
        self._repeat_timer.setInterval(70)

    def _on_repeat(self) -> None:
        if self._repeat_dir == 0:
            self._repeat_timer.stop()
            return

        self._repeat_phase += 1
        if self._repeat_phase == 10:
            self._repeat_timer.setInterval(55)
        if self._repeat_phase == 25:
            self._repeat_timer.setInterval(40)

        if self._anim.state() != QtCore.QAbstractAnimation.State.Running:
            self.step(self._repeat_dir)

    # Helpers
    def _card_size(self) -> Tuple[int, int]:
        w = max(1, self.width())
        h = max(1, self.height())

        card_h = int(h * 0.52)
        max_w = int(w * 0.28)
        card_w = int(card_h * (2 / 3))
        if card_w > max_w:
            card_w = max_w
            card_h = int(card_w * 1.5)

        card_w = max(220, card_w)
        card_h = max(330, card_h)
        return card_w, card_h

    def _fonts(self) -> Tuple[QtGui.QFont, QtGui.QFont, QtGui.QFont]:
        h = max(1, self.height())
        title_pt = max(16, int(h * 0.028))
        sub_pt = max(11, int(h * 0.016))
        hint_pt = max(10, int(h * 0.014))

        title = self.font()
        title.setPointSize(title_pt)
        title.setWeight(QtGui.QFont.Weight.Bold)

        sub = self.font()
        sub.setPointSize(sub_pt)
        sub.setWeight(QtGui.QFont.Weight.DemiBold)

        hint = self.font()
        hint.setPointSize(hint_pt)
        hint.setWeight(QtGui.QFont.Weight.DemiBold)

        return title, sub, hint

    def _load_pixmap(self, path: Optional[str]) -> QtGui.QPixmap:
        if not path:
            return self._placeholder

        cached = self._pix_cache.get(path)
        if cached is not None:
            return cached

        pm = QtGui.QPixmap(path)
        if pm.isNull():
            pm = self._placeholder

        self._pix_cache.put(path, pm)
        return pm

    def _make_placeholder(self, w: int, h: int) -> QtGui.QPixmap:
        w = max(100, int(w))
        h = max(150, int(h))
        pm = QtGui.QPixmap(w, h)
        pm.fill(QtGui.QColor(30, 30, 34))

        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        grad = QtGui.QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QtGui.QColor(52, 52, 62))
        grad.setColorAt(1.0, QtGui.QColor(20, 20, 24))
        p.fillRect(pm.rect(), grad)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(255, 255, 255, 26))
        r = min(w, h) * 0.22
        p.drawEllipse(QtCore.QPointF(w * 0.5, h * 0.42), r, r)

        p.end()
        return pm

    def _center_crop_source(self, pm: QtGui.QPixmap, target_w: float, target_h: float) -> QtCore.QRectF:
        sw, sh = pm.width(), pm.height()
        if sw <= 0 or sh <= 0:
            return QtCore.QRectF(0, 0, 0, 0)

        target_ratio = float(target_w) / float(target_h)
        src_ratio = float(sw) / float(sh)

        if src_ratio > target_ratio:
            new_w = int(sh * target_ratio)
            x0 = (sw - new_w) // 2
            return QtCore.QRectF(x0, 0, new_w, sh)
        else:
            new_h = int(sw / target_ratio)
            y0 = (sh - new_h) // 2
            return QtCore.QRectF(0, y0, sw, new_h)

    def _clamp_index(self, idx: int) -> int:
        n = len(self._items)
        if n <= 0:
            return 0
        if self._loop:
            return idx % n
        return max(0, min(n - 1, idx))

    def _index_at_relative(self, rel: int) -> Optional[int]:
        n = len(self._items)
        if n <= 0:
            return None
        idx = self._current_index + rel
        if self._loop:
            return idx % n
        if 0 <= idx < n:
            return idx
        return None