"""Быстрая аналитика — с доп. инфой и мини-графиками."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QFrame, QScrollArea)
from src.ui.widgets.player_card import PlayerCard
from src.ui.widgets.stat_box import StatBox
from src.ui.widgets.mini_chart import MiniChart
from src.config import COLORS


class QuickPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        main = QHBoxLayout(self)
        main.setSpacing(14)

        # Левая колонка — карточка
        left = QVBoxLayout()
        self.card = PlayerCard()
        left.addWidget(self.card)
        left.addStretch()
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(260)
        main.addWidget(lw)

        # Правая — скролл со всей инфой
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        w = QWidget()
        right = QVBoxLayout(w)
        right.setSpacing(14)

        # ── FACEIT ──
        right.addWidget(self._section("🎮 FACEIT"))
        self.faceit_boxes = self._grid([
            ("faceit_level", "Уровень"),
            ("faceit_elo", "ELO"),
            ("faceit_rank_country", "Топ страны"),
            ("faceit_rank_region", "Топ региона"),
            ("faceit_matches", "Матчей"),
            ("faceit_winrate", "Winrate"),
            ("faceit_kd", "K/D"),
            ("faceit_hs", "HS%"),
            ("faceit_current_streak", "Win streak"),
            ("faceit_longest_streak", "Longest"),
            ("faceit_region", "Регион"),
            ("faceit_url", "FACEIT URL"),
        ], right)
        # Мини-график ELO
        right.addWidget(QLabel("📈 Динамика ELO (последние 20 матчей)"))
        self.elo_chart = MiniChart()
        right.addWidget(self.elo_chart)

        # ── CSStats ──
        right.addWidget(self._section("🎯 CS2 (CSStats)"))
        self.cs2_boxes = self._grid([
            ("kd", "K/D"), ("adr", "ADR"), ("hs", "HS%"),
            ("rating", "Rating"), ("matches", "Матчей"),
            ("wins", "Побед"), ("win_rate", "Winrate"),
            ("kills_total", "Убийств"), ("deaths_total", "Смертей"),
            ("kills_round", "K/R"), ("rating_badge", "Rank badge"),
            ("source", "Источник"),
        ], right)

        # ── CSWatch / CSRep ──
        right.addWidget(self._section("🛡️ CSWatch / CSRep"))
        self.cswatch_boxes = self._grid([
            ("cswatch_reputation", "Репутация"),
            ("cswatch_risk", "Риск"),
            ("vac_banned", "VAC-бан"),
            ("game_banned", "Game-бан"),
            ("trust_score", "Trust Score"),
            ("overwatch_verdict", "Overwatch"),
            ("conviction_count", "Обвинений"),
            ("ai_severity", "AI-тяжесть"),
            ("reaction_time", "Реакция (мс)"),
            ("preaim", "Преаим"),
            ("time_to_damage", "Time to Damage"),
            ("kast", "KAST%"),
        ], right)

        # ── Доп. метрики ──
        right.addWidget(self._section("📊 Доп. метрики"))
        self.extra_boxes = self._grid([
            ("clutch_winrate", "Clutch WR"),
            ("entry_success", "Entry success"),
            ("multi_kill_rounds", "Multi-kill rounds"),
            ("impact_rating", "Impact rating"),
            ("kd_std", "K/D стабильность"),
            ("adr_std", "ADR стабильность"),
        ], right)

        # ── Steam ──
        right.addWidget(self._section("💨 Steam"))
        self.steam_boxes = self._grid([
            ("steam_id", "Steam ID"),
            ("nickname", "Ник"),
            ("visibility", "Профиль"),
            ("country", "Страна"),
        ], right)

        right.addStretch()
        scroll.setWidget(w)
        main.addWidget(scroll, 1)

    def _section(self, text):
        l = QLabel(text)
        l.setObjectName("section")
        return l

    def _grid(self, items, parent_layout):
        grid = QGridLayout()
        grid.setSpacing(8)
        boxes = {}
        for i, (key, label) in enumerate(items):
            b = StatBox(label)
            grid.addWidget(b, i // 4, i % 4)
            boxes[key] = b
        parent_layout.addLayout(grid)
        return boxes

    def set_quick_stats(self, stats):
        def s(boxes, key, value, color=None):
            if key in boxes and value is not None:
                try:
                    boxes[key].set(value, color)
                except Exception:
                    pass

        # FACEIT
        s(self.faceit_boxes, "faceit_level", stats.get("faceit_level", "—"))
        s(self.faceit_boxes, "faceit_elo", stats.get("faceit_elo", "—"))
        s(self.faceit_boxes, "faceit_rank_country", stats.get("faceit_rank_country", "—"))
        s(self.faceit_boxes, "faceit_rank_region", stats.get("faceit_rank_region", "—"))
        s(self.faceit_boxes, "faceit_matches", stats.get("matches_total", "—"))
        wr = stats.get("win_rate", "—")
        c = None
        try:
            v = float(str(wr).replace("%", ""))
            c = COLORS["success"] if v >= 50 else COLORS["danger"]
        except Exception:
            pass
        s(self.faceit_boxes, "faceit_winrate", wr, c)
        s(self.faceit_boxes, "faceit_kd", stats.get("avg_kd", "—"))
        s(self.faceit_boxes, "faceit_hs", stats.get("avg_hs", "—"))
        s(self.faceit_boxes, "faceit_current_streak", stats.get("current_win_streak", "—"))
        s(self.faceit_boxes, "faceit_longest_streak", stats.get("longest_win_streak", "—"))
        s(self.faceit_boxes, "faceit_region", stats.get("faceit_region", "—"))
        url = stats.get("faceit_url", "—")
        s(self.faceit_boxes, "faceit_url", url[:40] if url else "—")

        # CSStats
        cs2 = stats.get("csstats", {}) if isinstance(stats.get("csstats"), dict) else {}
        s(self.cs2_boxes, "kd", cs2.get("kd") or stats.get("kd", "—"))
        s(self.cs2_boxes, "adr", cs2.get("adr") or stats.get("adr", "—"))
        s(self.cs2_boxes, "hs", cs2.get("hs") or stats.get("hs_percent", "—"))
        s(self.cs2_boxes, "rating", cs2.get("rating", "—"))
        s(self.cs2_boxes, "matches", cs2.get("matches_total", "—"))
        s(self.cs2_boxes, "wins", cs2.get("wins", "—"))
        s(self.cs2_boxes, "win_rate", cs2.get("win_rate", "—"))
        s(self.cs2_boxes, "kills_total", cs2.get("kills_total", "—"))
        s(self.cs2_boxes, "deaths_total", cs2.get("deaths_total", "—"))
        s(self.cs2_boxes, "kills_round", cs2.get("kills_round", "—"))
        s(self.cs2_boxes, "rating_badge", cs2.get("rating_badge", "—"))
        s(self.cs2_boxes, "source", cs2.get("source", "—"))

        # CSWatch / CSRep
        s(self.cswatch_boxes, "cswatch_reputation", stats.get("cswatch_reputation", "—"))
        risk = stats.get("cswatch_risk", "—")
        rc = None
        if risk == "critical":
            rc = COLORS["danger"]
        elif risk == "high":
            rc = COLORS["warning"]
        elif risk == "low":
            rc = COLORS["success"]
        s(self.cswatch_boxes, "cswatch_risk", risk, rc)
        vac = "Да" if stats.get("vac_banned") else "Нет"
        s(self.cswatch_boxes, "vac_banned", vac,
          COLORS["danger"] if vac == "Да" else COLORS["success"])
        gb = "Да" if stats.get("game_banned") else "Нет"
        s(self.cswatch_boxes, "game_banned", gb,
          COLORS["danger"] if gb == "Да" else COLORS["success"])
        # CSRep
        s(self.cswatch_boxes, "trust_score", stats.get("trust_score", "—"))
        s(self.cswatch_boxes, "overwatch_verdict", stats.get("overwatch_verdict", "—"))
        s(self.cswatch_boxes, "conviction_count", stats.get("conviction_count", "—"))
        s(self.cswatch_boxes, "ai_severity", stats.get("ai_severity", "—"))
        s(self.cswatch_boxes, "reaction_time", stats.get("reaction_time", "—"))
        s(self.cswatch_boxes, "preaim", stats.get("preaim", "—"))
        s(self.cswatch_boxes, "time_to_damage", stats.get("time_to_damage", "—"))
        s(self.cswatch_boxes, "kast", stats.get("kast", "—"))

        # Extra
        s(self.extra_boxes, "clutch_winrate", stats.get("clutch_winrate", "—"))
        s(self.extra_boxes, "entry_success", stats.get("entry_success", "—"))
        s(self.extra_boxes, "multi_kill_rounds", stats.get("multi_kill_rounds", "—"))
        s(self.extra_boxes, "impact_rating", stats.get("impact_rating", "—"))
        s(self.extra_boxes, "kd_std", stats.get("kd_std", "—"))
        s(self.extra_boxes, "adr_std", stats.get("adr_std", "—"))

        # Steam
        s(self.steam_boxes, "steam_id", stats.get("steam_id", "—"))
        s(self.steam_boxes, "nickname", stats.get("nickname", "—"))
        s(self.steam_boxes, "visibility",
          "Публичный" if stats.get("visibility") == 3 else "Приватный")
        s(self.steam_boxes, "country", stats.get("country", "—"))

        # ELO chart
        elo_history = stats.get("elo_history", [])
        if elo_history:
            self.elo_chart.set_data([e[1] for e in elo_history[-20:]])
