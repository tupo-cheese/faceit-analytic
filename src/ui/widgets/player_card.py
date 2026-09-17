"""Карточка игрока с флагом и топом."""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices, QPainter, QPainterPath
from src.config import COLORS

COUNTRY_CODES = {
    "ru": "ru", "ua": "ua", "kz": "kz", "by": "by", "de": "de",
    "fr": "fr", "us": "us", "gb": "gb", "pl": "pl", "se": "se",
    "fi": "fi", "no": "no", "dk": "dk", "nl": "nl", "be": "be",
    "es": "es", "it": "it", "pt": "pt", "tr": "tr", "br": "br",
}


class PlayerCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        self.avatar = QLabel("🎮")
        self.avatar.setFixedSize(110, 110)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setStyleSheet(
            f"background: {COLORS['bg_tertiary']}; border-radius: 55px; "
            "font-size: 48px;")

        nick_row = QHBoxLayout()
        nick_row.addStretch()
        self.flag = QLabel()
        self.flag.setFixedSize(32, 22)
        nick_row.addWidget(self.flag)
        self.nick = QLabel("—")
        self.nick.setObjectName("title")
        nick_row.addWidget(self.nick)
        nick_row.addStretch()

        self.level = QLabel("FACEIT Level —")
        self.level.setObjectName("subtitle")
        self.level.setAlignment(Qt.AlignCenter)

        # 🔥 Топ в стране и регионе
        self.rank_country = QLabel("🌍 Страна: —")
        self.rank_country.setAlignment(Qt.AlignCenter)
        self.rank_country.setStyleSheet(
            f"color: {COLORS['accent']}; font-size: 13px; font-weight: 600;")

        self.rank_region = QLabel("🗺 Регион: —")
        self.rank_region.setAlignment(Qt.AlignCenter)
        self.rank_region.setStyleSheet(
            f"color: {COLORS['accent']}; font-size: 13px; font-weight: 600;")

        btn_row = QHBoxLayout()
        self.btn_steam = QPushButton("Steam")
        self.btn_faceit = QPushButton("FACEIT")
        self.btn_steam.setMinimumHeight(34)
        self.btn_faceit.setMinimumHeight(34)
        self.btn_steam.clicked.connect(self._open_steam)
        self.btn_faceit.clicked.connect(self._open_faceit)
        btn_row.addWidget(self.btn_steam)
        btn_row.addWidget(self.btn_faceit)

        layout.addWidget(self.avatar, alignment=Qt.AlignCenter)
        layout.addLayout(nick_row)
        layout.addWidget(self.level)
        layout.addWidget(self.rank_country)
        layout.addWidget(self.rank_region)
        layout.addLayout(btn_row)
        layout.addStretch()

        self._steam_url = ""
        self._faceit_url = ""

    def set_data(self, data):
        self.nick.setText(data.get("nickname", "—"))
        country = (data.get("country", "") or "").lower()
        code = COUNTRY_CODES.get(country)
        if code:
            self._load_flag(code)
        level = data.get("faceit_level", 0)
        self.level.setText(f"FACEIT Level {level}" if level else "FACEIT Level —")

        # Топ (пока заполним из данных, если есть)
        rc = data.get("faceit_rank_country", "—")
        rr = data.get("faceit_rank_region", "—")
        self.rank_country.setText(f"🌍 Страна: {rc}")
        self.rank_region.setText(f"🗺 Регион: {rr}")

        self._steam_url = data.get("steam_url", "")
        self._faceit_url = data.get("faceit_url", "")
        if data.get("avatar_url"):
            self._load_avatar(data["avatar_url"])

    def _load_flag(self, code):
        import urllib.request
        try:
            req = urllib.request.Request(
                f"https://flagcdn.com/w40/{code}.png",
                headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                pix = QPixmap()
                if pix.loadFromData(resp.read()):
                    self.flag.setPixmap(pix.scaled(
                        32, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            pass

    def _load_avatar(self, url):
        import urllib.request
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                pix = QPixmap()
                if pix.loadFromData(resp.read()):
                    rounded = QPixmap(pix.size())
                    rounded.fill(Qt.transparent)
                    p = QPainter(rounded)
                    p.setRenderHint(QPainter.Antialiasing)
                    path = QPainterPath()
                    path.addEllipse(0, 0, pix.width(), pix.height())
                    p.setClipPath(path)
                    p.drawPixmap(0, 0, pix)
                    p.end()
                    self.avatar.setPixmap(rounded.scaled(
                        110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.avatar.setText("")
                    self.avatar.setStyleSheet("")
        except Exception:
            pass

    def _open_steam(self):
        if self._steam_url:
            QDesktopServices.openUrl(QUrl(self._steam_url))

    def _open_faceit(self):
        if self._faceit_url:
            QDesktopServices.openUrl(QUrl(self._faceit_url))
