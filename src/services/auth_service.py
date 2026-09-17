"""
Сервис безопасной аутентификации через существующую сессию Steam в браузере.
Пароли и 2FA-коды НЕ запрашиваются и НЕ сохраняются.
Cookies хранятся только в оперативной памяти.
"""
import browser_cookie3
from typing import Optional


class AuthService:
    """Извлекает сессионные cookies из браузера для OAuth-входа."""

    SUPPORTED_BROWSERS = {
        "chrome": browser_cookie3.chrome,
        "edge": browser_cookie3.edge,
        "firefox": browser_cookie3.firefox,
        "opera": browser_cookie3.opera,
        "brave": browser_cookie3.brave,
    }

    def __init__(self):
        self._cookies: dict = {}
        self._active_browser: Optional[str] = None

    def detect_browser_session(self) -> list[str]:
        """Проверяет, в каких браузерах есть активная сессия Steam."""
        available = []
        for name, loader in self.SUPPORTED_BROWSERS.items():
            try:
                cj = loader(domain_name="steamcommunity.com")
                if any(c.name == "steamLoginSecure" for c in cj):
                    available.append(name)
            except Exception:
                continue
        return available

    def load_steam_cookies(self, browser: str = "chrome") -> bool:
        """Загружает cookies Steam из указанного браузера в память."""
        loader = self.SUPPORTED_BROWSERS.get(browser)
        if not loader:
            return False
        try:
            cj = loader(domain_name="steamcommunity.com")
            self._cookies = {c.name: c.value for c in cj}
            self._active_browser = browser
            return "steamLoginSecure" in self._cookies
        except Exception:
            return False

    def get_steam_id(self) -> Optional[str]:
        """Извлекает SteamID64 из cookie steamLoginSecure."""
        token = self._cookies.get("steamLoginSecure", "")
        if "||" in token:
            return token.split("||")[0]
        return None

    def get_cookies_dict(self) -> dict:
        """Возвращает cookies для использования в HTTP-запросах."""
        return dict(self._cookies)

    def clear(self):
        """Очищает cookies из памяти."""
        self._cookies.clear()
        self._active_browser = None
