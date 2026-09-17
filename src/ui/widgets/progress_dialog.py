"""Диалог прогресса."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout
from PySide6.QtCore import Signal


class ProgressDialog(QDialog):
    cancelled = Signal()

    def __init__(self, title="Загрузка...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(420, 160)
        layout = QVBoxLayout(self)
        self.label = QLabel("Подготовка...")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        layout.addWidget(self.bar)
        row = QHBoxLayout()
        row.addStretch()
        self.btn_cancel = QPushButton("Прервать")
        self.btn_cancel.clicked.connect(self._on_cancel)
        row.addWidget(self.btn_cancel)
        layout.addLayout(row)

    def set_progress(self, value, text=""):
        self.bar.setValue(value)
        if text:
            self.label.setText(text)

    def _on_cancel(self):
        self.cancelled.emit()
        self.reject()
