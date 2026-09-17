import statistics
from collections import defaultdict


def _mean(vals):
    return round(statistics.mean(vals), 2) if vals else 0.0

def _median(vals):
    return round(statistics.median(vals), 2) if vals else 0.0

def _std(vals):
    return round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0

def _safe_div(a, b, default=0.0):
    try:
        return a / b if b else default
    except Exception:
        return default


class DeepConclusions:
    """Глубокая аналитика по match_data."""

    def __init__(self, friends_set=None):
        self.friends_set = friends_set or set()

    def analyze(self, match_data):
        if not match_data:
            return {}
        self.md = match_data
        return {
            'by_party': self._party(),
            'by_country_teammates': self._country_teammates(),
            'by_country_enemies': self._country_enemies(),
            'friends_impact': self._friends(),
            'teammate_impact': self._teammates(),
            'enemy_impact': self._enemies(),
            'own_performance': self._own(),
            'elo_context': self._elo_ctx(),
            'map_impact': self._maps(),
            'trends': self._trends(),
            'anomalies': self._anomalies(),
            'match_count_distribution': self._exp(),
        }

    def _party(self):
        b = defaultdict(list)
        for e in self.md:
            b[e.get('party_size', 1)].append(e)
        out = {}
        for size, ms in sorted(b.items()):
            wins = sum(1 for m in ms if m.get('result') == 1)
            kd = [float((m.get('my_stats') or {}).get('kd_ratio', 0) or 0) for m in ms]
            adr = [float((m.get('my_stats') or {}).get('adr', 0) or 0) for m in ms
                   if (m.get('my_stats') or {}).get('adr')]
            out[str(size)] = {
                'matches': len(ms),
                'winrate': round(_safe_div(wins, len(ms)) * 100, 1),
                'my_kd': _mean(kd),
                'my_adr': _mean(adr),
            }
        return out

    def _country_teammates(self):
        agg = defaultdict(lambda: {'n': 0, 'wins': 0, 'kd': [], 'adr': [],
                                    'my_kd': [], 'my_adr': [], 'rating': []})
        for e in self.md:
            won = 1 if e.get('result') == 1 else 0
            my = e.get('my_stats') or {}
            for p in e.get('teammates', []):
                c = (p.get('country') or '?').lower()
                a = agg[c]
                a['n'] += 1; a['wins'] += won
                if p.get('kd_ratio'): a['kd'].append(float(p['kd_ratio']))
                if p.get('adr'):      a['adr'].append(float(p['adr']))
                if p.get('rating'):   a['rating'].append(float(p['rating']))
                if my.get('kd_ratio'): a['my_kd'].append(float(my['kd_ratio']))
                if my.get('adr'):      a['my_adr'].append(float(my['adr']))
        out = {}
        for c, a in sorted(agg.items(), key=lambda x: -x[1]['n'])[:25]:
            out[c] = {
                'count': a['n'],
                'winrate': round(_safe_div(a['wins'], a['n']) * 100, 1),
                'avg_kd': _mean(a['kd']),
                'avg_adr': _mean(a['adr']),
                'avg_rating': _mean(a['rating']),
                'my_kd_with_them': _mean(a['my_kd']),
                'my_adr_with_them': _mean(a['my_adr']),
            }
        return out

    def _country_enemies(self):
        agg = defaultdict(lambda: {'n': 0, 'wins': 0, 'kd': [], 'adr': [],
                                    'my_kd': [], 'my_adr': []})
        for e in self.md:
            won = 1 if e.get('result') == 1 else 0
            my = e.get('my_stats') or {}
            for p in e.get('enemies', []):
                c = (p.get('country') or '?').lower()
                a = agg[c]
                a['n'] += 1; a['wins'] += won
                if p.get('kd_ratio'): a['kd'].append(float(p['kd_ratio']))
                if p.get('adr'):      a['adr'].append(float(p['adr']))
                if my.get('kd_ratio'): a['my_kd'].append(float(my['kd_ratio']))
                if my.get('adr'):      a['my_adr'].append(float(my['adr']))
        out = {}
        for c, a in sorted(agg.items(), key=lambda x: -x[1]['n'])[:25]:
            out[c] = {
                'count': a['n'],
                'loss_rate': round((1 - _safe_div(a['wins'], a['n'])) * 100, 1),
                'avg_kd': _mean(a['kd']),
                'avg_adr': _mean(a['adr']),
                'my_kd_vs': _mean(a['my_kd']),
                'my_adr_vs': _mean(a['my_adr']),
            }
        return out

    def _friends(self):
        by = defaultdict(lambda: {'w_n': 0, 'w_wins': 0, 'kd': [], 'adr': [], 'rt': []})
        base = {'win': 0, 'n': 0, 'kd': [], 'adr': []}
        for e in self.md:
            won = 1 if e.get('result') == 1 else 0
            my = e.get('my_stats') or {}
            hit = False
            for p in e.get('teammates', []):
                k = p.get('player_id') or p.get('nickname', '')
                if k in self.friends_set:
                    hit = True
                    a = by[k]
                    a['w_n'] += 1; a['w_wins'] += won
                    if my.get('kd_ratio'): a['kd'].append(float(my['kd_ratio']))
                    if my.get('adr'):      a['adr'].append(float(my['adr']))
                    if my.get('rating'):   a['rt'].append(float(my['rating']))
            if not hit:
                base['n'] += 1; base['win'] += won
                if my.get('kd_ratio'): base['kd'].append(float(my['kd_ratio']))
                if my.get('adr'):      base['adr'].append(float(my['adr']))
        base_wr = _safe_div(base['win'], base['n']) * 100
        base_kd = _mean(base['kd'])
        base_adr = _mean(base['adr'])
        out = {}
        for k, a in sorted(by.items(), key=lambda x: -x[1]['w_n'])[:30]:
            wr = _safe_div(a['w_wins'], a['w_n']) * 100
            out[k] = {
                'matches': a['w_n'],
                'winrate': round(wr, 1),
                'winrate_delta': round(wr - base_wr, 1),
                'my_kd': _mean(a['kd']),
                'my_kd_delta': round(_mean(a['kd']) - base_kd, 2),
                'my_adr': _mean(a['adr']),
                'my_adr_delta': round(_mean(a['adr']) - base_adr, 1),
                'my_rating': _mean(a['rt']),
            }
        out['__baseline__'] = {
            'matches': base['n'], 'winrate': round(base_wr, 1),
            'my_kd': base_kd, 'my_adr': base_adr,
        }
        return out

    def _teammates(self):
        by = defaultdict(lambda: {'n': 0, 'wins': 0, 'kd': [], 'adr': [],
                                   'rt': [], 'country': '', 'nick': ''})
        for e in self.md:
            won = 1 if e.get('result') == 1 else 0
            for p in e.get('teammates', []):
                k = p.get('player_id') or p.get('nickname', '')
                if not k: continue
                a = by[k]
                a['n'] += 1; a['wins'] += won
                a['nick'] = p.get('nickname', '')
                a['country'] = p.get('country', '')
                if p.get('kd_ratio'): a['kd'].append(float(p['kd_ratio']))
                if p.get('adr'):      a['adr'].append(float(p['adr']))
                if p.get('rating'):   a['rt'].append(float(p['rating']))
        arr = []
        for k, a in by.items():
            if a['n'] < 2: continue
            arr.append({
                'key': k, 'nick': a['nick'], 'country': a['country'],
                'matches': a['n'],
                'winrate': round(_safe_div(a['wins'], a['n']) * 100, 1),
                'kd': _mean(a['kd']), 'adr': _mean(a['adr']),
                'rating': _mean(a['rt']),
            })
        arr.sort(key=lambda x: (-x['winrate'], -x['matches']))
        return {'best': arr[:10], 'worst': arr[-10:][::-1] if len(arr) > 10 else arr[::-1][:10]}

    def _enemies(self):
        by = defaultdict(lambda: {'n': 0, 'wins': 0, 'kd': [], 'adr': [],
                                   'country': '', 'nick': ''})
        for e in self.md:
            won = 1 if e.get('result') == 1 else 0
            for p in e.get('enemies', []):
                k = p.get('player_id') or p.get('nickname', '')
                if not k: continue
                a = by[k]
                a['n'] += 1; a['wins'] += won
                a['nick'] = p.get('nickname', '')
                a['country'] = p.get('country', '')
                if p.get('kd_ratio'): a['kd'].append(float(p['kd_ratio']))
                if p.get('adr'):      a['adr'].append(float(p['adr']))
        arr = []
        for k, a in by.items():
            if a['n'] < 2: continue
            arr.append({
                'key': k, 'nick': a['nick'], 'country': a['country'],
                'matches': a['n'],
                'loss_rate': round((1 - _safe_div(a['wins'], a['n'])) * 100, 1),
                'kd': _mean(a['kd']), 'adr': _mean(a['adr']),
            })
        arr.sort(key=lambda x: (-x['loss_rate'], -x['matches']))
        return {'toughest': arr[:10]}

    def _own(self):
        kd, adr, hs, rt, wins, n = [], [], [], [], 0, 0
        for e in self.md:
            me = e.get('my_stats') or {}
            n += 1
            if e.get('result') == 1: wins += 1
            if me.get('kd_ratio'): kd.append(float(me['kd_ratio']))
            if me.get('adr'):      adr.append(float(me['adr']))
            if me.get('headshots_percent'): hs.append(float(me['headshots_percent']))
            if me.get('rating'):   rt.append(float(me['rating']))
        return {
            'matches': n,
            'winrate': round(_safe_div(wins, n) * 100, 1),
            'kd_avg': _mean(kd), 'kd_med': _median(kd), 'kd_std': _std(kd),
            'adr_avg': _mean(adr), 'adr_med': _median(adr), 'adr_std': _std(adr),
            'hs_avg': _mean(hs), 'hs_med': _median(hs),
            'rating_avg': _mean(rt),
            'kd_consistency': round(100 - min(100, _std(kd) * 40), 1) if kd else 0,
        }

    def _elo_ctx(self):
        rows = []
        for e in self.md:
            my = e.get('my_stats') or {}
            my_elo = int(my.get('player_elo', 0) or 0)
            if not my_elo:
                my_elo = int(e.get('elo', 0) or 0)
            lobby = int(e.get('elo', 0) or 0)
            if my_elo and lobby:
                rows.append({'my': my_elo, 'lobby': lobby,
                             'delta': my_elo - lobby,
                             'won': 1 if e.get('result') == 1 else 0})
        if not rows: return {}
        my_elos = [r['my'] for r in rows]
        lb_elos = [r['lobby'] for r in rows]
        above = [r for r in rows if r['delta'] > 30]
        below = [r for r in rows if r['delta'] < -30]
        even  = [r for r in rows if -30 <= r['delta'] <= 30]
        def wr(rs): return round(_safe_div(sum(r['won'] for r in rs), len(rs)) * 100, 1) if rs else 0
        return {
            'my_elo_min': min(my_elos), 'my_elo_max': max(my_elos),
            'lobby_elo_min': min(lb_elos), 'lobby_elo_max': max(lb_elos),
            'winrate_above_lobby': wr(above),
            'winrate_below_lobby': wr(below),
            'winrate_even_lobby': wr(even),
            'samples_above': len(above), 'samples_below': len(below),
            'samples_even': len(even),
        }

    def _maps(self):
        by = defaultdict(lambda: {'n': 0, 'wins': 0, 'kd': [], 'adr': []})
        for e in self.md:
            mp = e.get('map_name', '?')
            a = by[mp]
            a['n'] += 1
            a['wins'] += 1 if e.get('result') == 1 else 0
            me = e.get('my_stats') or {}
            if me.get('kd_ratio'): a['kd'].append(float(me['kd_ratio']))
            if me.get('adr'):      a['adr'].append(float(me['adr']))
        out = {}
        for mp, a in by.items():
            out[mp] = {
                'matches': a['n'],
                'winrate': round(_safe_div(a['wins'], a['n']) * 100, 1),
                'kd': _mean(a['kd']), 'adr': _mean(a['adr']),
            }
        return out

    def _trends(self):
        if len(self.md) < 10: return {}
        s = sorted(self.md, key=lambda m: int(m.get('date', 0) or 0), reverse=True)
        def block(ms):
            n = len(ms)
            wins = sum(1 for m in ms if m.get('result') == 1)
            kd = [float((m.get('my_stats') or {}).get('kd_ratio', 0) or 0)
                  for m in ms if (m.get('my_stats') or {}).get('kd_ratio')]
            adr = [float((m.get('my_stats') or {}).get('adr', 0) or 0)
                   for m in ms if (m.get('my_stats') or {}).get('adr')]
            return {'n': n, 'wr': round(_safe_div(wins, n) * 100, 1),
                    'kd': _mean(kd), 'adr': _mean(adr)}
        a, b = block(s[:10]), block(s[10:20])
        return {'last_10': a, 'prev_10': b,
                'wr_delta': round(a['wr'] - b['wr'], 1),
                'kd_delta': round(a['kd'] - b['kd'], 2),
                'adr_delta': round(a['adr'] - b['adr'], 1)}

    def _anomalies(self):
        out = []
        kd = [float((m.get('my_stats') or {}).get('kd_ratio', 0) or 0)
              for m in self.md if (m.get('my_stats') or {}).get('kd_ratio')]
        adr = [float((m.get('my_stats') or {}).get('adr', 0) or 0)
               for m in self.md if (m.get('my_stats') or {}).get('adr')]
        if len(kd) >= 8:
            m, s = statistics.mean(kd), statistics.pstdev(kd) or 1
            for v in kd:
                if abs(v - m) > 2.5 * s:
                    out.append({'field': 'kd', 'value': round(v, 2),
                                'mean': round(m, 2), 'sigma': round((v - m) / s, 2)})
        if len(adr) >= 8:
            m, s = statistics.mean(adr), statistics.pstdev(adr) or 1
            for v in adr:
                if abs(v - m) > 2.5 * s:
                    out.append({'field': 'adr', 'value': round(v, 1),
                                'mean': round(m, 1), 'sigma': round((v - m) / s, 2)})
        return out[:20]

    def _exp(self):
        c = []
        for e in self.md:
            for p in e.get('teammates', []) + e.get('enemies', []):
                mc = int(p.get('player_matches', 0) or 0)
                if mc > 0: c.append(mc)
        if not c: return {}
        c.sort()
        return {'min': c[0], 'max': c[-1], 'avg': round(statistics.mean(c)),
                'med': int(statistics.median(c)), 'samples': len(c)}
