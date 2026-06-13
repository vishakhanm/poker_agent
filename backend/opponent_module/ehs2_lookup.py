# strategy/ehs2_lookup.py
# Runtime lookup of precomputed EHS² values
# Used in player.py to get opponent range bucket

import pickle
import numpy as np

# Opponent range buckets derived from EHS² distribution
# These thresholds split hands into tight/medium/loose thirds
# Literature: Gilpin et al. (AAAI 2007) — potential-aware bucketing
EHS2_RANGE_THRESHOLDS = [0.25, 0.50]   # tune after seeing distribution

class EHS2Lookup:
    """
    Loads precomputed EHS² table and provides:
      1. Raw EHS² value for any hole card combination
      2. Opponent range score in [0,1] from EHS²
         (used as the range_bucket input to the CFR table)
    """

    def __init__(self, table_path='opponent_module/ehs2_table.pkl'):
        with open(table_path, 'rb') as f:
            self.table = pickle.load(f)
        # print(f"[EHS2Lookup] Loaded {len(self.table)} entries "
        #       f"from '{table_path}'")

    def get_ehs2(self, hole_cards):
        """
        Look up EHS² for a hole card pair.

        Args:
            hole_cards: list of 2 Card objects

        Returns:
            float in [0,1] — potential-aware hand strength
        """
        key = tuple(sorted([str(c) for c in hole_cards]))
        if key not in self.table:
            # Fallback for unseen combos (should not happen)
            return 0.5
        return self.table[key]

    def get_range_score(self, hole_cards):
        """
        Convert EHS² to a range looseness score in [0,1].

        Low EHS²  → strong hand  → tight range  → score near 0
        High EHS² → weak hand    → loose range   → score near 1

        This inversion is intentional: a player holding a strong
        hand (high EHS²) is playing a "tight" range in the sense
        that they are selective — but from the OPPONENT's perspective,
        seeing raises from such a player signals strength.

        The CFR table uses this score to bucket opponent behavior.
        """
        ehs2 = self.get_ehs2(hole_cards)

        # Normalize to [0,1] range score
        # EHS²=0.8 (strong hand) → range_score near 0 (tight)
        # EHS²=0.1 (weak hand)   → range_score near 1 (loose)
        range_score = 1.0 - ehs2
        return float(range_score)