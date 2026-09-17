"""Консоль отладки: строка внизу + разворот."""
import sys
import logging
import importlib
import pkgutil
import traceback
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QDialog, QListWidget, QListWidgetItem, QLabel,
    QSplitter, QTabWidget, QDockWidget, QFrame
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QTextCursor, QKeySequence, QShortcut

from src.config import COLORS


class QtLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.widget = None
        self.message_count = 0
        self.last_message = ""
        self.on_message = None

    def emit(self, record):
        if self.widget is None:
            return
        msg = self.format(record)
        self.message_count += 1
        self.last_message = msg
        if self.on_message:
            self.on_message(msg)
        color = {
            logging.DEBUG: COLORS["text_secondary"],
            logging.INFO: COLORS["text_primary"],
            logging.WARNING: COLORS["warning"],
            logging.ERROR: COLORS["danger"],
            logging.CRITICAL: COLORS["danger"],
        }.get(record.levelno, COLORS["text_primary"])

        cursor = self.widget.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.widget.setTextCursor(cursor)
        self.widget.setTextColor(QColor(color))
        self.widget.insertPlainText(msg + "\n")
        self.widget.ensureCursorVisible()


_global_handler = None


def get_log_handler():
    global _global_handler
    if _global_handler is None:
        _global_handler = QtLogHandler()
        _global_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        ))
    return _global_handler


COMMANDS = {
    "help":            "Список команд",
    "clear":           "Очистить лог",
    "audit":           "Аудит UI + модулей",
    "errors":          "Ошибки сессии",
    "deep":            "deep <steam_id> — загрузить матчи",
    "load":            "load <steam_id> — короткая сводка",
    "test_csstats":    "test_csstats <steam_id>",
    "test_csstats_deep": "test_csstats_deep <steam_id>",
    "test_faceit_matches": "test_faceit_matches <steam_id>",
    "test_faceit_summary": "test_faceit_summary <steam_id>",
    "test_all":        "test_all <steam_id> — все тесты",
    "cache":           "Очистить кэш",
    "players":         "Игроки в базе",
}


class CommandsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Команды")
        self.resize(700, 500)
        layout = QHBoxLayout(self)
        self.list = QListWidget()
        for name, desc in COMMANDS.items():
            item = QListWidgetItem(f"{name} — {desc}")
            item.setData(Qt.UserRole, name)
            self.list.addItem(item)
        layout.addWidget(self.list, 1)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        layout.addWidget(self.detail, 2)
        self.list.currentItemChanged.connect(self._on_select)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _on_select(self, current, _):
        if not current:
            return
        name = current.data(Qt.UserRole)
        self.detail.setHtml(
            f"<h3>{name}</h3><p>{COMMANDS.get(name, '')}</p>")


def walk_widgets(widget, depth=0):
    yield widget, depth
    for child in widget.children():
        if isinstance(child, QWidget):
            yield from walk_widgets(child, depth + 1)


def audit_ui(main_window):
    lines = ["═══ АУДИТ UI ═══"]
    for w, depth in walk_widgets(main_window):
        indent = "  " * depth
        if isinstance(w, QPushButton):
            lines.append(f"{indent}🔘 '{w.text()}'")
        elif isinstance(w, QLineEdit):
            lines.append(f"{indent}✏️  '{w.placeholderText()}'")
        elif isinstance(w, QTabWidget):
            for i in range(w.count()):
                lines.append(f"{indent}📑 Tab[{i}]: '{w.tabText(i)}'")
    return "\n".join(lines)


def audit_modules():
    lines = ["═══ АУДИТ МОДУЛЕЙ ═══"]
    root = str(Path.cwd())
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import src
    except Exception as e:
        return f"❌ src: {e}\n{traceback.format_exc()}"
    ok, fail = 0, 0
    for _, modname, ispkg in pkgutil.walk_packages(
            src.__path__, prefix="src."):
        if ispkg:
            continue
        try:
            importlib.import_module(modname)
            ok += 1
        except Exception as e:
            lines.append(f"  ❌ {modname}: {type(e).__name__}: {e}")
            fail += 1
    lines.append(f"Всего модулей: OK={ok}, FAIL={fail}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# Консоль с разворотом
# ═══════════════════════════════════════════════════════════
class ConsolePanel(QWidget):
    """Разворачивающаяся консоль."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Строка-превью (видна всегда) ─────────────
        self.bar = QFrame()
        self.bar.setObjectName("consoleBar")
        self.bar.setCursor(Qt.PointingHandCursor)
        bar_layout = QHBoxLayout(self.bar)
        bar_layout.setContentsMargins(12, 6, 12, 6)

        self.arrow = QLabel("▶")
        self.arrow.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px;")
        bar_layout.addWidget(self.arrow)

        self.title = QLabel("Консоль отладки")
        self.title.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 12px; "
            "font-weight: 600;")
        bar_layout.addWidget(self.title)

        self.preview = QLabel("")
        self.preview.setObjectName("consoleText")
        self.preview.setSizePolicy(
            self.preview.sizePolicy().horizontalPolicy(),
            self.preview.sizePolicy().verticalPolicy())
        bar_layout.addWidget(self.preview, 1)

        self.counter = QLabel("0")
        self.counter.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            "padding: 2px 8px; border-radius: 8px; background: #242424;")
        bar_layout.addWidget(self.counter)

        self.btn_detach = QPushButton("↗")
        self.btn_detach.setFixedSize(28, 24)
        self.btn_detach.setToolTip("Открепить")
        self.btn_detach.setStyleSheet(
            "QPushButton { padding: 2px 6px; font-size: 12px; }")
        bar_layout.addWidget(self.btn_detach)

        outer.addWidget(self.bar)

        # ── Разворачиваемая часть ────────────────────
        self.body = QWidget()
        self.body.setMaximumHeight(0)
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 6, 0, 0)
        body_layout.setSpacing(4)

        # Поиск
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ctrl+F для поиска...")
        self.search_input.setVisible(False)
        search_row.addWidget(self.search_input, 1)
        body_layout.addLayout(search_row)

        # Лог
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            f"background-color: #0d0d0d;"
            f"border: 1px solid #2a2a2a;"
            "border-radius: 8px;"
            "font-family: 'Consolas', monospace;"
            "font-size: 12px; padding: 8px;")
        body_layout.addWidget(self.log_view, 1)

        # Ввод команд
        cmd_row = QHBoxLayout()
        cmd_row.addWidget(QLabel(">"))
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText(
            "Введите команду (help — список)...")
        cmd_row.addWidget(self.command_input, 1)
        body_layout.addLayout(cmd_row)

        outer.addWidget(self.body)

        # Состояние
        self.expanded = False
        self.animation = QPropertyAnimation(self.body, b"maximumHeight")
        self.animation.setDuration(220)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        # События
        self.bar.mousePressEvent = self._on_bar_click
        self.btn_detach.clicked.connect(self._on_detach_click)

        # Ctrl+F
        shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut.activated.connect(self._toggle_search)

        # Подключаем лог-хендлер
        handler = get_log_handler()
        handler.widget = self.log_view
        handler.on_message = self._on_new_message

    def _on_bar_click(self, event):
        # Игнорируем клик по кнопке detach
        if event.pos().x() >= self.btn_detach.x():
            return
        self.toggle()

    def _on_detach_click(self):
        # Сигнал наружу через родителя — устанавливается в main_window
        pass

    def toggle(self):
        if self.expanded:
            self.animation.setStartValue(self.body.height())
            self.animation.setEndValue(0)
            self.arrow.setText("▶")
        else:
            target = 320
            self.animation.setStartValue(self.body.maximumHeight())
            self.animation.setEndValue(target)
            self.arrow.setText("▼")
        self.animation.start()
        self.expanded = not self.expanded
        if self.expanded:
            self.command_input.setFocus()

    def collapse(self):
        if self.expanded:
            self.toggle()

    def _toggle_search(self):
        if not self.expanded:
            self.toggle()
        visible = not self.search_input.isVisible()
        self.search_input.setVisible(visible)
        if visible:
            self.search_input.setFocus()
            self.search_input.textChanged.connect(self._on_search_text)

    def _on_search_text(self, text):
        if not text:
            return
        # Подсветить все вхождения
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self.log_view.setTextCursor(cursor)
        if not self.log_view.find(text):
            self.log_view.moveCursor(QTextCursor.Start)

    def _on_new_message(self, msg):
        self.counter.setText(str(get_log_handler().message_count))
        # Превью — последняя строка
        short = msg[:80] + "..." if len(msg) > 80 else msg
        self.preview.setText(short)
