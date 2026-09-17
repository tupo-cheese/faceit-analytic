"""Интерактивные графики."""
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QHBoxLayout, QLabel
from src.config import COLORS


class ChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Метрика:"))
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(["ADR", "K/D", "Rating", "Reaction Time", "Preaim", "KAST", "Impact"])
        ctrl.addWidget(self.metric_combo)
        ctrl.addWidget(QLabel("Фильтр:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все матчи", "ELO 2000+", "ELO 2500+", "С друзьями"])
        ctrl.addWidget(self.filter_combo)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        pg.setConfigOption("background", COLORS["bg_secondary"])
        pg.setConfigOption("foreground", COLORS["text_secondary"])
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("left", "Значение")
        self.plot.setLabel("bottom", "Матч")
        layout.addWidget(self.plot)

    def plot_series(self, values, teammates=None):
        self.plot.clear()
        x = list(range(len(values)))
        self.plot.plot(x, values, pen=pg.mkPen(COLORS["accent"], width=2), name="Игрок/враги")
        if teammates:
            self.plot.plot(x, teammates, pen=pg.mkPen(COLORS["purple"], width=2), name="Тиммейты")
        self.plot.addLegend()
