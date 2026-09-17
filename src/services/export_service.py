"""Экспорт/импорт данных."""
import shutil
from pathlib import Path
from src.config import DATA_DIR


class ExportService:
    @staticmethod
    def export_all(dest_zip):
        shutil.make_archive(str(dest_zip.with_suffix("")), "zip", DATA_DIR)

    @staticmethod
    def import_all(src_zip):
        shutil.unpack_archive(str(src_zip), str(DATA_DIR))
