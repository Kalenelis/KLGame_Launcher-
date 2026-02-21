# game_edit_widget.py
from __future__ import annotations

import os
from typing import Dict, Any, Optional, List

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt


def safe_get_open_file(parent, title: str, start_dir: str, filter_str: str) -> str:
    """Безопасный QFileDialog (НЕ native) — часто фиксит 0xC0000409 на Windows/4K/DPI."""
    dlg = QtWidgets.QFileDialog(parent, title, start_dir, filter_str)
    dlg.setOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)
    if dlg.exec():
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""


class FileRuleDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, src: str = "", dst: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Config rule")
        self.setModal(True)
        self.resize(720, 180)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)
        root.addLayout(form)

        self.ed_dst = QtWidgets.QLineEdit(dst)
        self.ed_src = QtWidgets.QLineEdit(src)

        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(self.ed_dst, 1)
        btn_dst = QtWidgets.QToolButton()
        btn_dst.setText("…")
        btn_dst.clicked.connect(self._pick_dst)
        row1.addWidget(btn_dst)
        form.addRow("Target file (dst)", row1)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(self.ed_src, 1)
        btn_src = QtWidgets.QToolButton()
        btn_src.setText("…")
        btn_src.clicked.connect(self._pick_src)
        row2.addWidget(btn_src)
        form.addRow("Source file (src)", row2)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _pick_dst(self) -> None:
        start = os.path.dirname(self.ed_dst.text()) if self.ed_dst.text() else os.getcwd()
        path = safe_get_open_file(self, "Select target config file", start, "All files (*.*)")
        if path:
            self.ed_dst.setText(path)

    def _pick_src(self) -> None:
        start = os.path.dirname(self.ed_src.text()) if self.ed_src.text() else os.getcwd()
        path = safe_get_open_file(self, "Select source config file", start, "All files (*.*)")
        if path:
            self.ed_src.setText(path)

    def values(self) -> Dict[str, str]:
        return {"dst": self.ed_dst.text().strip(), "src": self.ed_src.text().strip()}


class ProfileEditorDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, monitors: Optional[dict] = None, profile_key: str = "", profile: Optional[dict] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit profile — {profile_key}")
        self.setModal(True)
        self.resize(900, 520)
        self.monitors = monitors or {}
        self.profile_key = profile_key
        self.profile: Dict[str, Any] = dict(profile or {})

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # --- display actions ---
        box = QtWidgets.QGroupBox("Display actions")
        root.addWidget(box)
        form = QtWidgets.QFormLayout(box)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.cb_monitor = QtWidgets.QComboBox()
        for mid, name in self.monitors.items():
            self.cb_monitor.addItem(str(name), str(mid))
        cur_mid = str(self.profile.get("monitor_id", "0"))
        idx = self.cb_monitor.findData(cur_mid)
        if idx >= 0:
            self.cb_monitor.setCurrentIndex(idx)
        form.addRow("Target monitor", self.cb_monitor)

        self.cb_window_mode = QtWidgets.QComboBox()
        self.cb_window_mode.addItems(["borderless", "fullscreen", "windowed"])
        cur_wm = str(self.profile.get("window_mode", "borderless"))
        if cur_wm in [self.cb_window_mode.itemText(i) for i in range(self.cb_window_mode.count())]:
            self.cb_window_mode.setCurrentText(cur_wm)
        form.addRow("Window mode", self.cb_window_mode)

        self.chk_move = QtWidgets.QCheckBox("Move window to target monitor")
        self.chk_move.setChecked(bool(self.profile.get("move_window", True)))
        form.addRow("", self.chk_move)

        self.chk_focus = QtWidgets.QCheckBox("Force focus")
        self.chk_focus.setChecked(bool(self.profile.get("force_focus", True)))
        form.addRow("", self.chk_focus)

        # --- rules table ---
        rules_box = QtWidgets.QGroupBox("Config files (rules)")
        root.addWidget(rules_box, 1)
        v = QtWidgets.QVBoxLayout(rules_box)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Enabled", "Target (dst)", "Source (src)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked | QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed)
        v.addWidget(self.table, 1)

        btn_row = QtWidgets.QHBoxLayout()
        v.addLayout(btn_row)
        self.btn_add_rule = QtWidgets.QPushButton("+ Add rule")
        self.btn_edit_rule = QtWidgets.QPushButton("Edit")
        self.btn_del_rule = QtWidgets.QPushButton("Delete")
        btn_row.addWidget(self.btn_add_rule)
        btn_row.addWidget(self.btn_edit_rule)
        btn_row.addWidget(self.btn_del_rule)
        btn_row.addStretch(1)

        self.btn_add_rule.clicked.connect(self._add_rule)
        self.btn_edit_rule.clicked.connect(self._edit_rule)
        self.btn_del_rule.clicked.connect(self._delete_rule)

        # load rules
        self._load_rules()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _load_rules(self) -> None:
        cfgs = self.profile.get("configs", [])
        if not isinstance(cfgs, list):
            cfgs = []
        for c in cfgs:
            if isinstance(c, dict):
                self._append_row(
                    enabled=bool(c.get("enabled", True)),
                    dst=str(c.get("dst", "")),
                    src=str(c.get("src", "")),
                )

    def _append_row(self, enabled: bool, dst: str, src: str) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)

        chk = QtWidgets.QTableWidgetItem()
        chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        chk.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
        self.table.setItem(r, 0, chk)

        it_dst = QtWidgets.QTableWidgetItem(dst)
        it_src = QtWidgets.QTableWidgetItem(src)
        self.table.setItem(r, 1, it_dst)
        self.table.setItem(r, 2, it_src)

    def _selected_row(self) -> int:
        rows = {i.row() for i in self.table.selectedIndexes()}
        return next(iter(rows), -1) if rows else -1

    def _add_rule(self) -> None:
        d = FileRuleDialog(self)
        if d.exec():
            v = d.values()
            if v["src"] and v["dst"]:
                self._append_row(True, v["dst"], v["src"])

    def _edit_rule(self) -> None:
        r = self._selected_row()
        if r < 0:
            return
        enabled = self.table.item(r, 0).checkState() == Qt.CheckState.Checked
        dst = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
        src = self.table.item(r, 2).text() if self.table.item(r, 2) else ""
        d = FileRuleDialog(self, src=src, dst=dst)
        if d.exec():
            v = d.values()
            if v["src"] and v["dst"]:
                self.table.item(r, 1).setText(v["dst"])
                self.table.item(r, 2).setText(v["src"])
                self.table.item(r, 0).setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)

    def _delete_rule(self) -> None:
        r = self._selected_row()
        if r >= 0:
            self.table.removeRow(r)

    def result_profile(self) -> Dict[str, Any]:
        prof = dict(self.profile)
        prof["monitor_id"] = str(self.cb_monitor.currentData() or "0")
        prof["move_window"] = bool(self.chk_move.isChecked())
        prof["force_focus"] = bool(self.chk_focus.isChecked())
        prof["window_mode"] = str(self.cb_window_mode.currentText())

        cfgs: List[Dict[str, Any]] = []
        for r in range(self.table.rowCount()):
            enabled = self.table.item(r, 0).checkState() == Qt.CheckState.Checked
            dst = self.table.item(r, 1).text().strip() if self.table.item(r, 1) else ""
            src = self.table.item(r, 2).text().strip() if self.table.item(r, 2) else ""
            if dst and src:
                cfgs.append({"dst": dst, "src": src, "enabled": enabled})
        prof["configs"] = cfgs
        return prof


class GameEditWidget(QtWidgets.QWidget):
    """
    Editor for one game. Backward compatible with current games.json schema.
    Adds a clean tabbed UI + profile editor with 1..N config rules.
    """
    saved = QtCore.pyqtSignal(dict)     # emits full game_data
    cancelled = QtCore.pyqtSignal()

    def __init__(self, monitors: Optional[dict] = None, parent=None) -> None:
        super().__init__(parent)
        self.monitors = monitors or {}
        self._original_key: Optional[str] = None
        self._game: Dict[str, Any] = {}

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(10)

        # header
        header = QtWidgets.QHBoxLayout()
        root.addLayout(header)

        self.title_label = QtWidgets.QLabel("Edit game")
        self.title_label.setObjectName("EditorTitle")
        header.addWidget(self.title_label)

        header.addStretch(1)

        self.btn_save = QtWidgets.QPushButton("Save")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        header.addWidget(self.btn_save)
        header.addWidget(self.btn_cancel)

        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.cancelled.emit)

        # tabs
        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)

        self._build_general_tab()
        self._build_profiles_tab()
        self._build_media_tab()

    # -------- Tabs --------
    def _build_general_tab(self) -> None:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QFormLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setHorizontalSpacing(10)
        lay.setVerticalSpacing(10)

        self.ed_name = QtWidgets.QLineEdit()
        lay.addRow("Name", self.ed_name)

        exe_row = QtWidgets.QHBoxLayout()
        self.ed_exe = QtWidgets.QLineEdit()
        btn_exe = QtWidgets.QToolButton()
        btn_exe.setText("…")
        btn_exe.clicked.connect(self._pick_exe)
        exe_row.addWidget(self.ed_exe, 1)
        exe_row.addWidget(btn_exe)
        lay.addRow("Exe path", exe_row)

        self.tabs.addTab(w, "General")

    def _build_profiles_tab(self) -> None:
        w = QtWidgets.QWidget()
        root = QtWidgets.QHBoxLayout(w)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.profile_list = QtWidgets.QListWidget()
        self.profile_list.setMinimumWidth(240)
        root.addWidget(self.profile_list, 0)

        right = QtWidgets.QVBoxLayout()
        root.addLayout(right, 1)

        hint = QtWidgets.QLabel("Select a profile and click Edit.\nProfiles are per-monitor launch setups (PC/TV/etc).\nEach profile contains 1..N config file rules.")
        hint.setStyleSheet("color: rgba(220,220,230,0.75);")
        right.addWidget(hint)

        btns = QtWidgets.QHBoxLayout()
        right.addLayout(btns)

        self.btn_add_prof = QtWidgets.QPushButton("+ Add")
        self.btn_dup_prof = QtWidgets.QPushButton("Duplicate")
        self.btn_del_prof = QtWidgets.QPushButton("Delete")
        self.btn_edit_prof = QtWidgets.QPushButton("Edit…")
        btns.addWidget(self.btn_add_prof)
        btns.addWidget(self.btn_dup_prof)
        btns.addWidget(self.btn_del_prof)
        btns.addStretch(1)
        btns.addWidget(self.btn_edit_prof)

        self.profile_info = QtWidgets.QTextEdit()
        self.profile_info.setReadOnly(True)
        right.addWidget(self.profile_info, 1)

        self.btn_add_prof.clicked.connect(self._add_profile)
        self.btn_dup_prof.clicked.connect(self._duplicate_profile)
        self.btn_del_prof.clicked.connect(self._delete_profile)
        self.btn_edit_prof.clicked.connect(self._edit_profile)
        self.profile_list.currentItemChanged.connect(self._update_profile_info)

        self.tabs.addTab(w, "Display Profiles")

    def _build_media_tab(self) -> None:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QFormLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setHorizontalSpacing(10)
        lay.setVerticalSpacing(10)

        icon_row = QtWidgets.QHBoxLayout()
        self.ed_icon = QtWidgets.QLineEdit()
        btn_icon = QtWidgets.QToolButton()
        btn_icon.setText("…")
        btn_icon.clicked.connect(self._pick_icon)
        icon_row.addWidget(self.ed_icon, 1)
        icon_row.addWidget(btn_icon)
        lay.addRow("Icon", icon_row)

        poster_row = QtWidgets.QHBoxLayout()
        self.ed_poster = QtWidgets.QLineEdit()
        btn_poster = QtWidgets.QToolButton()
        btn_poster.setText("…")
        btn_poster.clicked.connect(self._pick_poster)
        poster_row.addWidget(self.ed_poster, 1)
        poster_row.addWidget(btn_poster)
        lay.addRow("Poster", poster_row)

        self.tabs.addTab(w, "Media")

    # -------- Public API --------
    def open_for_new(self) -> None:
        self._original_key = None
        self._game = {
            "name": "",
            "exe_path": "",
            "icon_path": "",
            "poster_path": "",
            "play_time": "0h",
            "monitor_profiles": {},
        }
        self.title_label.setText("Add game")
        self._sync_to_ui()
        self._ensure_default_profiles()

    def open_for_edit(self, key: str, game: Dict[str, Any]) -> None:
        self._original_key = key
        self._game = dict(game or {})
        self.title_label.setText("Edit game")
        self._sync_to_ui()
        self._ensure_default_profiles()

    # -------- Internal helpers --------
    def _sync_to_ui(self) -> None:
        self.ed_name.setText(str(self._game.get("name", "")))
        self.ed_exe.setText(str(self._game.get("exe_path", "")))
        self.ed_icon.setText(str(self._game.get("icon_path", "")))
        self.ed_poster.setText(str(self._game.get("poster_path", "")))

        self._refresh_profile_list()

    def _ensure_default_profiles(self) -> None:
        mp = self._game.get("monitor_profiles")
        if not isinstance(mp, dict):
            mp = {}
        # ensure at least one profile per known monitor id
        if self.monitors:
            for mid in self.monitors.keys():
                key = f"monitor_{mid}"
                if key not in mp:
                    mp[key] = {"monitor_id": str(mid), "fps_limit": 0, "fps_method": "auto", "configs": []}
        self._game["monitor_profiles"] = mp
        self._refresh_profile_list()

    def _refresh_profile_list(self) -> None:
        self.profile_list.clear()
        mp = self._game.get("monitor_profiles") or {}
        if not isinstance(mp, dict):
            mp = {}
        for key, prof in mp.items():
            mon_id = str((prof or {}).get("monitor_id", ""))
            name = self.monitors.get(mon_id) or key
            item = QtWidgets.QListWidgetItem(f"{name}  ({key})")
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.profile_list.addItem(item)
        if self.profile_list.count():
            self.profile_list.setCurrentRow(0)

    def _current_profile_key(self) -> Optional[str]:
        it = self.profile_list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _update_profile_info(self) -> None:
        key = self._current_profile_key()
        mp = self._game.get("monitor_profiles") or {}
        if not key or key not in mp:
            self.profile_info.setPlainText("")
            return
        p = mp[key] or {}
        cfgs = p.get("configs", [])
        ccount = len(cfgs) if isinstance(cfgs, list) else 0
        txt = (
            f"Key: {key}\n"
            f"Monitor: {self.monitors.get(str(p.get('monitor_id','')), str(p.get('monitor_id','')))}\n"
            f"Window: {p.get('window_mode','borderless')}\n"
            f"Move window: {bool(p.get('move_window', True))}\n"
            f"Force focus: {bool(p.get('force_focus', True))}\n"
            f"Config rules: {ccount}\n"
        )
        self.profile_info.setPlainText(txt)

    # -------- Actions --------
    def _add_profile(self) -> None:
        # create with next index
        mp = self._game.get("monitor_profiles") or {}
        if not isinstance(mp, dict):
            mp = {}
        i = 0
        while f"profile_{i}" in mp:
            i += 1
        key = f"profile_{i}"
        # default monitor 0
        default_mid = next(iter(self.monitors.keys()), "0")
        mp[key] = {"monitor_id": str(default_mid), "fps_limit": 0, "fps_method": "auto", "configs": []}
        self._game["monitor_profiles"] = mp
        self._refresh_profile_list()

    def _duplicate_profile(self) -> None:
        key = self._current_profile_key()
        mp = self._game.get("monitor_profiles") or {}
        if not key or key not in mp:
            return
        src = dict(mp[key] or {})
        i = 0
        while f"{key}_copy{i}" in mp:
            i += 1
        mp[f"{key}_copy{i}"] = src
        self._refresh_profile_list()

    def _delete_profile(self) -> None:
        key = self._current_profile_key()
        mp = self._game.get("monitor_profiles") or {}
        if not key or key not in mp:
            return
        if QtWidgets.QMessageBox.question(self, "Delete profile", f"Delete {key}?") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        mp.pop(key, None)
        self._refresh_profile_list()

    def _edit_profile(self) -> None:
        key = self._current_profile_key()
        mp = self._game.get("monitor_profiles") or {}
        if not key or key not in mp:
            return
        d = ProfileEditorDialog(self, monitors=self.monitors, profile_key=key, profile=mp[key])
        if d.exec():
            mp[key] = d.result_profile()
            self._game["monitor_profiles"] = mp
            self._refresh_profile_list()

    # -------- Browsers --------
    def _pick_exe(self) -> None:
        start = os.path.dirname(self.ed_exe.text()) if self.ed_exe.text() else os.getcwd()
        path = safe_get_open_file(self, "Select game executable", start, "Executables (*.exe);;All files (*.*)")
        if path:
            self.ed_exe.setText(path)

    def _pick_icon(self) -> None:
        start = os.path.dirname(self.ed_icon.text()) if self.ed_icon.text() else os.getcwd()
        path = safe_get_open_file(self, "Select icon", start, "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)")
        if path:
            self.ed_icon.setText(path)

    def _pick_poster(self) -> None:
        start = os.path.dirname(self.ed_poster.text()) if self.ed_poster.text() else os.getcwd()
        path = safe_get_open_file(self, "Select poster", start, "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)")
        if path:
            self.ed_poster.setText(path)

    # -------- Save/Cancel --------
    def _on_save(self) -> None:
        self._game["name"] = self.ed_name.text().strip()
        self._game["exe_path"] = self.ed_exe.text().strip()
        self._game["icon_path"] = self.ed_icon.text().strip()
        self._game["poster_path"] = self.ed_poster.text().strip()
        if "play_time" not in self._game:
            self._game["play_time"] = "0h"
        if "monitor_profiles" not in self._game:
            self._game["monitor_profiles"] = {}
        self.saved.emit(self._game)
