
import pickle
import random
import numpy as np
from itertools import combinations
from pypokerengine.engine.deck import Deck
from pypokerengine.engine.card import Card
from pypokerengine.utils.card_utils import estimate_hole_card_win_rate

# ── Parameters ────────────────────────────────────────────────
N_BOARD_SAMPLES = 50    # random boards sampled per hole combo
                         # 50 is fast; 200 is more accurate
N_EHS_SIMS      = 50    # MC sims per EHS estimate inside EHS²
                         # keep low since we call it N_BOARD_SAMPLES times

# ── Build full deck as Card objects ───────────────────────────

deck = Deck()

def get_remaining_deck(known_cards):
    """Remove known cards from deck. Compares by string representation."""
    
    return [c for c in deck.deck if c not in known_cards]

def compute_ehs2_for_hand(hole_cards, n_board_samples=N_BOARD_SAMPLES,
                           n_ehs_sims=N_EHS_SIMS):
    """
    Compute EHS² for a specific hole card combination.

    EHS²(hand) = (1/N) Σ EHS(hand, board_i)²
                 over N randomly sampled complete boards

    Args:
        hole_cards:      list of 2 Card objects
        n_board_samples: number of random boards to sample
        n_ehs_sims:      MC simulations per EHS estimate

    Returns:
        float in [0, 1] — potential-aware hand strength

    Literature: Gilpin et al. (AAAI 2007)
    """
    remaining = get_remaining_deck(hole_cards)
    ehs_squared_values = []

    for _ in range(n_board_samples):
        # Sample a complete 5-card board
        board = random.sample(remaining, 5)

        # Compute EHS on this board
        ehs = estimate_hole_card_win_rate(
            n_ehs_sims, 2, hole_cards, board)

        ehs_squared_values.append(ehs ** 2)

    return float(np.mean(ehs_squared_values))

def compute_ehs2_table(n_board_samples=N_BOARD_SAMPLES,
                        n_ehs_sims=N_EHS_SIMS,
                        save_path='ehs2_table.pkl'):
    """
    Precompute EHS² for all 1326 unique hole card combinations.

    The table maps:
        (card1_str, card2_str) → ehs2_value  float in [0,1]

    Keys are stored as sorted tuples of card strings so lookup
    is order-independent: ('Ah','Kd') == ('Kd','Ah')
    """
    all_combos = list(combinations(deck.deck, 2))
    total      = len(all_combos)   # always 1326
    table      = {}

    print(f"Computing EHS² for {total} hole card combinations...")
    print(f"Board samples per hand: {n_board_samples}")
    print(f"EHS sims per board:     {n_ehs_sims}")
    print(f"Estimated time: "
          f"~{total * n_board_samples * n_ehs_sims // 50000} minutes\n")

    for i, (c1, c2) in enumerate(all_combos):
        hole   = [c1, c2]
        ehs2   = compute_ehs2_for_hand(hole, n_board_samples, n_ehs_sims)

        # Store with sorted key so lookup is order-independent
        key    = tuple(sorted([str(c1), str(c2)]))
        table[key] = ehs2

        if (i + 1) % 100 == 0:
            pct = (i + 1) / total * 100
            print(f"  [{i+1:>4}/{total}] {pct:.1f}% complete  "
                  f"last: {str(c1)}{str(c2)} → EHS²={ehs2:.4f}")

    # Save table
    with open(save_path, 'wb') as f:
        pickle.dump(table, f)

    print(f"\nEHS² table saved to '{save_path}'")
    print(f"Total entries: {len(table)}")

    # Print distribution summary
    values = list(table.values())
    print(f"\nEHS² distribution:")
    print(f"  min:    {min(values):.4f}")
    print(f"  max:    {max(values):.4f}")
    print(f"  mean:   {np.mean(values):.4f}")
    print(f"  median: {np.median(values):.4f}")

    return table

if __name__ == '__main__':
    compute_ehs2_table(
        n_board_samples = 50,
        n_ehs_sims      = 50,
        save_path       = 'ehs2_table.pkl'
    )