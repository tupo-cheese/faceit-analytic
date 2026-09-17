"""Детектор читерства + калибровка."""
from src.core.analytics.base import BaseAnalyzer


class CheaterDetector(BaseAnalyzer):
    name = "cheater_detector"

    WEIGHTS = {
        "vac_banned": 0.45,
        "game_banned": 0.20,
        "cswatch_cheater": 0.50,
        "cswatch_risk_critical": 0.35,
        "cswatch_risk_high": 0.20,
        "reaction_too_low": 0.25,
        "hs_percent_too_high": 0.15,
        "kd_too_high": 0.20,
        "adr_too_high": 0.15,
    }

    def __init__(self, db=None):
        self.db = db

    def analyze(self, player, matches=None, **kwargs):
        matches = matches or []
        reasons = []
        score = 0.0

        if player.get("vac_banned"):
            score += self.WEIGHTS["vac_banned"]
            reasons.append("VAC-бан")
        if player.get("game_banned"):
            score += self.WEIGHTS["game_banned"]
            reasons.append("Game-бан")
        if player.get("cswatch_cheater"):
            score += self.WEIGHTS["cswatch_cheater"]
            reasons.append("CSWatch: подтверждённый читер")
        risk = (player.get("cswatch_risk") or "").lower()
        if risk == "critical":
            score += self.WEIGHTS["cswatch_risk_critical"]
            reasons.append("CSWatch: критический риск")
        elif risk == "high":
            score += self.WEIGHTS["cswatch_risk_high"]
            reasons.append("CSWatch: высокий риск")

        if matches:
            reaction = [m.get("reaction_time_ms", 0) for m in matches if m.get("reaction_time_ms")]
            hs = [m.get("hs_percent", 0) for m in matches if m.get("hs_percent")]
            adr = [m.get("adr", 0) for m in matches if m.get("adr")]
            kd = [m.get("kd", 0) for m in matches if m.get("kd")]

            if reaction and min(reaction) < 120:
                score += self.WEIGHTS["reaction_too_low"]
                reasons.append(f"Аномально низкое время реакции: {min(reaction):.0f} мс")
            if hs and sum(hs) / len(hs) > 65:
                score += self.WEIGHTS["hs_percent_too_high"]
                reasons.append(f"Слишком высокий HS%: {sum(hs)/len(hs):.1f}")
            if kd and sum(kd) / len(kd) > 2.5:
                score += self.WEIGHTS["kd_too_high"]
                reasons.append(f"Подозрительно высокий K/D: {sum(kd)/len(kd):.2f}")
            if adr and sum(adr) / len(adr) > 120:
                score += self.WEIGHTS["adr_too_high"]
                reasons.append(f"Высокий ADR: {sum(adr)/len(adr):.1f}")

        probability = max(0.0, min(1.0, score))

        calibrated = False
        if self.db and (player.get("vac_banned") or player.get("game_banned")):
            self._calibrate(score, actual=1)
            calibrated = True
        return {
            "steam_id": player.get("steam_id", ""),
            "probability": round(probability * 100, 1),
            "reasons": reasons,
            "calibrated": calibrated,
            "confidence": 0.8 if calibrated else 0.6,
        }

    def _calibrate(self, predicted, actual):
        if self.db:
            self.db.add_calibration_sample("", predicted, actual, {})
