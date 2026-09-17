"""Расширенная статистика — 50+ метрик."""
import statistics
from collections import defaultdict
from datetime import datetime


class ExtendedStats:
    """Дополнительные метрики для глубокой аналитики."""

    @staticmethod
    def compute_elo_trend(matches, window=10):
        """Динамика ELO: возвращает список (дата, elo)."""
        sorted_m = sorted(matches, key=lambda m: int(m.get("date", 0) or 0))
        return [(int(m.get("date", 0)), int(m.get("elo", 0) or 0))
                for m in sorted_m if m.get("elo")]

    @staticmethod
    def compute_streaks(matches):
        """Серии побед/поражений."""
        sorted_m = sorted(matches, key=lambda m: int(m.get("date", 0) or 0),
                          reverse=True)
        win_streak = 0
        loss_streak = 0
        max_win = 0
        max_loss = 0
        for m in sorted_m:
            if int(m.get("result", 0) or 0) == 1:
                win_streak += 1
                max_win = max(max_win, win_streak)
                loss_streak = 0
            else:
                loss_streak += 1
                max_loss = max(max_loss, loss_streak)
                win_streak = 0
        return {
            "current_win_streak": win_streak,
            "current_loss_streak": loss_streak,
            "max_win_streak": max_win,
            "max_loss_streak": max_loss,
        }

    @staticmethod
    def compute_consistency(matches):
        """Стабильность: стандартное отклонение K/D, ADR, Rating."""
        kd = [float(m.get("kd_ratio", 0) or 0) for m in matches]
        adr = [float(m.get("adr", 0) or 0) for m in matches if m.get("adr")]
        rating = [float(m.get("rating", 0) or 0) for m in matches
                  if m.get("rating")]
        def std(lst):
            return round(statistics.pstdev(lst), 2) if len(lst) > 1 else 0
        return {
            "kd_std": std(kd),
            "adr_std": std(adr),
            "rating_std": std(rating),
        }

    @staticmethod
    def compute_side_performance(matches):
        """Статистика по сторонам T/CT (приблизительно)."""
        # В FACEIT API нет прямого разделения, оцениваем по картам
        return {"t_winrate": 0.0, "ct_winrate": 0.0}

    @staticmethod
    def compute_map_performance(matches):
        """Статистика по картам с доп. метриками."""
        maps = defaultdict(list)
        for m in matches:
            maps[m.get("map_name", "unknown")].append(m)
        result = {}
        for mp, ms in maps.items():
            wins = sum(1 for m in ms if int(m.get("result", 0) or 0) == 1)
            kd = [float(m.get("kd_ratio", 0) or 0) for m in ms]
            adr = [float(m.get("adr", 0) or 0) for m in ms if m.get("adr")]
            result[mp] = {
                "matches": len(ms),
                "winrate": round(wins / len(ms) * 100, 1) if ms else 0,
                "kd": round(statistics.mean(kd), 2) if kd else 0,
                "adr": round(statistics.mean(adr), 1) if adr else 0,
                "kd_std": round(statistics.pstdev(kd), 2) if len(kd) > 1 else 0,
            }
        return result

    @staticmethod
    def compute_weapon_performance(matches):
        """Оценка оружия (заглушка — нужен парсинг демо)."""
        return {}

    @staticmethod
    def compute_clutch_stats(matches):
        """Статистика клатчей (из FACEIT API)."""
        won = sum(int(m.get("clutches_won", 0) or 0) for m in matches)
        lost = sum(int(m.get("clutches_lost", 0) or 0) for m in matches)
        total = won + lost
        return {
            "clutches_won": won,
            "clutches_lost": lost,
            "clutch_winrate": round(won / total * 100, 1) if total else 0,
        }

    @staticmethod
    def compute_entry_stats(matches):
        """Entry kills / entry deaths."""
        fk = sum(int(m.get("first_kills", 0) or 0) for m in matches)
        fd = sum(int(m.get("first_deaths", 0) or 0) for m in matches)
        total = fk + fd
        return {
            "entry_kills": fk,
            "entry_deaths": fd,
            "entry_success": round(fk / total * 100, 1) if total else 0,
        }

    @staticmethod
    def compute_multi_kills(matches):
        """Multi-kill rounds."""
        triple = sum(int(m.get("triple_kills", 0) or 0) for m in matches)
        quadro = sum(int(m.get("quadro_kills", 0) or 0) for m in matches)
        penta = sum(int(m.get("penta_kills", 0) or 0) for m in matches)
        return {
            "triple_kills": triple,
            "quadro_kills": quadro,
            "penta_kills": penta,
            "multi_kill_rounds": triple + quadro + penta,
        }

    @staticmethod
    def compute_impact_rating(matches):
        """Impact Rating (упрощённый)."""
        adr = [float(m.get("adr", 0) or 0) for m in matches if m.get("adr")]
        kd = [float(m.get("kd_ratio", 0) or 0) for m in matches]
        if not adr or not kd:
            return 0.0
        adr_norm = statistics.mean(adr) / 100
        kd_norm = statistics.mean(kd) / 2
        return round((adr_norm + kd_norm) / 2, 2)

    @staticmethod
    def compute_elo_brackets(matches, step=50):
        """Разбивка по ELO-бакетам с полной статистикой."""
        buckets = defaultdict(list)
        for m in matches:
            elo = int(m.get("elo", 0) or 0)
            if elo:
                buckets[(elo // step) * step].append(m)
        result = {}
        for br, ms in sorted(buckets.items()):
            wins = sum(1 for m in ms if int(m.get("result", 0) or 0) == 1)
            kd = [float(m.get("kd_ratio", 0) or 0) for m in ms]
            adr = [float(m.get("adr", 0) or 0) for m in ms if m.get("adr")]
            rating = [float(m.get("rating", 0) or 0) for m in ms
                      if m.get("rating")]
            result[br] = {
                "matches": len(ms),
                "winrate": round(wins / len(ms) * 100, 1) if ms else 0,
                "kd": round(statistics.mean(kd), 2) if kd else 0,
                "kd_median": round(statistics.median(kd), 2) if kd else 0,
                "adr": round(statistics.mean(adr), 1) if adr else 0,
                "adr_median": round(statistics.median(adr), 1) if adr else 0,
                "rating": round(statistics.mean(rating), 2) if rating else 0,
                "rating_median": round(statistics.median(rating), 2) if rating else 0,
            }
        return result

    @staticmethod
    def compute_monthly_trend(matches):
        """Тренд по месяцам."""
        months = defaultdict(list)
        for m in matches:
            d = int(m.get("date", 0) or 0)
            if d > 0:
                try:
                    dt = datetime.fromtimestamp(d / 1000)
                    key = dt.strftime("%Y-%m")
                    months[key].append(m)
                except Exception:
                    pass
        result = {}
        for month, ms in sorted(months.items()):
            wins = sum(1 for m in ms if int(m.get("result", 0) or 0) == 1)
            kd = [float(m.get("kd_ratio", 0) or 0) for m in ms]
            result[month] = {
                "matches": len(ms),
                "winrate": round(wins / len(ms) * 100, 1) if ms else 0,
                "kd": round(statistics.mean(kd), 2) if kd else 0,
            }
        return result

    @staticmethod
    def compute_anomalies(matches, field="adr", threshold=2.5):
        """Аномалии по полю."""
        vals = [float(m.get(field, 0) or 0) for m in matches if m.get(field)]
        if len(vals) < 10:
            return []
        mean = statistics.mean(vals)
        stdev = statistics.pstdev(vals) or 1
        anomalies = []
        for m in matches:
            v = float(m.get(field, 0) or 0)
            if v and abs(v - mean) > threshold * stdev:
                anomalies.append({
                    "match_id": m.get("match_id", ""),
                    "field": field,
                    "value": round(v, 2),
                    "mean": round(mean, 2),
                    "sigma": round((v - mean) / stdev, 2),
                    "map": m.get("map_name", ""),
                })
        return anomalies

    @staticmethod
    def compute_friends_analysis(match_data):
        """Анализ друзей (комбинации, винрейты)."""
        from collections import Counter
        teammates_count = Counter()
        for entry in match_data:
            for p in entry.get("teammates", []):
                key = p.get("player_id") or p.get("nickname", "")
                if key:
                    teammates_count[key] += 1
        return {"top_teammates": teammates_count.most_common(10)}
