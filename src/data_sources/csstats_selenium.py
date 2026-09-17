"""CSStats через Selenium (опционально)."""
import logging

logger = logging.getLogger("faceit_analytics")

# Мягкий импорт — если нет selenium, класс просто не работает
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    webdriver = None


class CSStatsSelenium:
    def __init__(self):
        self.driver = None
        self.enabled = SELENIUM_AVAILABLE

    def _get_driver(self):
        if not SELENIUM_AVAILABLE:
            return None
        if self.driver is None:
            opts = Options()
            opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36")
            try:
                self.driver = webdriver.Chrome(options=opts)
            except Exception as e:
                logger.error(f"Selenium init: {e}")
                self.enabled = False
                return None
        return self.driver

    def fetch_player_stats(self, steam_id):
        import time
        import re
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium не установлен")
            return {}
        driver = self._get_driver()
        if not driver:
            return {}
        try:
            driver.get(f"https://csstats.gg/player/{steam_id}")
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(8)
            html = driver.page_source
            stats = {}
            patterns = {
                "kd": r'K/D(?:\s*Ratio)?[^0-9\-]{0,30}([\d.]+)',
                "adr": r'ADR[^0-9\-]{0,30}([\d.]+)',
                "hs": r'HS%[^0-9\-]{0,30}([\d.]+)',
                "kills_total": r'Kills[^0-9\-]{0,30}(\d+)',
                "deaths_total": r'Deaths[^0-9\-]{0,30}(\d+)',
            }
            for key, pat in patterns.items():
                m = re.search(pat, html, re.I)
                if m:
                    stats[key] = m.group(1)
            return stats
        except Exception as e:
            logger.error(f"CSStats Selenium: {e}")
            return {}

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
