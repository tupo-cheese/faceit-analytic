"""Мини-график (sparkline) для QuickPage."""
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt
import pyqtgraph as pg
from src.config import COLORS


class MiniChart(QWidget):
    """Компактный линейный график."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        pg.setConfigOption("background", "transparent")
        pg.setConfigOption("foreground", COLORS["text_secondary"])
        self.plot = pg.PlotWidget()
        self.plot.setBackground(None)
        self.plot.hideAxis("bottom")
        self.plot.hideAxis("left")
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMenuEnabled(False)
        layout.addWidget(self.plot)

    def set_data(self, values):
        self.plot.clear()
        if not values:
            return
        x = list(range(len(values)))
        self.plot.plot(x, values, pen=pg.mkPen(COLORS["accent"], width=1.5))
