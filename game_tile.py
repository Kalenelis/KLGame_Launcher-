# game_tile.py
from __future__ import annotations

import os
from typing import Optional, Any, Dict

from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QPushButton, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPixmap

from translations import tr


class GameTile(QFrame):
    # launcher.py ожидает эти сигналы
    clicked = pyqtSignal(object)         # (game_data, profile_key) or game_data
    edit_clicked = pyqtSignal(dict)      # game_data
    delete_clicked = pyqtSignal(str)     # game_name
    shortcut_clicked = pyqtSignal(dict)  # game_data

    def __init__(self, game_data: Dict[str, Any], width=220, height=320, get_monitor_name=None):
        super().__init__()
        self.game_data = game_data
        self.get_monitor_name = get_monitor_name

        self.setFixedSize(width, height)
        self.setObjectName("gameTile")

        # ===== Layout =====
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== POSTER =====
        self.poster_label = QLabel()
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setMinimumHeight(int(height * 0.78))
        main_layout.addWidget(self.poster_label)

        # ===== BOTTOM INFO =====
        bottom = QFrame()
        bottom.setStyleSheet("""
            QFrame {
                background-color: #15181e;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(8, 6, 8, 6)
        bottom_layout.setSpacing(2)

        self.name_label = QLabel(game_data.get("name", ""))
        self.name_label.setStyleSheet("color: white; font-weight: bold;")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)

        play_time = game_data.get("play_time", "0h")
        configs_count = sum(len(p.get("configs", [])) for p in game_data.get("monitor_profiles", {}).values())

        self.stats_label = QLabel(f"{play_time}  {tr('configs', configs_count)}")
        self.stats_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        bottom_layout.addWidget(self.name_label)
        bottom_layout.addWidget(self.stats_label)

        main_layout.addWidget(bottom)

        # ===== OVERLAY (only on poster area) =====
        self.overlay = QWidget(self)
        self.overlay.setStyleSheet("background-color: rgba(0,0,0,180);")
        self.overlay.hide()

        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.setContentsMargins(18, 18, 18, 18)
        overlay_layout.setSpacing(12)

        # profile panel
        self.profile_panel = QFrame()
        self.profile_panel.setObjectName("profilePanel")
        panel_layout = QVBoxLayout(self.profile_panel)
        panel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.setSpacing(10)
        panel_layout.setContentsMargins(16, 16, 16, 16)

        overlay_layout.addWidget(self.profile_panel)

        # profile buttons
        self.profile_buttons: list[QPushButton] = []
        monitor_profiles = game_data.get("monitor_profiles", {}) or {}

        for key, profile in monitor_profiles.items():
            mon_id = profile.get("monitor_id")
            display_name = None

            if self.get_monitor_name and mon_id is not None:
                display_name = self.get_monitor_name(mon_id)

            if not display_name:
                display_name = key

            fps_limit = profile.get("fps_limit", 0)
            fps_method = profile.get("fps_method", "auto")

            btn = QPushButton(f"{display_name}\n{fps_limit} FPS / {fps_method}")
            btn.setObjectName("profileButton")
            btn.setMinimumHeight(50)
            btn.setMinimumWidth(230)
            btn.clicked.connect(lambda checked=False, k=key: self._emit_launch_profile(k))

            panel_layout.addWidget(btn)
            self.profile_buttons.append(btn)

        # action row (Configure / Delete) -> 2 equal columns, no truncation
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.setContentsMargins(0, 6, 0, 0)

        self.btn_configure = QPushButton(tr("configure"))
        self.btn_configure.setObjectName("secondaryButton")
        self.btn_configure.setMinimumHeight(42)
        self.btn_configure.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                         QtWidgets.QSizePolicy.Policy.Fixed)
        self.btn_configure.setText("Настроить")  # чтобы точно было как ты ожидаешь
        self.btn_configure.clicked.connect(lambda: self.edit_clicked.emit(self.game_data))

        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.setObjectName("secondaryButton")
        self.btn_delete.setMinimumHeight(42)
        self.btn_delete.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                      QtWidgets.QSizePolicy.Policy.Fixed)
        self.btn_delete.clicked.connect(self._emit_delete)

        action_row.addWidget(self.btn_configure, 1)
        action_row.addWidget(self.btn_delete, 1)

        panel_layout.addLayout(action_row)

        # load poster
        self._poster_pixmap: Optional[QPixmap] = None
        self.load_poster()

        # enable hover tracking
        self.setMouseTracking(True)
        self.poster_label.setMouseTracking(True)
        self.overlay.setMouseTracking(True)

    # ===== Signals helpers =====
    def _emit_launch_profile(self, profile_key: str) -> None:
        self.clicked.emit((self.game_data, profile_key))

    def _emit_delete(self) -> None:
        name = self.game_data.get("name", "")
        self.delete_clicked.emit(name)

    # ===== Poster (no stretching) =====
    def load_poster(self) -> None:
        self._poster_pixmap = None

        poster_path = self.game_data.get("poster_path", "")
        if poster_path and os.path.exists(poster_path):
            pm = QPixmap(poster_path)
            if not pm.isNull():
                self._poster_pixmap = pm

        if self._poster_pixmap is None:
            icon_path = self.game_data.get("icon_path", "")
            if icon_path and os.path.exists(icon_path):
                pm = QPixmap(icon_path)
                if not pm.isNull():
                    self._poster_pixmap = pm

        if self._poster_pixmap is None:
            self.poster_label.setPixmap(QPixmap())
            self.poster_label.setText("🎮")
            self.poster_label.setStyleSheet("font-size: 64px; color: white;")
            return

        self.poster_label.setText("")
        self._update_poster()

    def _update_poster(self) -> None:
        pm = self._poster_pixmap
        if pm is None or pm.isNull():
            return
        w = self.poster_label.width()
        h = self.poster_label.height()
        if w < 10 or h < 10:
            return
        self.poster_label.setPixmap(self._center_crop(pm, w, h))

    def _center_crop(self, pm: QPixmap, tw: int, th: int) -> QPixmap:
        sw, sh = pm.width(), pm.height()
        if sw <= 0 or sh <= 0:
            return pm

        target_ratio = tw / th
        src_ratio = sw / sh

        if src_ratio > target_ratio:
            new_w = int(sh * target_ratio)
            x0 = (sw - new_w) // 2
            src = QRect(x0, 0, new_w, sh)
        else:
            new_h = int(sw / target_ratio)
            y0 = (sh - new_h) // 2
            src = QRect(0, y0, sw, new_h)

        return pm.copy(src).scaled(
            tw, th,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

    # ===== Events =====
    def resizeEvent(self, event):
        # overlay only over poster area
        self.overlay.setGeometry(0, 0, self.width(), self.poster_label.height())
        self._update_poster()
        super().resizeEvent(event)

    def enterEvent(self, event):
        self.overlay.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.overlay.hide()
        super().leaveEvent(event)