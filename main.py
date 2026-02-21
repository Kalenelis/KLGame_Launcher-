import os
import sys
from PyQt6 import QtWidgets

# если на ТВ/DPI бывают краши, пусть будет безопасный режим
os.environ.setdefault("QT_OPENGL", "software")

from launcher import GameLauncher  # noqa: E402


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GLL")

    qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    w = GameLauncher()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())