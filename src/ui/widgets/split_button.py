from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt


class SplitButton(QWidget):
    """
    [ Основное действие ][ ↻ ]
    main — клик (не checkable, чтобы не конфликтовать с QButtonGroup).
    refresh — правый угол.
    """
    clicked = Signal()
    refresh_clicked = Signal()

    def __init__(self, text='', parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.main_btn = QPushButton(text)
        self.main_btn.setObjectName('navTabMain')
        self.main_btn.setCheckable(True)
        self.main_btn.setMinimumHeight(40)
        self.main_btn.setMinimumWidth(110)
        self.main_btn.setFocusPolicy(Qt.NoFocus)
        self.main_btn.clicked.connect(lambda _=False: self.clicked.emit())

        self.refresh_btn = QPushButton('↻')
        self.refresh_btn.setObjectName('navTabRefresh')
        self.refresh_btn.setFixedWidth(40)
        self.refresh_btn.setMinimumHeight(40)
        self.refresh_btn.setFocusPolicy(Qt.NoFocus)
        self.refresh_btn.setAutoDefault(False)
        self.refresh_btn.setDefault(False)
        self.refresh_btn.setToolTip('↻ Обновить данные (принудительно)')
        self.refresh_btn.clicked.connect(lambda _=False: self.refresh_clicked.emit())

        layout.addWidget(self.main_btn)
        layout.addWidget(self.refresh_btn)

    def setChecked(self, v):
        self.main_btn.setChecked(v)

    def isChecked(self):
        return self.main_btn.isChecked()

    def setText(self, t):
        self.main_btn.setText(t)
