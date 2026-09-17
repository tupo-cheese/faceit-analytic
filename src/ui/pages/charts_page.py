"""Страница графиков."""
from PySide6.QtWidgets import QWidget, QVBoxLayout
from src.ui.widgets.chart_widget import ChartWidget


class ChartsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.chart = ChartWidget()
        layout.addWidget(self.chart)
