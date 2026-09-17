from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget,
                                QTableWidgetItem, QHeaderView, QLabel)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from src.config import COLORS


class MatchesPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.info = QLabel('🎮 Матчи игрока (двойной клик — открыть на FACEIT)')
        layout.addWidget(self.info)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ['Дата', 'Карта', 'Счёт', 'Result', 'K/D/A',
             'ADR', 'HS%', 'ELO', 'Источники'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._open_match)
        layout.addWidget(self.table)
        self._matches = []

    def set_matches(self, matches, match_data=None):
        """matches — список из faceit_matches, match_data — собранные детали."""
        detail_ids = set()
        if match_data:
            for entry in match_data:
                mid = entry.get('match_id')
                if mid:
                    detail_ids.add(mid)

        by_id = {}
        for m in matches or []:
            mid = m.get('match_id') or m.get('id')
            if not mid:
                continue
            if mid in by_id:
                src = m.get('source', '')
                if src and src not in by_id[mid]['sources']:
                    by_id[mid]['sources'].append(src)
            else:
                m = dict(m)
                m['sources'] = [m.get('source', '?')]
                m['_has_details'] = (mid in detail_ids) if match_data else False
                by_id[mid] = m

        unique = list(by_id.values())
        self._matches = unique
        self.table.setRowCount(len(unique))

        with_details = 0
        without = 0
        import datetime
        for i, m in enumerate(unique):
            d = m.get('date', 0)
            try:
                d_int = int(d)
                if d_int > 10 ** 12:
                    d_int //= 1000
                dt_str = (datetime.datetime.fromtimestamp(d_int)
                          .strftime('%Y-%m-%d %H:%M') if d_int > 0 else '?')
            except Exception:
                dt_str = '?'
            score = f"{m.get('score_a', 0)}:{m.get('score_b', 0)}"
            res = '✅ WIN' if int(m.get('result', 0) or 0) == 1 else '❌ LOSS'
            kda = (f"{m.get('kills', 0)}/{m.get('deaths', 0)}/"
                   f"{m.get('assists', 0)}")
            has_det = m.get('_has_details', False)
            if has_det:
                with_details += 1
            else:
                without += 1
            src_str = ', '.join(m.get('sources', []))
            if match_data is not None and not has_det:
                src_str += ' ⚠ нет деталей'
            cells = [dt_str, m.get('map_name', ''), score, res, kda,
                     str(m.get('adr', 0)),
                     f"{m.get('headshots_percent', 0)}%",
                     str(m.get('elo', 0)), src_str]
            for j, v in enumerate(cells):
                item = QTableWidgetItem(str(v))
                if j == 3:
                    item.setForeground(QColor(
                        COLORS['success'] if 'WIN' in str(v)
                        else COLORS['danger']))
                if j == 8 and match_data is not None and not has_det:
                    item.setForeground(QColor(COLORS['warning']))
                self.table.setItem(i, j, item)

        if match_data is not None:
            self.info.setText(
                f'🎮 Матчей: {len(unique)}  '
                f'✅ с деталями: {with_details}  '
                f'⚠ без деталей: {without}')
        else:
            self.info.setText(f'🎮 Матчей: {len(unique)}')

    def _open_match(self, index):
        row = index.row()
        if 0 <= row < len(self._matches):
            mid = self._matches[row].get('match_id', '')
            if mid:
                import webbrowser
                webbrowser.open(
                    f'https://www.faceit.com/en/cs2/room/{mid}/scoreboard')
