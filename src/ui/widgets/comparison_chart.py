"""График: плавный gradient, кастомный tooltip, auto-range."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QFrame, QSpinBox, QCheckBox, QListWidget,
    QListWidgetItem)
from PySide6.QtCore import Qt, Signal, QPoint, QRectF
from PySide6.QtGui import QColor, QCursor
import pyqtgraph as pg
import numpy as np
from src.config import COLORS
from src.ui.widgets.chart_tooltip import ChartTooltip


class ComparisonChart(QWidget):
    filters_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Фильтры ──
        fl1_frame = QFrame()
        fl1_frame.setObjectName("card")
        fl1 = QHBoxLayout(fl1_frame)
        fl1.setContentsMargins(10, 8, 10, 8)
        fl1.setSpacing(8)

        fl1.addWidget(QLabel("Метрика:"))
        self.metric_combo = QComboBox()
        self.metric_combo.addItems([
            "Rating", "K/D Ratio", "Winrate", "ADR",
            "K/R Ratio", "Kills", "Swing", "HS%", "Deaths", "Assists"])
        self.metric_combo.setMinimumWidth(110)
        self.metric_combo.currentIndexChanged.connect(self._redraw)
        fl1.addWidget(self.metric_combo)

        fl1.addWidget(QLabel("Режим ELO:"))
        self.elo_mode = QComboBox()
        self.elo_mode.addItems([
            "По игрокам (личный ELO)",
            "По лобби (среднее матча)"])
        self.elo_mode.setMinimumWidth(200)
        self.elo_mode.currentIndexChanged.connect(self._emit_filters)
        fl1.addWidget(self.elo_mode)

        fl1.addWidget(QLabel("Шаг:"))
        self.elo_step = QSpinBox()
        self.elo_step.setRange(25, 500)
        self.elo_step.setSingleStep(25)
        self.elo_step.setValue(50)
        self.elo_step.setSuffix(" ELO")
        self.elo_step.setMinimumWidth(95)
        self.elo_step.valueChanged.connect(self._emit_filters)
        fl1.addWidget(self.elo_step)

        self.cb_median = QCheckBox("Медиана")
        self.cb_median.stateChanged.connect(self._emit_filters)
        fl1.addWidget(self.cb_median)

        fl1.addWidget(QLabel("Пати:"))
        self.party_checks = {}
        for size in [1, 2, 3, 4, 5]:
            cb = QCheckBox(str(size))
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_filters)
            self.party_checks[size] = cb
            fl1.addWidget(cb)

        fl1.addStretch()
        self.btn_reset = QPushButton("↻")
        self.btn_reset.setObjectName("zoomBtn")
        self.btn_reset.clicked.connect(self._reset)
        fl1.addWidget(self.btn_reset)
        self.btn_zoom = QPushButton("⤢")
        self.btn_zoom.setObjectName("zoomBtn")
        self.btn_zoom.clicked.connect(self._autoscale)
        fl1.addWidget(self.btn_zoom)
        layout.addWidget(fl1_frame)

        # ── Страны + порог ──
        fl2_frame = QFrame()
        fl2_frame.setObjectName("card")
        fl2 = QHBoxLayout(fl2_frame)
        fl2.setContentsMargins(10, 6, 10, 6)
        fl2.setSpacing(8)

        fl2.addWidget(QLabel("Страны:"))
        self.country_list = QListWidget()
        self.country_list.setFlow(QListWidget.LeftToRight)
        self.country_list.setWrapping(False)
        self.country_list.setMaximumHeight(28)
        self.country_list.setMinimumWidth(200)
        self.country_list.setSelectionMode(QListWidget.MultiSelection)
        self.country_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.country_list.itemSelectionChanged.connect(self._emit_filters)
        fl2.addWidget(self.country_list, 1)

        self.btn_all_countries = QPushButton("Все")
        self.btn_all_countries.setObjectName("zoomBtn")
        self.btn_all_countries.clicked.connect(self._select_all_countries)
        fl2.addWidget(self.btn_all_countries)

        fl2.addWidget(QLabel("Порог:"))
        self.reliability_threshold = QSpinBox()
        self.reliability_threshold.setRange(5, 500)
        self.reliability_threshold.setValue(25)
        self.reliability_threshold.valueChanged.connect(self._redraw)
        fl2.addWidget(self.reliability_threshold)
        layout.addWidget(fl2_frame)

        # ── График ──
        ch_frame = QFrame()
        ch_frame.setObjectName("card")
        cl = QVBoxLayout(ch_frame)
        cl.setContentsMargins(8, 8, 8, 8)
        pg.setConfigOption("background", "#1e1e1e")
        pg.setConfigOption("foreground", "#888888")
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", "ELO")
        self.plot.addLegend(offset=(-10, 10))
        self.plot.scene().sigMouseClicked.connect(self._on_plot_click)
        cl.addWidget(self.plot)
        layout.addWidget(ch_frame, 1)

        self.tooltip = ChartTooltip()
        self._highlight_item = None
        self._pinned = False

        self._player_data = {}
        self._teammates_data = {}
        self._enemies_data = {}
        self._friends_data = {}
        self._series_plots = {}

        self._hover_proxy = pg.SignalProxy(
            self.plot.scene().sigMouseMoved, rateLimit=40,
            slot=self._on_mouse_move)

    def set_full_data(self, player, teammates, enemies, friends=None):
        self._player_data = player or {}
        self._teammates_data = teammates or {}
        self._enemies_data = enemies or {}
        self._friends_data = friends or {}
        self._pinned = False
        self.tooltip.hide()
        self._redraw()

    def set_countries(self, countries):
        current = self._selected_countries()
        self.country_list.blockSignals(True)
        self.country_list.clear()
        for c in sorted(countries):
            item = QListWidgetItem(c.upper())
            item.setData(Qt.UserRole, c.lower())
            self.country_list.addItem(item)
            if not current or c.lower() in current:
                item.setSelected(True)
        self.country_list.blockSignals(False)

    def _selected_countries(self):
        return [self.country_list.item(i).data(Qt.UserRole)
                for i in range(self.country_list.count())
                if self.country_list.item(i).isSelected()]

    def _select_all_countries(self):
        self.country_list.blockSignals(True)
        for i in range(self.country_list.count()):
            self.country_list.item(i).setSelected(True)
        self.country_list.blockSignals(False)
        self._emit_filters()

    def get_filters(self):
        party_sizes = [s for s, cb in self.party_checks.items()
                       if cb.isChecked()]
        countries = self._selected_countries()
        all_c = [self.country_list.item(i).data(Qt.UserRole)
                 for i in range(self.country_list.count())]
        if not countries or set(countries) == set(all_c):
            countries = None
        return {
            "elo_step": self.elo_step.value(),
            "party_sizes": party_sizes,
            "countries": countries,
            "median_mode": self.cb_median.isChecked(),
            "elo_mode": ("personal" if self.elo_mode.currentIndex() == 0
                         else "lobby"),
        }

    def _emit_filters(self):
        self.filters_changed.emit(self.get_filters())

    def _reset(self):
        self.metric_combo.setCurrentIndex(0)
        self.elo_mode.setCurrentIndex(0)
        self.elo_step.setValue(50)
        self.cb_median.setChecked(False)
        for cb in self.party_checks.values():
            cb.setChecked(True)
        self._select_all_countries()

    def _autoscale(self):
        vb = self.plot.getViewBox()
        vb.enableAutoRange()
        vb.autoRange()

    def _metric_value(self, data, metric):
        if not data:
            return None
        m = metric.lower()
        if "rating" in m: return data.get("rating")
        elif "winrate" in m: return data.get("wr")
        elif "k/d" in m: return data.get("kd")
        elif "k/r" in m: return data.get("kr")
        elif "adr" in m: return data.get("adr")
        elif "hs" in m: return data.get("hs")
        elif "swing" in m: return data.get("swing")
        elif "kills" in m: return data.get("kills")
        elif "deaths" in m: return data.get("deaths")
        elif "assists" in m: return data.get("assists")
        return None

    def _redraw(self):
        self.plot.clear()
        self._series_plots = {}
        self._highlight_item = None
        self._pinned = False
        metric = self.metric_combo.currentText()
        step = self.elo_step.value()
        threshold = self.reliability_threshold.value()
        colors = {"player": COLORS["purple"], "teammates": COLORS["accent"],
                  "enemies": COLORS["danger"], "friends": COLORS["success"]}
        names = {"player": "Игрок", "teammates": "Тиммейты",
                 "enemies": "Оппоненты", "friends": "Друзья"}

        all_x = []
        all_y = []
        reliability = []  # (x, count)

        for key, data in [
                ("player", self._player_data),
                ("teammates", self._teammates_data),
                ("enemies", self._enemies_data),
                ("friends", self._friends_data)]:
            if not data:
                continue
            xs = sorted(data.keys())
            ys = []
            for x in xs:
                v = self._metric_value(data[x], metric)
                ys.append(v if v is not None else float("nan"))
                if v is not None:
                    all_x.append(x)
                    all_y.append(v)
                    reliability.append((x, data[x].get("count", 0)))
            color = colors.get(key, "#aaa")
            pen = pg.mkPen(color, width=2)
            self.plot.plot(
                xs, ys, pen=pen, name=names.get(key, key),
                connect="finite", symbol="o", symbolSize=8,
                symbolBrush=color, symbolPen=None)
            self._series_plots[key] = (xs, ys, data, color)

        # Плавный градиент надёжности
        self._draw_gradient(reliability, threshold, step)

        # Title
        mode_str = ("личный ELO" if self.elo_mode.currentIndex() == 0
                    else "лобби")
        self.plot.setTitle(
            f"{metric} — "
            f"{'median' if self.cb_median.isChecked() else 'mean'} — "
            f"{mode_str}", color="#e8e8e8")
        self.plot.setLabel("left", metric)

        # АВТО-МАСШТАБ (проблема 4)
        if all_x and all_y:
            x_min = min(all_x) - step * 1.5
            x_max = max(all_x) + step * 1.5
            y_min = min(all_y)
            y_max = max(all_y)
            y_pad = max((y_max - y_min) * 0.25, 1)
            self.plot.setXRange(x_min, x_max, padding=0)
            self.plot.setYRange(y_min - y_pad, y_max + y_pad * 1.5,
                                 padding=0)

    def _draw_gradient(self, reliability, threshold, step):
        """Плавный градиент надёжности под графиком."""
        if not reliability:
            return
        rel_by_x = {}
        for x, cnt in reliability:
            rel_by_x[x] = max(rel_by_x.get(x, 0), cnt)
        if not rel_by_x:
            return

        xs_sorted = sorted(rel_by_x.keys())
        x_min = min(xs_sorted) - step * 1.5
        x_max = max(xs_sorted) + step * 1.5

        # Y-диапазон
        vr = self.plot.getViewBox().viewRange()
        y_min_vis = vr[1][0] if vr else 0
        y_max_vis = vr[1][1] if vr else 1
        band_h = 0.06 * (y_max_vis - y_min_vis)
        y_base = y_min_vis + 0.02 * (y_max_vis - y_min_vis)

        n_cols = 400
        n_rows = 20
        img = np.zeros((n_rows, n_cols, 4), dtype=np.uint8)

        for i in range(n_cols):
            x_val = x_min + (x_max - x_min) * (i / (n_cols - 1))
            nearest = min(rel_by_x.keys(),
                          key=lambda xx: abs(xx - x_val))
            if abs(nearest - x_val) > step:
                continue
            cnt = rel_by_x[nearest]
            rel = min(1.0, cnt / max(threshold, 1))
            if rel >= 0.7:
                r, g, b = 63, 185, 80
            elif rel >= 0.4:
                r, g, b = 210, 153, 34
            else:
                r, g, b = 248, 81, 73
            alpha = int(80 + rel * 120)
            img[:, i] = [r, g, b, alpha]

        item = pg.ImageItem(img)
        item.setRect(QRectF(x_min, y_base, x_max - x_min, band_h))
        item.setZValue(-10)
        self.plot.addItem(item)

    def _on_mouse_move(self, event):
        if self._pinned:
            return
        pos = event[0]
        if not self.plot.sceneBoundingRect().contains(pos):
            self.tooltip.hide()
            self._clear_highlight()
            return
        vb = self.plot.getViewBox()
        mp = vb.mapSceneToView(pos)
        mx, my = mp.x(), mp.y()
        step = self.elo_step.value()
        threshold = self.reliability_threshold.value()
        best, best_dist = None, float("inf")
        for key, (xs, ys, data, color) in self._series_plots.items():
            for i, x in enumerate(xs):
                y = ys[i]
                if y != y:
                    continue
                dx = abs(mx - x)
                dy = abs(my - y)
                if dx > step * 0.5:
                    continue
                d = dx * dx + dy * dy
                if d < best_dist:
                    best_dist = d
                    best = (key, x, y, data[x], color)
        if best:
            key, x, y, d, color = best
            self._show_tooltip(key, x, y, d, threshold)
            self._highlight(x, y, color)

    def _highlight(self, x, y, color):
        self._clear_highlight()
        self._highlight_item = pg.ScatterPlotItem(
            [x], [y], size=20, brush=pg.mkBrush(color),
            pen=pg.mkPen("#ffffff", width=2))
        self.plot.addItem(self._highlight_item)

    def _clear_highlight(self):
        if self._highlight_item:
            try:
                self.plot.removeItem(self._highlight_item)
            except Exception:
                pass
            self._highlight_item = None

    def _show_tooltip(self, key, x, y, d, threshold):
        names = {"player": "Игрок", "teammates": "Тиммейты",
                 "enemies": "Оппоненты", "friends": "Друзья"}
        cnt = d.get("count", 0)
        rel = int(min(1.0, cnt / max(threshold, 1)) * 100)
        stats = d.get("_stats", {})
        kd_s = stats.get("kd", {})
        adr_s = stats.get("adr", {})
        rows = [
            ("ELO", f"{x}-{x + self.elo_step.value() - 1}"),
            ("Значение", f"{round(y, 2)}"),
            ("Игроков", f"{cnt}"),
            ("Матчей", f"{d.get('matches', 0)}"),
            ("Надёжность", f"{rel}%"),
            ("Winrate", f"{d.get('wr', 0)}%"),
            ("K/D avg", f"{kd_s.get('avg', 0)}"),
            ("K/D med", f"{kd_s.get('med', 0)}"),
            ("K/D min-max",
             f"{kd_s.get('min', 0)} - {kd_s.get('max', 0)}"),
            ("ADR avg", f"{adr_s.get('avg', 0)}"),
            ("ADR med", f"{adr_s.get('med', 0)}"),
            ("Rating", f"{d.get('rating', 0)}"),
            ("K/R", f"{d.get('kr', 0)}"),
            ("HS%", f"{d.get('hs', 0)}%"),
        ]
        self.tooltip.set_data(
            f"{names.get(key, key)}", f"Надёжность {rel}% ({cnt})",
            rows)
        self.tooltip.show_at(QCursor.pos() + QPoint(15, 15))

    def _on_plot_click(self, event):
        if event.button() == Qt.RightButton:
            self._pinned = False
            self.tooltip.hide()
            self._clear_highlight()
            return
        if event.button() == Qt.LeftButton:
            if self.tooltip.isVisible():
                self._pinned = True
                self.tooltip.subtitle.setText(
                    "📌 Закреплено — ПКМ закрыть")
