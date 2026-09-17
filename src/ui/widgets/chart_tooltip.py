"""Кастомный tooltip для графика."""
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QApplication)
from PySide6.QtCore import Qt, Signal
from src.config import COLORS


class ChartTooltip(QFrame):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedWidth(320)
        self.setStyleSheet(f"""
            ChartTooltip {{
                background-color: {COLORS['bg_secondary']};
                border: 2px solid {COLORS['accent']};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.title = QLabel("")
        self.title.setStyleSheet(
            f"color: {COLORS['accent']}; font-weight: 700; font-size: 13px; "
            "background: transparent;")
        header.addWidget(self.title, 1)
        self.btn_close = QPushButton("✕ ПКМ")
        self.btn_close.setToolTip("Закрыть (правый клик на графике)")
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_tertiary']};
                color: {COLORS['text_secondary']};
                border: none; border-radius: 4px;
                padding: 2px 8px; font-size: 10px;
            }}
            QPushButton:hover {{
                background: {COLORS['danger']}; color: white;
            }}
        """)
        self.btn_close.clicked.connect(self.hide_tooltip)
        header.addWidget(self.btn_close)
        layout.addLayout(header)

        self.subtitle = QLabel("")
        self.subtitle.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            "background: transparent;")
        layout.addWidget(self.subtitle)

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(3)
        layout.addLayout(self.rows_layout)

        self.hint = QLabel("Клик по значению — копировать в буфер")
        self.hint.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 10px; "
            "font-style: italic; background: transparent;")
        layout.addWidget(self.hint)

        self._rows = []

    def set_data(self, title, subtitle, rows):
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.subtitle.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            "background: transparent;")

        for row in self._rows:
            row.setParent(None)
        self._rows = []

        for label, value in rows:
            row = self._make_row(label, value)
            self.rows_layout.addWidget(row)
            self._rows.append(row)

        self.adjustSize()

    def _make_row(self, label, value):
        row = QFrame()
        row.setCursor(Qt.PointingHandCursor)
        row.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_tertiary']};
                border-radius: 4px;
            }}
            QFrame:hover {{
                background: {COLORS['border']};
            }}
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            "background: transparent;")
        rl.addWidget(lbl)
        rl.addStretch()
        val = QLabel(str(value))
        val.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-weight: 600; "
            "font-size: 11px; background: transparent;")
        rl.addWidget(val)
        text_to_copy = f"{label}: {value}"
        row.mousePressEvent = lambda e: self._copy(text_to_copy)
        row.setToolTip(f"Клик — копировать «{text_to_copy}»")
        return row

    def _copy(self, text):
        QApplication.clipboard().setText(text)
        self.subtitle.setText("✓ Скопировано")
        self.subtitle.setStyleSheet(
            f"color: {COLORS['success']}; font-size: 11px; "
            "background: transparent;")

    def show_at(self, pos):
        self.move(pos)
        self.show()
        self.raise_()

    def hide_tooltip(self):
        self.hide()
        self.closed.emit()
