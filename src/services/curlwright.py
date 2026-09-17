"""Обёртка для CurlWright — обход сложных челленджей Cloudflare."""
import subprocess
import json
from pathlib import Path


class CurlWrightWrapper:
    """Запускает CurlWright через subprocess."""

    @staticmethod
    def fetch(url, output_file=None):
        """
        Загружает URL через реальный Chrome.
        Возвращает HTML или None.
        """
        try:
            # CurlWright должен быть установлен: pip install curlwright
            result = subprocess.run(
                ["curlwright", "fetch", url, "--output", "json"],
                capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                html = data.get("body", "")
                if output_file and html:
                    Path(output_file).write_text(html, encoding="utf-8")
                return html
        except FileNotFoundError:
            print("CurlWright не установлен. Установи: pip install curlwright")
        except Exception as e:
            print(f"CurlWright ошибка: {e}")
        return None
