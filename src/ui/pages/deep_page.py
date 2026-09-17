"""Глубокая аналитика с выводами."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QTextEdit,
    QFrame, QGridLayout, QScrollArea)
from PySide6.QtGui import QColor
from src.config import COLORS
from src.ui.widgets.comparison_chart import ComparisonChart
from src.ui.widgets.stat_box import StatBox


class DeepPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._match_data = []
        self._aggregator = None
        self._conclusions = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()

        self.comparison = ComparisonChart()
        self.tabs.addTab(self.comparison, "📊 Сравнение")

        self.overview = self._make_overview()
        self.tabs.addTab(self.overview, "📈 Обзор")

        self.elo_table = self._make_table([
            "ELO", "N", "WR%", "K/D", "ADR", "HS%",
            "Rating", "K/R", "K", "D", "A"])
        self.tabs.addTab(self.elo_table, "🏔 По ELO")

        self.map_table = self._make_table([
            "Карта", "Игр", "WR%", "K/D", "ADR", "HS%", "ELO avg"])
        self.tabs.addTab(self.map_table, "🗺 Карты")

        self.country_view = QTextEdit()
        self.country_view.setReadOnly(True)
        self.tabs.addTab(self.country_view, "🌍 Страны")

        self.party_view = QTextEdit()
        self.party_view.setReadOnly(True)
        self.tabs.addTab(self.party_view, "👥 Пати")

        self.friends_view = QTextEdit()
        self.friends_view.setReadOnly(True)
        self.tabs.addTab(self.friends_view, "🤝 Друзья")

        self.verdict_view = QTextEdit()
        self.verdict_view.setReadOnly(True)
        self.tabs.addTab(self.verdict_view, "🎯 Выводы")

        layout.addWidget(self.tabs, 1)

    def _make_table(self, headers):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        return t

    def _make_overview(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        h = QLabel("📊 Обзор производительности")
        h.setObjectName("section")
        layout.addWidget(h)
        self.overview_summary = QLabel("Загрузите матчи")
        self.overview_summary.setWordWrap(True)
        layout.addWidget(self.overview_summary)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.overview_boxes = {}
        for i, (key, label) in enumerate([
                ("wr", "Winrate"), ("matches", "Матчей"),
                ("kd", "K/D"), ("adr", "ADR"),
                ("hs", "HS%"), ("kills_avg", "Kills avg"),
                ("deaths_avg", "Deaths avg"),
                ("assists_avg", "Assists avg"),
                ("mvps", "MVPs avg"), ("rounds", "Rounds avg"),
                ("elo_min", "ELO min"), ("elo_max", "ELO max"),
                ("elo_avg", "ELO avg"), ("elo_delta", "Δ ELO"),
                ("last10_wr", "WR (10)"), ("prev10_wr", "WR (10 до)"),
                ("kd_trend", "Δ K/D"), ("adr_trend", "Δ ADR"),
                ("kd_med", "K/D median"), ("adr_med", "ADR median"),
                ("hs_med", "HS median"), ("kills_total", "Kills total"),
                ("deaths_total", "Deaths total"),
                ("assists_total", "Assists total")]):
            box = StatBox(label)
            grid.addWidget(box, i // 6, i % 6)
            self.overview_boxes[key] = box
        layout.addLayout(grid)
        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    def set_match_data(self, match_data):
        self._match_data = match_data or []

    def set_aggregator(self, aggregator):
        self._aggregator = aggregator

    def set_deep_analysis(self, result):
        try:
            self._fill(result)
        except Exception as e:
            import traceback, logging
            logging.getLogger("faceit_analytics").error(
                f"DeepPage error: {e}\n{traceback.format_exc()}")

    def _fill(self, result):
        s = result.get("summary", {})
        by_map = result.get("by_map", {})
        progress = result.get("progress", {})

        self.overview_summary.setText(
            f"Матчей: {s.get('matches', 0)} | "
            f"Побед: {s.get('wins', 0)} ({s.get('winrate', 0)}%) | "
            f"ELO: {s.get('elo_min', 0)}—{s.get('elo_max', 0)}")

        def fill(key, value, color=None):
            if key in self.overview_boxes:
                self.overview_boxes[key].set(value, color)

        wr = s.get("winrate", 0)
        fill("wr", wr, COLORS["success"] if wr >= 50 else COLORS["danger"])
        fill("matches", s.get("matches", 0))
        fill("kd", s.get("kd_total", 0))
        fill("adr", s.get("adr_avg", 0))
        fill("hs", s.get("hs_avg", 0))
        fill("kills_avg", s.get("kills_avg", 0))
        fill("deaths_avg", s.get("deaths_avg", 0))
        fill("assists_avg", s.get("assists_avg", 0))
        fill("mvps", s.get("mvps_avg", 0))
        fill("rounds", s.get("rounds_avg", 0))
        fill("elo_min", s.get("elo_min", 0))
        fill("elo_max", s.get("elo_max", 0))
        fill("elo_avg", s.get("elo_avg", 0))
        fill("elo_delta", f"{s.get('elo_delta_sum', 0):+d}")
        fill("kd_med", s.get("kd_median", 0))
        fill("adr_med", s.get("adr_median", 0))
        fill("hs_med", s.get("hs_median", 0))
        fill("kills_total", s.get("kills", 0))
        fill("deaths_total", s.get("deaths", 0))
        fill("assists_total", s.get("assists", 0))
        if progress:
            fill("last10_wr", progress.get("last_10", {}).get("winrate", 0))
            fill("prev10_wr", progress.get("prev_10", {}).get("winrate", 0))
            fill("kd_trend", f"{progress.get('kd_delta', 0):+.2f}")
            fill("adr_trend", f"{progress.get('adr_delta', 0):+.1f}")

        sorted_maps = sorted(by_map.items(),
                             key=lambda x: -x[1].get("matches", 0))
        self.map_table.setRowCount(len(sorted_maps))
        for i, (mp, d) in enumerate(sorted_maps):
            self._fill_row(self.map_table, i, [
                mp, d.get("matches", 0),
                f"{d.get('winrate', 0)}%", d.get("kd_ratio", 0),
                d.get("adr_avg", 0), f"{d.get('hs_avg', 0)}%",
                d.get("elo_avg", 0)])

        # Выводы — глубочайший анализ
        self._build_conclusions(s, by_map, progress)

    def _update_elo_table(self, tm, en, pl, step):
        buckets = sorted(set(tm.keys()) | set(en.keys()) | set(pl.keys()))
        self.elo_table.setRowCount(len(buckets))
        for i, br in enumerate(buckets):
            t = tm.get(br, {}) or {}
            e = en.get(br, {}) or {}
            p = pl.get(br, {}) or {}
            self._fill_row(self.elo_table, i, [
                f"{br}-{br+step-1}", t.get("count", 0),
                f"{t.get('wr', 0)}%", t.get("kd", "—"),
                t.get("adr", "—"), f"{t.get('hs', 0)}%",
                t.get("rating", "—"), t.get("kr", "—"),
                t.get("kills", "—"), t.get("deaths", "—"),
                t.get("assists", "—")])

    def set_conclusions(self, conclusions):
        """Заполняет все вкладки анализом."""
        self._conclusions = conclusions or {}
        # Страны
        txt = ["🌍 Влияние стран", ""]
        tm_countries = conclusions.get("by_country_teammates", {})
        en_countries = conclusions.get("by_country_enemies", {})
        if tm_countries:
            txt.append("── ТИММЕЙТЫ ──")
            txt.append(f"{'Страна':<8} | {'N':>4} | {'K/D':>6} | {'WR%':>6}")
            for c, d in tm_countries.items():
                txt.append(f"{c.upper():<8} | {d['count']:>4} | "
                           f"{d['avg_kd']:>6} | {d['winrate']:>6}")
        if en_countries:
            txt.append("")
            txt.append("── ВРАГИ ──")
            txt.append(f"{'Страна':<8} | {'N':>4} | {'K/D':>6} | {'Loss%':>6}")
            for c, d in en_countries.items():
                txt.append(f"{c.upper():<8} | {d['count']:>4} | "
                           f"{d['avg_kd']:>6} | {d['loss_rate']:>6}")
        self.country_view.setPlainText("\n".join(txt))

        # Пати
        by_party = conclusions.get("by_party", {})
        txt = ["👥 Влияние размера пати", ""]
        for size, d in by_party.items():
            txt.append(f"Пати {size}: {d['matches']} матчей, "
                       f"winrate {d['winrate']}%")
        self.party_view.setPlainText("\n".join(txt))

        # Друзья
        friends = conclusions.get("friends_impact", {})
        txt = ["🤝 Влияние друзей", ""]
        for k, d in sorted(friends.items(),
                           key=lambda x: -x[1]["matches"])[:20]:
            txt.append(f"{k[:30]}: {d['matches']} игр, "
                       f"WR {d['winrate']}%, K/D {d['my_kd']}")
        self.friends_view.setPlainText("\n".join(txt))

    def _build_conclusions(self, s, by_map, progress):
        lines = ["🎯 Глубочайший анализ", ""]

        wr = s.get("winrate", 0)
        kd = s.get("kd_total", 0)
        adr = s.get("adr_avg", 0)
        hs = s.get("hs_avg", 0)

        # Сравнение с ожиданиями
        lines.append("── Базовая оценка ──")
        if wr > 55:
            lines.append(f"✅ Winrate {wr}% — выше среднего")
        elif wr < 45:
            lines.append(f"⚠ Winrate {wr}% — ниже среднего")
        else:
            lines.append(f"Winrate {wr}% — на среднем уровне")

        if kd > 1.15:
            lines.append(f"✅ K/D {kd} — сильная сторона")
        elif kd < 0.9:
            lines.append(f"⚠ K/D {kd} — слабая сторона")

        if adr > 80:
            lines.append(f"✅ ADR {adr} — высокий урон за раунд")
        elif adr < 65:
            lines.append(f"⚠ ADR {adr} — низкий урон")

        # Аномалия: высокий K/D но низкий WR
        if kd >= 1.15 and wr < 52:
            lines.append("")
            lines.append("🔴 АНОМАЛИЯ: K/D высокий, но winrate низкий")
            lines.append("   Возможные причины:")
            lines.append("   • Фраги в мусорных раундах")
            lines.append("   • Слабая игра в клатчах")
            lines.append("   • Мало impact-фрагов (энтри)")
            lines.append("   • Тиммейты не тянут")

        if adr > 80 and wr < 50:
            lines.append("")
            lines.append("🔴 АНОМАЛИЯ: высокий ADR, но winrate низкий")
            lines.append("   Ты наносишь много урона, но команда проигрывает")
            lines.append("   Возможно: фраги не конвертируются в победы")

        # По картам
        if by_map:
            sorted_m = sorted(by_map.items(),
                              key=lambda x: -x[1].get("winrate", 0))
            lines.append("")
            lines.append("── Карты ──")
            lines.append("🟢 Топ-3:")
            for mp, d in sorted_m[:3]:
                lines.append(f"   {mp}: {d.get('winrate')}% "
                             f"({d.get('matches')} игр, "
                             f"K/D {d.get('kd_ratio')})")
            lines.append("🔴 Худшие:")
            for mp, d in sorted_m[-3:]:
                lines.append(f"   {mp}: {d.get('winrate')}% "
                             f"({d.get('matches')} игр, "
                             f"K/D {d.get('kd_ratio')})")

        # Прогресс
        if progress:
            delta = progress.get("kd_delta", 0)
            lines.append("")
            lines.append("── Динамика (10 последних vs 10 до) ──")
            if delta > 0.1:
                lines.append(f"📈 K/D вырос на {delta:+.2f}")
            elif delta < -0.1:
                lines.append(f"📉 K/D упал на {delta:+.2f}")
            else:
                lines.append(f"K/D стабилен ({delta:+.2f})")

        self.verdict_view.setPlainText("\n".join(lines))

    def _fill_row(self, table, row, values):
        for col, v in enumerate(values):
            item = QTableWidgetItem(str(v))
            s = str(v)
            if "%" in s:
                try:
                    fv = float(s.replace("%", ""))
                    if fv >= 55:
                        item.setForeground(QColor(COLORS["success"]))
                    elif fv <= 45:
                        item.setForeground(QColor(COLORS["danger"]))
                except Exception:
                    pass
            table.setItem(row, col, item)
