from __future__ import annotations

from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt


class ListGameItemWidget(QtWidgets.QFrame):
    def __init__(self, title: str, subtitle: str = "", icon_path: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ListGameItemWidget")
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        self.icon = QtWidgets.QLabel()
        self.icon.setFixedSize(56, 56)
        self.icon.setScaledContents(True)

        if icon_path:
            pm = QtGui.QPixmap(icon_path)
            if not pm.isNull():
                self.icon.setPixmap(pm.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)

        v = QtWidgets.QVBoxLayout()
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        self.title = QtWidgets.QLabel(title)
        f = self.title.font()
        f.setPointSize(max(12, f.pointSize()))
        f.setWeight(QtGui.QFont.Weight.DemiBold)
        self.title.setFont(f)

        self.sub = QtWidgets.QLabel(subtitle)
        self.sub.setStyleSheet("color: #aab3c7;")
        self.sub.setWordWrap(True)

        v.addWidget(self.title)
        if subtitle:
            v.addWidget(self.sub)

        lay.addLayout(v, 1)

        # right hint
        self.hint = QtWidgets.QLabel("Enter: Play   Double-click: Play   Right-click: Menu")
        self.hint.setStyleSheet("color: #7d879b;")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.hint, 0, Qt.AlignmentFlag.AlignVCenter)

        # subtle background for widget itself (selection still handled by QListWidget)
        self.setStyleSheet("""
        #ListGameItemWidget {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 14px;
        }
        """)
