"""Страница анализа друзей."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel)


class FriendsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Анализ игр с друзьями"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Друг", "Матчей", "Winrate", "K/D", "ADR"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def set_friends(self, data):
        friends = data.get("friends", {})
        self.table.setRowCount(len(friends))
        for i, (fid, st) in enumerate(friends.items()):
            self.table.setItem(i, 0, QTableWidgetItem(fid))
            self.table.setItem(i, 1, QTableWidgetItem(str(st.get("matches", 0))))
            self.table.setItem(i, 2, QTableWidgetItem(f"{st.get('winrate', 0)*100:.1f}%"))
            self.table.setItem(i, 3, QTableWidgetItem(str(st.get("avg_kd", 0))))
            self.table.setItem(i, 4, QTableWidgetItem(str(st.get("avg_adr", 0))))
