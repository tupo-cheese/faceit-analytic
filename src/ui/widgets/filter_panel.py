"""Панель фильтров."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDateEdit, QPushButton, QGroupBox)
from PySide6.QtCore import QDate, Signal


class FilterPanel(QWidget):
    filters_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        date_group = QGroupBox("Период")
        dg = QVBoxLayout(date_group)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("С:"))
        self.date_from = QDateEdit(QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        row1.addWidget(self.date_from)
        row1.addWidget(QLabel("По:"))
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        row1.addWidget(self.date_to)
        dg.addLayout(row1)
        layout.addWidget(date_group)

        game_group = QGroupBox("Игровые параметры")
        gg = QVBoxLayout(game_group)
        gg.addWidget(QLabel("Карта:"))
        self.map_combo = QComboBox()
        self.map_combo.addItems(["Все", "Mirage", "Dust2", "Inferno", "Nuke", "Ancient", "Anubis", "Vertigo", "Overpass"])
        gg.addWidget(self.map_combo)
        gg.addWidget(QLabel("Размер пати:"))
        self.party_combo = QComboBox()
        self.party_combo.addItems(["Все", "1", "2", "3", "4", "5"])
        gg.addWidget(self.party_combo)
        gg.addWidget(QLabel("Диапазон ELO:"))
        self.elo_combo = QComboBox()
        self.elo_combo.addItems(["Все"] + [f"{i}-{i+99}" for i in range(1000, 3000, 100)] + ["3000+"])
        gg.addWidget(self.elo_combo)
        layout.addWidget(game_group)

        btn_row = QHBoxLayout()
        self.btn_apply = QPushButton("Применить")
        self.btn_apply.setObjectName("accent")
        self.btn_reset = QPushButton("Сбросить")
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_reset)
        layout.addLayout(btn_row)
        layout.addStretch()
        self.btn_apply.clicked.connect(lambda: self.filters_changed.emit(self.get_filters()))

    def get_filters(self):
        return {
            "date_from": self.date_from.date().toString("yyyy-MM-dd"),
            "date_to": self.date_to.date().toString("yyyy-MM-dd"),
            "map": None if self.map_combo.currentIndex() == 0 else self.map_combo.currentText(),
            "party_size": None if self.party_combo.currentIndex() == 0 else self.party_combo.currentIndex(),
            "elo_bracket": None if self.elo_combo.currentIndex() == 0 else self.elo_combo.currentText(),
        }
