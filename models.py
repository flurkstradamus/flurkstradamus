import math
import re

def calculate_win_prob(target_line, projected_total, std_dev=7.0, is_under=True):
    if std_dev <= 0.2:
        return 1.0 if (projected_total < target_line if is_under else projected_total > target_line) else 0.0
    std_dev = max(std_dev, 0.75)
    z = (target_line - projected_total) / std_dev
    under_prob = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return under_prob if is_under else (1.0 - under_prob)

def calculate_spread_prob(projected_margin, target_spread, std_dev=7.0):
    diff = projected_margin - (-target_spread)
    z = diff / max(std_dev, 1.0)
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def calculate_moneyline_prob(home_proj, away_proj, home_record_str, away_record_str, is_final=False):
    if is_final:
        return 1.0 if home_proj > away_proj else 0.0
    spread_exp = home_proj - away_proj

    def parse_rec(rec):
        parts = re.findall(r"\d+", rec)
        if len(parts) >= 2:
            w, l = float(parts[0]), float(parts[1])
            return w / max(w + l, 1.0)
        return 0.5

    h_pct = parse_rec(home_record_str)
    a_pct = parse_rec(away_record_str)
    record_delta = (h_pct - a_pct) * 7.0

    effective_spread = spread_exp + record_delta
    prob_home_win = 1.0 / (1.0 + math.exp(-effective_spread / 6.5))
    return max(min(prob_home_win, 0.99), 0.01)
