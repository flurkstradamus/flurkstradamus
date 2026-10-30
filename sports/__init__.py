"""Sports package initializer for Flurkstradamus."""

# Football exports
try:
    from .football import fetch_football_scoreboard, get_live_football_roster
except Exception:
    def fetch_football_scoreboard(): return []
    def get_live_football_roster(*args, **kwargs): return []

# Basketball exports
try:
    from .basketball import fetch_nba_scoreboard
except Exception:
    def fetch_nba_scoreboard(): return []

try:
    from .basketball import get_live_nba_roster
except Exception:
    def get_live_nba_roster(*args, **kwargs): return []

try:
    from .basketball import get_live_nba_3pm_roster
except Exception:
    def get_live_nba_3pm_roster(*args, **kwargs): return []

try:
    from .basketball import fetch_nba_injury_set
except Exception:
    def fetch_nba_injury_set(): return set()

__all__ = [
    "fetch_football_scoreboard",
    "get_live_football_roster",
    "fetch_nba_scoreboard",
    "get_live_nba_roster",
    "get_live_nba_3pm_roster",
    "fetch_nba_injury_set",
]
