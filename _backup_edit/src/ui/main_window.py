from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QLineEdit, QPushButton, QStatusBar, QLabel,
                                QFrame, QStackedWidget, QButtonGroup,
                                QProgressBar, QComboBox, QSpinBox)
from PySide6.QtCore import Qt, Signal
from src.ui.pages.quick_page import QuickPage
from src.ui.pages.deep_page import DeepPage
from src.ui.pages.matches_page import MatchesPage
from src.ui.debug_console import ConsolePanel, CommandsDialog
from src.ui.widgets.split_button import SplitButton


class MainWindow(QMainWindow):
    quick_refresh = Signal()
    deep_refresh = Signal()
    load_more_clicked = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Faceit Analytics')
        self.resize(1600, 1000)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 8)
        layout.setSpacing(8)

        # ─── верхняя строка ───
        top1 = QHBoxLayout()
        top1.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            'URL или ник: Steam / FACEIT / csstats / cswatch')
        self.search_input.setMinimumHeight(40)
        top1.addWidget(self.search_input, 1)

        self.players_combo = QComboBox()
        self.players_combo.setMinimumWidth(200)
        self.players_combo.setMinimumHeight(40)
        self.players_combo.setToolTip('История загруженных игроков')
        self.players_combo.addItem('— история —', '')
        top1.addWidget(self.players_combo)

        # ─── split-кнопки навигации ───
        self.btn_quick = SplitButton('⚡ Быстрая')
        self.btn_deep = SplitButton('🔬 Глубокая')
        self.btn_matches = QPushButton('🎮 Матчи')
        self.btn_matches.setObjectName('navTabMain')
        self.btn_matches.setCheckable(True)
        self.btn_matches.setMinimumHeight(40)
        self.btn_matches.setMinimumWidth(140)
        top1.addWidget(self.btn_quick)
        top1.addWidget(self.btn_deep)
        top1.addWidget(self.btn_matches)
        self.btn_quick.setChecked(True)

        self.nav_group = QButtonGroup(self)
        self.nav_group.addButton(self.btn_quick.main_btn, 0)
        self.nav_group.addButton(self.btn_deep.main_btn, 1)
        self.nav_group.addButton(self.btn_matches, 2)
        self.nav_group.buttonClicked.connect(self._on_nav_clicked)
        self.btn_quick.refresh_clicked.connect(self.quick_refresh.emit)
        self.btn_deep.refresh_clicked.connect(self.deep_refresh.emit)
        layout.addLayout(top1)

        # ─── источники + доп. матчи ───
        top2 = QHBoxLayout()
        top2.setSpacing(6)
        top2.addWidget(QLabel('Источники:'))
        self.source_chips = {}
        for key, short in [('steam', 'Steam'), ('cswatch', 'CSWatch'),
                            ('faceit', 'FACEIT'), ('csstats', 'CSStats'),
                            ('fa', 'FaceitAnalyser')]:
            chip = QPushButton(short)
            chip.setObjectName('chip')
            chip.setCheckable(True)
            chip.setChecked(True)
            chip.setMinimumHeight(30)
            self.source_chips[key] = chip
            top2.addWidget(chip)
        top2.addStretch()
        top2.addWidget(QLabel('Доп. матчи:'))
        self.load_more_spin = QSpinBox()
        self.load_more_spin.setRange(25, 5000)
        self.load_more_spin.setSingleStep(25)
        self.load_more_spin.setValue(200)
        self.load_more_spin.setSuffix(' шт')
        self.load_more_spin.setMinimumWidth(90)
        top2.addWidget(self.load_more_spin)
        self.btn_load_more = QPushButton('📥 Загрузить')
        self.btn_load_more.setMinimumHeight(30)
        self.btn_load_more.clicked.connect(
            lambda: self.load_more_clicked.emit(self.load_more_spin.value()))
        top2.addWidget(self.btn_load_more)
        layout.addLayout(top2)

        # ─── прогресс + ETA ───
        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        prog_row.addWidget(self.progress_bar, 3)
        self.progress_label = QLabel('')
        self.progress_label.setMinimumWidth(400)
        prog_row.addWidget(self.progress_label, 2)
        self.eta_label = QLabel('')
        self.eta_label.setMinimumWidth(150)
        self.eta_label.setStyleSheet('color:#d29922; font-weight:600;')
        prog_row.addWidget(self.eta_label)
        self.btn_cancel = QPushButton('✕ Отмена')
        self.btn_cancel.setObjectName('zoomBtn')
        self.btn_cancel.setVisible(False)
        prog_row.addWidget(self.btn_cancel)
        layout.addLayout(prog_row)

        # ─── stack ───
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
        self.empty_label = QLabel('👋 Введите URL игрока в поле сверху')
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(
            'font-size: 18px; color: #888; padding: 40px;')
        el.addWidget(self.empty_label)
        el.addStretch()
        self.stack.addWidget(self.empty_page)
        layout.addWidget(self.stack, 1)

        # ─── консоль ───
        self.console = ConsolePanel()
        layout.addWidget(self.console)
        self.command_input = self.console.command_input
        self.log_view = self.console.log_view

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage('Готово')
        self._has_url = False
        self.stack.setCurrentWidget(self.empty_page)

    def _on_nav_clicked(self, btn):
        if not self._has_url:
            self.stack.setCurrentWidget(self.empty_page)
            return
        idx = self.nav_group.id(btn)
        if idx >= 0:
            self.stack.setCurrentIndex(idx)

    def mark_url_loaded(self):
        self._has_url = True
        self.btn_quick.setChecked(True)
        self.stack.setCurrentWidget(self.quick_page)

    def set_status(self, text):
        self.statusBar().showMessage(text)

    def set_loading(self, active, text=''):
        self.progress_bar.setVisible(active)
        self.btn_cancel.setVisible(active)
        self.progress_label.setVisible(active)
        self.eta_label.setVisible(active)
        if text:
            self.progress_label.setText(text)
        if not active:
            self.progress_bar.setValue(0)
            self.progress_label.setText('')
            self.eta_label.setText('')

    def set_progress(self, value, text='', eta=''):
        self.progress_bar.setValue(value)
        if text:
            self.progress_label.setText(text)
        if eta:
            self.eta_label.setText(f'⏱ {eta}')

    def show_commands_dialog(self):
        CommandsDialog(self).exec()

    def refresh_players_combo(self, players_list, current_id=''):
        self.players_combo.blockSignals(True)
        self.players_combo.clear()
        self.players_combo.addItem('— история —', '')
        for sid, rec in players_list:
            nick = rec.get('nickname', sid[:8])
            elo = rec.get('faceit_elo', '')
            deep = '🔬' if rec.get('has_deep') else '⚡'
            label = f'{deep} {nick} [{elo}]' if elo else f'{deep} {nick}'
            self.players_combo.addItem(label, sid)
            if sid == current_id:
                self.players_combo.setCurrentIndex(
                    self.players_combo.count() - 1)
        self.players_combo.blockSignals(False)

    def get_sources(self):
        return {
            'steam': self.source_chips['steam'].isChecked(),
            'cswatch': self.source_chips['cswatch'].isChecked(),
            'faceit': self.source_chips['faceit'].isChecked(),
            'csstats': self.source_chips['csstats'].isChecked(),
            'faceitanalyser': self.source_chips['fa'].isChecked(),
        }
