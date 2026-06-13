# strategy/cfr_table.py
# CFR information set abstraction and regret matching

import numpy as np
import pickle

ACTIONS   = ['fold', 'call', 'raise']
N_ACTIONS = len(ACTIONS)

# ── Bucketing thresholds ──────────────────────────────────────
# EHS buckets: 5 levels 
EHS_THRESHOLDS = [0.2, 0.4, 0.6, 0.8]

# Pot odds buckets: 3 levels
POT_ODDS_THRESHOLDS = [0.2, 0.4]

# Opponent range buckets: 3 levels (tight / medium / loose)
# Derived from VPIP passed in from opponent model black box
RANGE_THRESHOLDS = [0.33, 0.66]

STREETS = ['preflop', 'flop', 'turn', 'river']
RAISE_SIZE   = 10

def bucket_ehs(ehs):
    for i, t in enumerate(EHS_THRESHOLDS):
        if ehs < t:
            return i
    return len(EHS_THRESHOLDS)  # bucket 4

def bucket_pot_odds(pot_odds):
    for i, t in enumerate(POT_ODDS_THRESHOLDS):
        if pot_odds < t:
            return i
    return len(POT_ODDS_THRESHOLDS)  # bucket 2

def bucket_range(range_score):
    """
    range_score: scalar in [0,1] from opponent model.
    Low = tight opponent (unlikely to hold strong hands),
    High = loose opponent (wide range).
    """
    for i, t in enumerate(RANGE_THRESHOLDS):
        if range_score < t:
            return i
    return len(RANGE_THRESHOLDS)

def make_info_set(street, ehs, pot_odds, range_score):
    """
    Map continuous inputs to a discrete information set key.
    Total buckets: 4 × 5 × 3 × 3 = 180
    """
    s = STREETS.index(street) if street in STREETS else 0
    e = bucket_ehs(ehs)
    p = bucket_pot_odds(pot_odds)
    r = bucket_range(range_score)
    return (s, e, p, r)

class CFRTable:
    """
    Stores regret sums and strategy sums for each information set.
    """

    def __init__(self):
        # key: info_set tuple → np.array of shape (N_ACTIONS,)
        self.regret_sum   = {}
        self.strategy_sum = {}

    def _init_key(self, key):
        if key not in self.regret_sum:
            self.regret_sum[key]   = np.zeros(N_ACTIONS)
            self.strategy_sum[key] = np.zeros(N_ACTIONS)

    def get_strategy(self, key):
        """
        Regret matching: σ(I, a) = max(regret, 0) / Σ max(regret, 0)
        Falls back to uniform if all regrets ≤ 0.
        """
        self._init_key(key)
        pos_regrets = np.maximum(self.regret_sum[key], 0)
        total       = pos_regrets.sum()

        if total > 0:
            return pos_regrets / total
        else:
            return np.ones(N_ACTIONS) / N_ACTIONS  # uniform

    def update_regret(self, key, action_evs, action_taken_idx):
        """
        Update cumulative regret after observing outcome.
        regret(a) += EV(a) - EV(action_taken)
        """
        self._init_key(key)
        ev_taken = action_evs[action_taken_idx]
        for i in range(N_ACTIONS):
            self.regret_sum[key][i] += action_evs[i] - ev_taken

    def accumulate_strategy(self, key, strategy):
        """Accumulate strategy for final average strategy computation."""
        self._init_key(key)
        self.strategy_sum[key] += strategy

    def get_average_strategy(self, key):
        """Average strategy converges to Nash equilibrium."""
        print("in avg strategy")
        self._init_key(key)
        total = self.strategy_sum[key].sum()
        print(total)
        if total > 0:
            return self.strategy_sum[key] / total
        return np.ones(N_ACTIONS) / N_ACTIONS

    def save(self, path='cfr_strategy.pkl'):
        with open(path, 'wb') as f:
            pickle.dump({
                'regret_sum':   self.regret_sum,
                'strategy_sum': self.strategy_sum
            }, f)
        print(f"CFR table saved to {path}")

    def load(self, path='cfr_strategy.pkl'):
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.regret_sum   = data['regret_sum']
        self.strategy_sum = data['strategy_sum']
        print(f"CFR table loaded from {path}")