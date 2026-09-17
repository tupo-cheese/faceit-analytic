"""Главное окно."""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QStatusBar, QLabel, QFrame, QStackedWidget,
    QButtonGroup, QProgressBar
)
from PySide6.QtCore import Qt
from src.ui.pages.quick_page import QuickPage
from src.ui.pages.deep_page import DeepPage
from src.ui.pages.matches_page import MatchesPage
from src.ui.debug_console import ConsolePanel, CommandsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Faceit Analytics")
        self.resize(1600, 1000)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 8)
        layout.setSpacing(8)

        top1 = QHBoxLayout()
        top1.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "URL или ник: Steam / FACEIT / csstats / cswatch")
        self.search_input.setMinimumHeight(40)
        top1.addWidget(self.search_input, 1)

        self.nav_group = QButtonGroup(self)
        self.nav_buttons = {}
        for key, label in [
                ("quick", "⚡ Быстрая"),
                ("deep", "🔬 Глубокая"),
                ("matches", "🎮 Матчи")]:
            btn = QPushButton(label)
            btn.setObjectName("navTab")
            btn.setCheckable(True)
            btn.setMinimumHeight(40)
            btn.setMinimumWidth(140)
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
            top1.addWidget(btn)
        self.nav_buttons["quick"].setChecked(True)
        self.nav_group.buttonClicked.connect(self._on_nav_clicked)
        layout.addLayout(top1)

        top2 = QHBoxLayout()
        top2.setSpacing(6)
        top2.addWidget(QLabel("Источники:"))
        self.source_chips = {}
        for key, short in [
                ("steam", "Steam"), ("cswatch", "CSWatch"),
                ("faceit", "FACEIT"), ("csstats", "CSStats"),
                ("fa", "FaceitAnalyser")]:
            chip = QPushButton(short)
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setChecked(True)
            chip.setMinimumHeight(30)
            self.source_chips[key] = chip
            top2.addWidget(chip)
        top2.addStretch()
        layout.addLayout(top2)

        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        prog_row.addWidget(self.progress_bar, 1)
        self.progress_label = QLabel("")
        self.progress_label.setMinimumWidth(300)
        prog_row.addWidget(self.progress_label)
        self.btn_cancel = QPushButton("✕ Отмена")
        self.btn_cancel.setObjectName("zoomBtn")
        self.btn_cancel.setVisible(False)
        prog_row.addWidget(self.btn_cancel)
        layout.addLayout(prog_row)

        self.stack = QStackedWidget()
        self.quick_page = QuickPage()
        self.deep_page = DeepPage()
        self.matches_page = MatchesPage()
        self.stack.addWidget(self.quick_page)
        self.stack.addWidget(self.deep_page)
        self.stack.addWidget(self.matches_page)
        self.empty_page = QWidget()
        el = QVBoxLayout(self.empty_page)
        el.addStretch()
        self.empty_label = QLabel("👋 Введите URL игрока в поле сверху")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(
            "font-size: 18px; color: #888; padding: 40px;")
        el.addWidget(self.empty_label)
        el.addStretch()
        self.stack.addWidget(self.empty_page)
        layout.addWidget(self.stack, 1)

        self.console = ConsolePanel()
        layout.addWidget(self.console)
        self.command_input = self.console.command_input
        self.log_view = self.console.log_view

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готово")
        self._has_url = False
        self.stack.setCurrentWidget(self.empty_page)

    def _on_nav_clicked(self, btn):
        if not self._has_url:
            self.stack.setCurrentWidget(self.empty_page)
            return
        idx = list(self.nav_buttons.values()).index(btn)
        self.stack.setCurrentIndex(idx)

    def mark_url_loaded(self):
        self._has_url = True
        self.nav_buttons["quick"].setChecked(True)
        self.stack.setCurrentWidget(self.quick_page)

    def set_status(self, text):
        self.statusBar().showMessage(text)

    def set_loading(self, active, text=""):
        self.progress_bar.setVisible(active)
        self.btn_cancel.setVisible(active)
        self.progress_label.setVisible(active)
        if text:
            self.progress_label.setText(text)
        if not active:
            self.progress_bar.setValue(0)
            self.progress_label.setText("")

    def set_progress(self, value, text=""):
        self.progress_bar.setValue(value)
        if text:
            self.progress_label.setText(text)

    def show_commands_dialog(self):
        CommandsDialog(self).exec()

    def get_sources(self):
        return {
            "steam": self.source_chips["steam"].isChecked(),
            "cswatch": self.source_chips["cswatch"].isChecked(),
            "faceit": self.source_chips["faceit"].isChecked(),
            "csstats": self.source_chips["csstats"].isChecked(),
            "faceitanalyser": self.source_chips["fa"].isChecked(),
        }
