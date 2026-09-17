"""Список аномалий."""
from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from src.config import COLORS


class AnomalyList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)

    def set_anomalies(self, anomalies):
        self.clear()
        if not anomalies:
            item = QListWidgetItem("✅ Аномалий не обнаружено")
            self.addItem(item)
            return
        for a in anomalies:
            t = a.get("type", "")
            v = a.get("value", 0)
            sigma = a.get("sigma", 0)
            text = f"⚠️ {t}: {v} (отклонение {sigma}σ)"
            self.addItem(QListWidgetItem(text))
