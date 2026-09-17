"""Страница матчей."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from src.config import COLORS


class MatchesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        info = QLabel("🎮 Матчи игрока (двойной клик по строке — "
                      "открыть на FACEIT)")
        layout.addWidget(info)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Дата", "Карта", "Счёт", "Result", "K/D/A",
            "ADR", "HS%", "ELO", "Источники"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._open_match)
        layout.addWidget(self.table)
        self._matches = []

    def set_matches(self, matches):
        by_id = {}
        for m in matches:
            mid = m.get("match_id") or m.get("id")
            if not mid:
                continue
            if mid in by_id:
                src = m.get("source", "")
                if src and src not in by_id[mid]["sources"]:
                    by_id[mid]["sources"].append(src)
            else:
                m = dict(m)
                m["sources"] = [m.get("source", "?")]
                by_id[mid] = m
        unique = list(by_id.values())
        self._matches = unique

        import datetime
        self.table.setRowCount(len(unique))
        for i, m in enumerate(unique):
            d = m.get("date", 0)
            try:
                d_int = int(d)
                if d_int > 10**12:
                    d_int //= 1000
                dt_str = (datetime.datetime.fromtimestamp(d_int).strftime(
                    "%Y-%m-%d %H:%M") if d_int > 0 else "?")
            except Exception:
                dt_str = "?"
            score = f"{m.get('score_a', 0)}:{m.get('score_b', 0)}"
            res = "✅ WIN" if int(m.get("result", 0) or 0) == 1 else "❌ LOSS"
            kda = (f"{m.get('kills', 0)}/{m.get('deaths', 0)}/"
                   f"{m.get('assists', 0)}")
            cells = [
                dt_str, m.get("map_name", ""), score, res, kda,
                str(m.get("adr", 0)),
                f"{m.get('headshots_percent', 0)}%",
                str(m.get("elo", 0)),
                ", ".join(m.get("sources", [])),
            ]
            for j, v in enumerate(cells):
                item = QTableWidgetItem(str(v))
                if j == 3:
                    item.setForeground(QColor(
                        COLORS["success"] if "WIN" in str(v)
                        else COLORS["danger"]))
                self.table.setItem(i, j, item)

    def _open_match(self, index):
        row = index.row()
        if 0 <= row < len(self._matches):
            mid = self._matches[row].get("match_id", "")
            if mid:
                import webbrowser
                webbrowser.open(
                    f"https://www.faceit.com/en/cs2/room/{mid}/scoreboard")
