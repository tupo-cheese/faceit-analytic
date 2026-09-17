"""Карточка метрики — StatBox."""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from src.config import COLORS


class StatBox(QFrame):
    """Мини-карточка с метрикой."""

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            StatBox {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            StatBox:hover {{
                border: 1px solid {COLORS['accent']};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.label = QLabel(label)
        self.label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 12px; "
            "font-weight: 500;")
        layout.addWidget(self.label)

        self.value = QLabel("—")
        self.value.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 22px; "
            "font-weight: 700;")
        layout.addWidget(self.value)

        self.sub = QLabel("")
        self.sub.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(self.sub)

    def set(self, value, color=None, sub=""):
        self.value.setText(str(value))
        if color:
            self.value.setStyleSheet(
                f"color: {color}; font-size: 22px; font-weight: 700;")
        else:
            self.value.setStyleSheet(
                f"color: {COLORS['text_primary']}; font-size: 22px; "
                "font-weight: 700;")
        self.sub.setText(sub)
