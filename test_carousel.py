import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame, QLabel, QPushButton
)
from PyQt6.QtCore import Qt

class TestTile(QFrame):
    def __init__(self, text, width, height, color):
        super().__init__()
        self.setFixedSize(width, height)
        self.setStyleSheet(f"background-color: {color}; border: 2px solid white; border-radius: 10px;")
        layout = QVBoxLayout()
        label = QLabel(text)
        label.setStyleSheet("color: white; font-size: 16px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)

class TestCarousel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Carousel")
        self.resize(800, 400)
        self.setStyleSheet("background-color: #0e1115;")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Параметры
        base_width, base_height = 200, 300
        selected_width, selected_height = int(base_width * 1.15), int(base_height * 1.15)

        # Контейнер с фиксированной высотой (равной высоте увеличенной плитки)
        container = QWidget()
        container.setFixedHeight(selected_height)
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(150, 0, 0, 0)  # отступ слева
        container_layout.setSpacing(0)

        # Создаём плитки
        tiles_data = [
            ("Left", selected_width, selected_height, "#2b5e8c"),
            ("Middle", base_width, base_height, "#4a4a4a"),
            ("Right", base_width, base_height, "#4a4a4a")
        ]

        for i, (text, w, h, color) in enumerate(tiles_data):
            tile = TestTile(text, w, h, color)
            container_layout.addWidget(tile, alignment=Qt.AlignmentFlag.AlignTop)

            # Добавляем промежуток после каждой плитки, кроме последней
            if i < len(tiles_data) - 1:
                spacer = QFrame()
                spacer.setFixedWidth(60 if i == 0 else 20)
                spacer.setStyleSheet("background: transparent;")
                container_layout.addWidget(spacer)

        # Скролл
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(container)
        scroll.setStyleSheet("QScrollArea { background-color: #0e1115; border: none; }")

        layout.addWidget(scroll)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestCarousel()
    window.show()
    sys.exit(app.exec())