"""Тёмная тема в стиле DeepSeek."""
from src.config import COLORS

DARK_QSS = f"""
QWidget {{
    background-color: #1a1a1a;
    color: #e8e8e8;
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{ background-color: #1a1a1a; }}

/* ── Навигация (страницы) ─────────────────────── */
QPushButton#navTabMain {
    background: #232323;
    color: #a0a0a0;
    border: 1.5px solid #2f2f2f;
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right: none;
    padding: 9px 16px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#navTabMain:hover {
    background: #2a2a2a;
    color: #ffffff;
    border-color: #3a3a3a;
}
QPushButton#navTabMain:checked {
    background: #1e2a4d;
    color: #6a9eff;
    border: 2px solid #4d6bfe;
    border-right: none;
}
QPushButton#navTabRefresh {
    background: #232323;
    color: #a0a0a0;
    border: 1.5px solid #2f2f2f;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    padding: 9px 4px;
    font-size: 16px;
    font-weight: 700;
}
QPushButton#navTabRefresh:hover {
    background: #2a2a2a;
    color: #6a9eff;
    border-color: #4d6bfe;
}
QPushButton#navTabMain {
    background: #232323;
    color: #a0a0a0;
    border: 1.5px solid #2f2f2f;
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right: none;
    padding: 9px 16px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#navTabMain:hover {
    background: #2a2a2a;
    color: #ffffff;
    border-color: #3a3a3a;
}
QPushButton#navTabMain:checked {
    background: #1e2a4d;
    color: #6a9eff;
    border: 2px solid #4d6bfe;
    border-right: none;
}
QPushButton#navTabRefresh {
    background: #232323;
    color: #a0a0a0;
    border: 1.5px solid #2f2f2f;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    padding: 9px 4px;
    font-size: 16px;
    font-weight: 700;
}
QPushButton#navTabRefresh:hover {
    background: #2a2a2a;
    color: #6a9eff;
    border-color: #4d6bfe;
}
QPushButton#navTab {{
    background: #232323;
    color: #a0a0a0;
    border: 1.5px solid #2f2f2f;
    border-radius: 8px;
    padding: 9px 20px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#navTab:hover {{
    background: #2a2a2a;
    color: #ffffff;
    border-color: #3a3a3a;
}}
QPushButton#navTab:checked {{
    background: #1e2a4d;
    color: #6a9eff;
    border: 2px solid #4d6bfe;
}}

/* ── Чипсы источников ─────────────────────────── */
QPushButton#chip {{
    background: #232323;
    color: #a0a0a0;
    border: 1.5px solid #2f2f2f;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    min-width: 60px;
}}
QPushButton#chip:hover {{ background: #2a2a2a; color: #ffffff; }}
QPushButton#chip:checked {{
    background: #1e2a4d;
    color: #6a9eff;
    border: 1.5px solid #4d6bfe;
}}

/* ── Обычные кнопки ───────────────────────────── */
QPushButton {{
    background-color: #232323;
    color: #e8e8e8;
    border: 1.5px solid #2f2f2f;
    border-radius: 8px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: #2a2a2a; border-color: #3a3a3a; }}
QPushButton#accent {{
    background-color: #1e2a4d;
    color: #6a9eff;
    border: 1.5px solid #4d6bfe;
}}
QPushButton#accent:hover {{
    background-color: #253266;
    color: #8fb3ff;
}}
QPushButton#zoomBtn {{
    background: #232323;
    color: #a0a0a0;
    border: 1.5px solid #2f2f2f;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
}}
QPushButton#zoomBtn:hover {{ color: #6a9eff; border-color: #4d6bfe; }}

/* ── Вкладки DeepPage — серые квадратные чипсы ── */
QTabWidget::pane {{
    border: none;
    background: #1a1a1a;
    top: -1px;
}}
QTabBar {{
    background: #1a1a1a;
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: #232323;
    color: #a0a0a0;
    border: 1.5px solid #2f2f2f;
    border-radius: 6px;
    padding: 8px 16px;
    margin: 2px 3px;
    font-size: 12px;
    font-weight: 600;
    min-width: 90px;
}}
QTabBar::tab:hover {{
    background: #2a2a2a;
    color: #ffffff;
    border-color: #3a3a3a;
}}
QTabBar::tab:selected {{
    background: #1e2a4d;
    color: #6a9eff;
    border: 1.5px solid #4d6bfe;
}}

/* ── Ввод ─────────────────────────────────────── */
QLineEdit, QComboBox, QDateEdit, QSpinBox {{
    background-color: #242424;
    border: 1.5px solid #2f2f2f;
    border-radius: 8px;
    padding: 9px 12px;
    color: #e8e8e8;
    font-size: 13px;
    selection-background-color: #4d6bfe;
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{
    border: 1.5px solid #4d6bfe;
    background-color: #2a2a2a;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: #232323;
    border: 1px solid #2f2f2f;
    selection-background-color: #4d6bfe;
}}

/* ── Таблицы ──────────────────────────────────── */
QTableWidget {{
    background-color: #1e1e1e;
    alternate-background-color: #232323;
    gridline-color: transparent;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    font-size: 12px;
}}
QHeaderView::section {{
    background-color: #1a1a1a;
    color: #888888;
    padding: 10px;
    border: none;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
}}

/* ── Прогресс ─────────────────────────────────── */
QProgressBar {{
    background-color: #242424;
    border: none;
    border-radius: 6px;
    height: 10px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4d6bfe, stop:1 #7d9aff);
    border-radius: 6px;
}}

/* ── Скроллбар ────────────────────────────────── */
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{
    background: #333; border-radius: 5px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: #4d6bfe; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

/* ── Служебные ────────────────────────────────── */
QLabel#title {{ font-size: 20px; font-weight: 700; color: #fff; }}
QLabel#subtitle {{ font-size: 12px; color: #888; }}
QLabel#section {{
    font-size: 13px; font-weight: 700; color: #6a9eff; padding: 6px 0;
}}
QFrame#card {{
    background: #1e1e1e;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
}}
QFrame#consoleBar {{
    background: #141414;
    border: 1.5px solid #2a2a2a;
    border-radius: 8px;
}}
QFrame#consoleBar:hover {{ border: 1.5px solid #4d6bfe; }}
QStatusBar {{
    background-color: #1e1e1e;
    color: #888;
    border-top: 1px solid #2a2a2a;
}}
"""
