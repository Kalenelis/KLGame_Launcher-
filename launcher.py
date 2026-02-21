# launcher.py
from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from core.profile_manager import LastProfileStore, compute_game_id, game_to_profiles
from core.launch_pipeline import LaunchPipeline


# --- Optional imports (не ломаем запуск если файлов нет)
try:
    from game_tile import GameTile
except Exception:
    GameTile = None  # type: ignore

try:
    from game_edit_widget import GameEditWidget
except Exception:
    GameEditWidget = None  # type: ignore

try:
    from gll_views.carousel_view import CarouselView, GameItem
except Exception:
    CarouselView = None  # type: ignore
    GameItem = None  # type: ignore


def load_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path: str, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_games(path: str) -> Dict[str, dict]:
    data = load_json(path, {})
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if isinstance(v, dict):
                g = dict(v)
                g.setdefault("name", v.get("name", k))
                out[g["name"]] = g
        return out
    out = {}
    if isinstance(data, list):
        for v in data:
            if isinstance(v, dict) and v.get("name"):
                out[v["name"]] = v
    return out



class _WaitProcessWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal()

    def __init__(self, proc, session, pipeline) -> None:
        super().__init__()
        self.proc = proc
        self.session = session
        self.pipeline = pipeline

    def run(self) -> None:
        try:
            self.proc.wait()
        finally:
            try:
                self.pipeline.restore(self.session)
            except Exception:
                pass
            self.finished.emit()


class GameLauncher(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GLL")
        self.resize(1400, 820)

        base = os.path.dirname(__file__)
        self.games_path = os.path.join(base, "games.json")
        self.monitors_path = os.path.join(base, "monitors.json")
        self.last_profiles_path = os.path.join(base, "last_profiles.json")
        self.backups_root = os.path.join(base, "backups")

        self.last_profiles = LastProfileStore(self.last_profiles_path)
        self.pipeline = LaunchPipeline(self.backups_root)

        self.games: Dict[str, dict] = load_games(self.games_path)
        self.monitors: dict = load_json(self.monitors_path, {})

        root = QtWidgets.QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        self.v = QtWidgets.QVBoxLayout(root)
        self.v.setContentsMargins(0, 0, 0, 0)
        self.v.setSpacing(0)

        # predefine optional pages before building topbar (avoid AttributeError)
        self.carousel_view = None
        self.editor = None

        self._build_topbar()

        self.content = QtWidgets.QWidget()
        self.content.setObjectName("Content")
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(18, 14, 18, 18)
        self.content_layout.setSpacing(10)
        self.v.addWidget(self.content, 1)

        self.stack = QtWidgets.QStackedWidget()
        self.content_layout.addWidget(self.stack, 1)

        # ---------- GRID PAGE ----------
        self.grid_container = QtWidgets.QWidget()
        self.grid_container.setObjectName("GridContainer")
        self.grid_layout = QtWidgets.QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(18)
        self.grid_layout.setVerticalSpacing(18)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.grid_scroll = QtWidgets.QScrollArea()
        self.grid_scroll.setObjectName("GridScroll")
        self.grid_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setWidget(self.grid_container)
        self.stack.addWidget(self.grid_scroll)

        # ---------- LIST PAGE ----------
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.itemActivated.connect(self._on_list_activated)
        self.list_widget.setObjectName("GameList")
        self.stack.addWidget(self.list_widget)

        # ---------- CAROUSEL PAGE (optional) ----------
        self.carousel_view = None
        if CarouselView is not None:
            self.carousel_view = CarouselView(loop=True)
            self.carousel_view.launchRequested.connect(self._on_carousel_launch)
            self.carousel_view.requestProfile.connect(self._on_carousel_profile)
            self.carousel_view.backRequested.connect(lambda: self.set_view('grid'))
            self.stack.addWidget(self.carousel_view)
            # show carousel tab now that view exists
            if hasattr(self, 'btn_carousel'):
                self.btn_carousel.show()

        # ---------- EDITOR PAGE (optional) ----------
        self.editor = None
        if GameEditWidget is not None:
            self.editor = GameEditWidget(monitors=self.monitors)
            self.editor.saved.connect(self._on_editor_saved)
            self.editor.cancelled.connect(lambda: self.set_view("grid"))
            self.stack.addWidget(self.editor)

        # default
        self.set_view("grid")

        # reflow on resize
        self._grid_reflow_timer = QtCore.QTimer(self)
        self._grid_reflow_timer.setSingleShot(True)
        self._grid_reflow_timer.timeout.connect(self.render_grid)

        self.refresh()

    # ---------------- Topbar ----------------
    def _build_topbar(self) -> None:
        bar = QtWidgets.QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(62)
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(12)

        self.logo = QtWidgets.QLabel("GLL")
        self.logo.setObjectName("Logo")
        lay.addWidget(self.logo)

        lay.addStretch(1)

        self.btn_grid = QtWidgets.QPushButton("Grid")
        self.btn_list = QtWidgets.QPushButton("List")
        self.btn_carousel = QtWidgets.QPushButton("Carousel")

        for b in (self.btn_grid, self.btn_list, self.btn_carousel):
            b.setObjectName("TabButton")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            lay.addWidget(b)

        # если карусели нет — прячем таб
        if self.carousel_view is None:
            self.btn_carousel.hide()

        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.addButton(self.btn_grid)
        self.group.addButton(self.btn_list)
        self.group.addButton(self.btn_carousel)

        self.btn_grid.clicked.connect(lambda: self.set_view("grid"))
        self.btn_list.clicked.connect(lambda: self.set_view("list"))
        self.btn_carousel.clicked.connect(lambda: self.set_view("carousel"))

        lay.addStretch(1)

        self.btn_add = QtWidgets.QPushButton("Add game")
        self.btn_tv = QtWidgets.QPushButton("TV")
        self.btn_settings = QtWidgets.QPushButton("Settings")
        self.btn_reload = QtWidgets.QPushButton("Reload")

        for b in (self.btn_add, self.btn_tv, self.btn_settings, self.btn_reload):
            b.setObjectName("TopButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            lay.addWidget(b)

        self.btn_reload.clicked.connect(self.reload)
        self.btn_add.clicked.connect(self.add_game)
        self.btn_tv.clicked.connect(self.enter_tv_mode)

        self.v.addWidget(bar)

    # ---------------- View switching ----------------
    def set_view(self, mode: str) -> None:
        if mode == "grid":
            self.stack.setCurrentWidget(self.grid_scroll)
            self.btn_grid.setChecked(True)
        elif mode == "list":
            self.stack.setCurrentWidget(self.list_widget)
            self.btn_list.setChecked(True)
        elif mode == "carousel" and self.carousel_view is not None:
            self.stack.setCurrentWidget(self.carousel_view)
            self.btn_carousel.setChecked(True)
        else:
            self.stack.setCurrentWidget(self.grid_scroll)
            self.btn_grid.setChecked(True)

    # ---------------- Data actions ----------------
    def reload(self) -> None:
        self.games = load_games(self.games_path)
        self.refresh()

    def refresh(self) -> None:
        self.render_list()
        self.render_grid()
        self._refresh_carousel()

    # ---------------- Render list ----------------
    def render_list(self) -> None:
        self.list_widget.clear()
        for name in sorted(self.games.keys(), key=lambda x: x.lower()):
            self.list_widget.addItem(name)

    # ---------------- Render grid ----------------
    def render_grid(self) -> None:
        # clear
        while self.grid_layout.count():
            it = self.grid_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        names = sorted(self.games.keys(), key=lambda x: x.lower())
        if not names or GameTile is None:
            lbl = QtWidgets.QLabel("Нет игр (или не найден game_tile.py).")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.grid_layout.addWidget(lbl, 0, 0)
            return

        viewport_w = self.grid_scroll.viewport().width()
        tile_w, tile_h = 240, 360
        spacing = self.grid_layout.horizontalSpacing()

        cols = max(2, min(7, int((max(400, viewport_w) + spacing) / (tile_w + spacing))))

        row = col = 0
        for name in names:
            g = self.games[name]
            tile = GameTile(g, width=tile_w, height=tile_h, get_monitor_name=self.get_monitor_name)
            tile.clicked.connect(self._on_tile_launch)
            tile.edit_clicked.connect(self._on_tile_edit)
            tile.delete_clicked.connect(self._on_tile_delete)
            self.grid_layout.addWidget(tile, row, col)

            col += 1
            if col >= cols:
                col = 0
                row += 1

        self.grid_layout.setRowStretch(row + 1, 1)

    

    def _refresh_carousel(self) -> None:
        if self.carousel_view is None or GameItem is None:
            return
        items = []
        for name in sorted(self.games.keys(), key=lambda x: x.lower()):
            g = self.games[name]
            gid = compute_game_id(g)
            last_mid = self.last_profiles.get(gid) or ""
            prof_name = self.get_monitor_name(last_mid) if last_mid else ""
            items.append(GameItem(
                id=name,
                title=str(g.get("name", name)),
                poster_path=g.get("poster_path"),
                profile_name=prof_name,
                tv_badge="TV" if "tv" in (prof_name or "").lower() else ""
            ))
        self.carousel_view.setItems(items)
    def get_monitor_name(self, monitor_id: Any) -> str:
        return str(self.monitors.get(str(monitor_id), f"monitor_{monitor_id}"))

    # ---------------- Add game (optional) ----------------
    def add_game(self) -> None:
        if self.editor is None:
            QtWidgets.QMessageBox.information(self, "Add game", "Editor not found (game_edit_widget.py).")
            return
        self.editor.open_for_new()
        self.stack.setCurrentWidget(self.editor)



    # ---------------- Launch handling ----------------
    def _on_tile_launch(self, payload) -> None:
        """
        payload can be (game_data, profile_key) from GameTile
        """
        try:
            game, profile_key = payload
        except Exception:
            game, profile_key = payload, None

        if not isinstance(game, dict):
            return

        # choose profile
        mp = game.get("monitor_profiles", {}) or {}
        if profile_key and profile_key in mp:
            prof = mp[profile_key]
        else:
            # fallback to last monitor id (stored), else first profile
            gid = compute_game_id(game)
            last_mid = self.last_profiles.get(gid)
            prof = None
            if last_mid is not None:
                for _k, _p in mp.items():
                    if str((_p or {}).get("monitor_id", "")) == str(last_mid):
                        prof = _p
                        profile_key = _k
                        break
            if prof is None and isinstance(mp, dict) and mp:
                profile_key, prof = next(iter(mp.items()))

        if not isinstance(prof, dict):
            QtWidgets.QMessageBox.warning(self, "Launch", "No profile found for this game.")
            return

        # remember last
        gid = compute_game_id(game)
        self.last_profiles.set(gid, str(prof.get("monitor_id", "0")))

        # build DisplayProfile and launch
        profiles = game_to_profiles(game, self.monitors)
        dp = next((p for p in profiles if p.key == profile_key), None)
        if dp is None:
            # create minimal
            from core.profile_manager import DisplayProfile, FileRule
            cfgs = prof.get("configs", [])
            rules=[]
            if isinstance(cfgs, list):
                for c in cfgs:
                    if isinstance(c, dict) and c.get("src") and c.get("dst"):
                        rules.append(FileRule(src=str(c["src"]), dst=str(c["dst"]), enabled=bool(c.get("enabled", True))))
            dp = DisplayProfile(key=str(profile_key or "profile"), name=str(profile_key or "profile"),
                                monitor_id=str(prof.get("monitor_id","0")),
                                move_window=bool(prof.get("move_window", True)),
                                force_focus=bool(prof.get("force_focus", True)),
                                window_mode=str(prof.get("window_mode","borderless")),
                                rules=rules)

        try:
            proc, session = self.pipeline.launch_with_session(game, dp)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Launch error", str(e))
            return

        # wait in background thread so UI doesn't freeze
        th = QtCore.QThread(self)
        worker = _WaitProcessWorker(proc, session, self.pipeline)
        worker.moveToThread(th)
        th.started.connect(worker.run)
        worker.finished.connect(th.quit)
        worker.finished.connect(worker.deleteLater)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_tile_edit(self, game: dict) -> None:
        if self.editor is None:
            return
        key = str(game.get("name", "")) or None
        if key and key in self.games:
            self.editor.open_for_edit(key, self.games[key])
        else:
            self.editor.open_for_edit(key or "", game)
        self.editor.open_for_new()
        self.stack.setCurrentWidget(self.editor)

    def _on_tile_delete(self, name: str) -> None:
        name = str(name or "")
        if not name:
            return
        if QtWidgets.QMessageBox.question(self, "Delete game", f"Delete '{name}'?") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.games.pop(name, None)
        save_json(self.games_path, self.games)
        self.refresh()

    def _on_list_activated(self, item: QtWidgets.QListWidgetItem) -> None:
        name = item.text()
        g = self.games.get(name)
        if g:
            self._on_tile_launch((g, None))

    def _on_editor_saved(self, game: dict) -> None:
        # key in games.json is game name
        name = str(game.get("name", "")).strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Save", "Game name is empty.")
            return
        self.games[name] = game
        save_json(self.games_path, self.games)
        self.refresh()
        self.set_view("grid")

    
    def _on_carousel_launch(self, item, mode: str = "normal") -> None:
        # item.id stores game key (name)
        name = getattr(item, "id", None) or getattr(item, "title", None)
        if not name:
            return
        g = self.games.get(str(name))
        if not g:
            return
        self._on_tile_launch((g, None))

    def _on_carousel_profile(self, item) -> None:
        name = getattr(item, "id", None) or getattr(item, "title", None)
        g = self.games.get(str(name)) if name else None
        if not g:
            return
        # simple picker dialog by monitor profile key
        mp = g.get("monitor_profiles", {}) or {}
        keys = list(mp.keys())
        if not keys:
            return
        labels = []
        for k in keys:
            mid = str((mp[k] or {}).get("monitor_id", ""))
            labels.append(f"{self.get_monitor_name(mid)} — {k}")
        choice, ok = QtWidgets.QInputDialog.getItem(self, "Select profile", "Profile:", labels, 0, False)
        if not ok:
            return
        sel_idx = labels.index(choice)
        self._on_tile_launch((g, keys[sel_idx]))
# ---------------- TV mode ----------------
    def enter_tv_mode(self) -> None:
        if self.carousel_view is None:
            return
        self.set_view("carousel")
        self.showFullScreen()
        self.carousel_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            e.accept()
            return
        super().keyPressEvent(e)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.stack.currentWidget() == self.grid_scroll:
            self._grid_reflow_timer.start(80)