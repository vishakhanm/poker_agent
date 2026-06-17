# strategy/cfr_train.py
# TRUE self-play CFR for heads-up limit hold'em
# Both players traverse the game tree and update regrets simultaneously
# Literature: Zinkevich et al. (NIPS 2007), Neller & Lanctot (2013)

from itertools import combinations
import random
import numpy as np
import pickle
from collections import defaultdict

from pypokerengine.engine.deck import Deck
from pypokerengine.utils.card_utils import HandEvaluator, estimate_hole_card_win_rate
# from strategy.ehs import monte_carlo_ehs, FULL_DECK, evaluate_hand
from cfr_table import (CFRTable, make_info_set,
                                 ACTIONS, STREETS)

NUM_ITERATIONS = 10000
SMALL_BLIND    = 10
BIG_BLIND      = 20
RAISE_SIZE     = 10
MAX_RAISES     = 4

# ── Game state representation ─────────────────────────────────

class GameState:
    """
    Represents a single point in the game tree.
    Both players share the same community cards but have
    private hole cards — this is the imperfect information.
    """
    def __init__(self, p0_hole, p1_hole, community,
                 street_idx, pot, p0_bet, p1_bet,
                 raises_this_street, acting_player,
                 p0_folded=False, p1_folded=False):

        self.p0_hole           = p0_hole       # private to player 0
        self.p1_hole           = p1_hole       # private to player 1
        self.community         = community     # shared — grows each street
        self.street_idx        = street_idx   # 0=preflop,1=flop,2=turn,3=river
        self.pot               = pot
        self.p0_bet            = p0_bet        # what p0 has put in THIS street
        self.p1_bet            = p1_bet
        self.raises_this_street = raises_this_street
        self.acting_player     = acting_player # 0 or 1
        self.p0_folded         = p0_folded
        self.p1_folded         = p1_folded

    @property
    def street(self):
        return STREETS[self.street_idx]

    @property
    def is_terminal(self):
        return self.p0_folded or self.p1_folded or self.street_idx > 3

    def call_amount(self):
        """How much the acting player needs to put in to call."""
        if self.acting_player == 0:
            return max(0, self.p1_bet - self.p0_bet)
        else:
            return max(0, self.p0_bet - self.p1_bet)

    def can_raise(self):
        return self.raises_this_street < MAX_RAISES

    def get_info_set_key(self, player, ehs, opp_range):
        """
        Build abstracted information set for this player.
        Each player only sees their own hole cards + community.
        The information set abstracts away the exact cards.
        """
        call_amt  = self.call_amount()
        denom     = self.pot + call_amt
        pot_odds  = (call_amt / denom) if denom > 0 else 0.0
        return make_info_set(self.street, ehs, pot_odds, opp_range)


def deal_hands(deck, hole):
    """Deal two private hands and 5 community cards from a shuffled deck."""
    remaining = [c for c in deck.deck if c not in hole]  
     
    p1_hole   = remaining[0:2]
    community = remaining[2:7]   # all 5 — revealed progressively
    return p1_hole, community

def terminal_payoff(state):
    """
    Compute payoff for player 0 at a terminal node.
    Player 1 payoff = -player 0 payoff (zero sum).
    """
    if state.p0_folded:
        return -state.pot / 2   # p0 loses what's in pot
    if state.p1_folded:
        return state.pot / 2    # p0 wins what's in pot

    # Showdown — reveal all 5 community cards
    board    = state.community   # all 5 cards
    p0_score = HandEvaluator.eval_hand(state.p0_hole, board)
    p1_score = HandEvaluator.eval_hand(state.p1_hole, board)

    if p0_score > p1_score:
        return state.pot / 2
    elif p1_score > p0_score:
        return -state.pot / 2
    else:
        return 0.0   # split pot


# ── Core CFR traversal ────────────────────────────────────────

class SelfPlayCFR:
    """
    Vanilla CFR with abstracted information sets.

    At each decision node, both players:
    1. Compute current strategy via regret matching
    2. Compute COUNTERFACTUAL value of each action
    3. Update regrets: regret(a) += cfv(a) - cfv(strategy played)
    4. Accumulate strategy for average strategy computation

    Literature:
        Zinkevich et al. "Regret Minimization in Games with
        Incomplete Information" (NIPS 2007)
        Neller & Lanctot "An Introduction to CFR" (2013)
    """

    def __init__(self):
        self.table = CFRTable()
        # EHS cache: avoid recomputing for same cards
        self._ehs_cache = {}

    def get_ehs(self, hole, community):
        # key = (tuple(hole), tuple(community))
        hole_key = tuple(str(c) for c in hole)
        comm_key = tuple(str(c) for c in community)
        key = (hole_key, comm_key)
        # print(key)
        if key not in self._ehs_cache:
            self._ehs_cache[key] = estimate_hole_card_win_rate(100, 2, hole, community)
        return self._ehs_cache[key]
    

    def cfr(self, state, p0_reach, p1_reach):
        """
        Recursive CFR traversal.

        Args:
            state:     current GameState
            p0_reach:  probability of reaching this node under p0's strategy
            p1_reach:  probability of reaching this node under p1's strategy

        Returns:
            float: expected payoff for player 0
        """

        # ── Terminal node ─────────────────────────────────────
        if state.is_terminal:
            return terminal_payoff(state)

        # ── Chance node: deal next street's community cards ───
        # Between streets, if both players have matched bets,
        # reveal the next community cards (nature's move)
        bets_equal   = state.p0_bet == state.p1_bet
        street_active = state.raises_this_street > 0
        is_preflop   = state.street_idx == 0

        if bets_equal and (street_active or is_preflop):
        # if (state.p0_bet == state.p1_bet and
        #         state.raises_this_street > 0 or
        #         state.street_idx == 0 and state.p0_bet == state.p1_bet):

            next_street_idx = state.street_idx + 1
            if next_street_idx > 3:
                # All streets done → showdown
                terminal_state       = GameState(
                    state.p0_hole, state.p1_hole,
                    state.community, 4,   # > 3 triggers terminal
                    state.pot, 0, 0, 0,
                    0
                )
                return terminal_payoff(terminal_state)

            # Nature moves: next street revealed (no choice, just advance)
            next_state = GameState(
                p0_hole            = state.p0_hole,
                p1_hole            = state.p1_hole,
                community          = state.community,  # already have all 5
                street_idx         = next_street_idx,
                pot                = state.pot,
                p0_bet             = 0,
                p1_bet             = 0,
                raises_this_street = 0,
                acting_player      = 0   # SB acts first post-flop
            )
            return self.cfr(next_state, p0_reach, p1_reach)

        # ── Decision node ─────────────────────────────────────
        player       = state.acting_player
        opponent     = 1 - player

        # Get this player's hole cards and visible community cards
        n_visible    = [0, 3, 4, 5][state.street_idx]
        visible_comm = state.community[:n_visible]
        hole         = state.p0_hole if player == 0 else state.p1_hole

        # Compute EHS for this player's perspective
        ehs          = self.get_ehs(hole, visible_comm)

        # Opponent range: in true CFR this would be the full
        # range distribution. Here we use a scalar approximation
        # (the average EHS the opponent could have given the board)
        opp_hole     = state.p1_hole if player == 0 else state.p0_hole
        opp_ehs      = self.get_ehs(opp_hole, visible_comm)
        # Convert opponent EHS to a range looseness score
        opp_range    = opp_ehs

        # Build abstracted information set
        key          = state.get_info_set_key(player, ehs, opp_range)

        # Get current strategy via regret matching
        strategy     = self.table.get_strategy(key)
        self.table.accumulate_strategy(key, strategy)

        # ── Available actions ─────────────────────────────────
        available    = ['fold', 'call']
        if state.can_raise():
            available.append('raise')

        # Mask unavailable actions
        action_mask  = np.array([
            1.0 if a in available else 0.0
            for a in ACTIONS
        ])
        masked_strat = strategy * action_mask
        if masked_strat.sum() > 0:
            masked_strat /= masked_strat.sum()
        else:
            masked_strat = action_mask / action_mask.sum()

        # ── Compute counterfactual value of each action ───────
        # This is the KEY step that distinguishes CFR from EV lookup:
        # We actually recurse into the game tree for EACH action
        # and observe what would have happened
        action_values = np.zeros(3)

        for a_idx, action in enumerate(ACTIONS):
            if action_mask[a_idx] == 0:
                continue

            # Build next state for this action
            next_state = self._apply_action(state, action)

            # Recurse — swap reach probabilities
            if player == 0:
                action_values[a_idx] = self.cfr(
                    next_state,
                    p0_reach * masked_strat[a_idx],
                    p1_reach
                )
            else:
                action_values[a_idx] = -self.cfr(
                    next_state,
                    p0_reach,
                    p1_reach * masked_strat[a_idx]
                )

        # ── Node value: weighted sum over actions ─────────────
        node_value = float(np.dot(masked_strat, action_values))

        # ── Regret update ─────────────────────────────────────
        # counterfactual regret: how much better would each
        # action have been compared to the mixed strategy value?
        # Weighted by OPPONENT's reach probability (counterfactual)
        opp_reach = p1_reach if player == 0 else p0_reach
        for a_idx in range(3):
            if action_mask[a_idx] == 0:
                continue
            regret = (action_values[a_idx] - node_value) * opp_reach
            
            if key not in self.table.regret_sum:
                self.table.regret_sum[key] = np.zeros(3)

            self.table.regret_sum[key][a_idx] += regret

        return node_value if player == 0 else -node_value

    def _apply_action(self, state, action):
        """
        Transition to next game state after an action.
        Enforces project betting rules:
          - Raise = $10 above opponent's current bet
          - Call  = match opponent's bet exactly
          - Fold  = forfeit
        """
        p0_bet  = state.p0_bet
        p1_bet  = state.p1_bet
        pot     = state.pot
        raises  = state.raises_this_street
        player  = state.acting_player

        call_amt = state.call_amount()

        if action == 'fold':
            return GameState(
                state.p0_hole, state.p1_hole,
                state.community, state.street_idx,
                pot, p0_bet, p1_bet, raises,
                acting_player = 1 - player,
                p0_folded = (player == 0),
                p1_folded = (player == 1)
            )

        elif action == 'call':
            if player == 0:
                p0_bet += call_amt
            else:
                p1_bet += call_amt
            pot += call_amt

            # After a call both bets are equal → street may end
            # Signal street end by setting raises > 0 and bets equal
            # The next cfr() call detects this and advances street
            return GameState(
                state.p0_hole, state.p1_hole,
                state.community, state.street_idx,
                pot, p0_bet, p1_bet,
                raises_this_street = max(raises, 1),  # mark street as active
                acting_player      = 1 - player
            )

        else:  # raise
            raise_total = call_amt + RAISE_SIZE
            if player == 0:
                p0_bet += raise_total
            else:
                p1_bet += raise_total
            pot += raise_total

            return GameState(
                state.p0_hole, state.p1_hole,
                state.community, state.street_idx,
                pot, p0_bet, p1_bet,
                raises_this_street = raises + 1,
                acting_player      = 1 - player
            )

    def train(self, num_iterations=NUM_ITERATIONS):
        """
        Stratified self-play training loop.
        
        Combines two sampling strategies:
        - 50% standard random deals (preserves realism)
        - 50% targeted deals aimed at undervisited buckets
        
        The CFR tree traversal and regret updates are identical —
        only how cards are dealt changes.
        """
        deck      = Deck()
        all_cards = deck.deck[:]

        # Track visit counts per bucket for adaptive sampling
        visit_counts  = {}
        total_iters   = num_iterations
        iteration     = 0

        while iteration < num_iterations:
            self._ehs_cache = {}

            # ── Decide sampling strategy this iteration ───────────
            use_targeted = (iteration % 2 == 1)   # alternate 50/50

            if use_targeted:
                p0_hole, p1_hole, community = self._targeted_deal(
                    all_cards, visit_counts)
            else:
                p0_hole, p1_hole, community = self._random_deal(all_cards)

            if p0_hole is None:
                # Targeted deal failed — fall back to random
                p0_hole, p1_hole, community = self._random_deal(all_cards)

            initial_state = GameState(
                p0_hole            = p0_hole,
                p1_hole            = p1_hole,
                community          = community,
                street_idx         = 0,
                pot                = SMALL_BLIND + BIG_BLIND,
                p0_bet             = SMALL_BLIND,
                p1_bet             = BIG_BLIND,
                raises_this_street = 0,
                acting_player      = 0
            )

            self.cfr(initial_state, p0_reach=1.0, p1_reach=1.0)

            # Track which bucket this iteration hit
            ehs_approx = self.get_ehs(p0_hole, [])
            key_approx = make_info_set('preflop', ehs_approx, 0.0, 0.5)
            visit_counts[key_approx] = visit_counts.get(key_approx, 0) + 1

            iteration += 1
            if iteration % 1000 == 0:
                coverage = len(self.table.strategy_sum)
                print(f"Iter {iteration:>6}/{total_iters} | "
                    f"Info sets visited: {coverage}/180")

        self.table.save('cfr_strategy_stratified.pkl')
        print("Self-play training complete.")


    def _random_deal(self, all_cards):
        """Standard random deal — preserves natural card distribution."""
        cards   = all_cards[:]
        random.shuffle(cards)
        p0_hole   = cards[0:2]
        p0_strs   = set(str(c) for c in p0_hole)
        remaining = [c for c in cards if str(c) not in p0_strs]
        random.shuffle(remaining)
        p1_hole   = remaining[0:2]
        community = remaining[2:7]
        return p0_hole, p1_hole, community


    def _targeted_deal(self, all_cards, visit_counts):
        """
        Deal cards targeting undervisited EHS buckets.
        
        Strategy:
        1. Find which EHS bucket has fewest visits
        2. Sample hole cards until we get a hand in that bucket
        3. Deal p1 and community normally
        
        This ensures all EHS buckets get roughly equal training.
        """
        from cfr_table import (EHS_THRESHOLDS, POT_ODDS_THRESHOLDS,
                                RANGE_THRESHOLDS)

        # ── Find least visited EHS bucket ────────────────────────
        ehs_bucket_visits = [0] * 5
        for (s, e, p, r), count in visit_counts.items():
            ehs_bucket_visits[e] += count

        # Target the bucket with fewest visits
        target_bucket = int(np.argmin(ehs_bucket_visits))

        # EHS range for target bucket
        lo = [0.0] + EHS_THRESHOLDS
        hi = EHS_THRESHOLDS + [1.0]
        target_lo = lo[target_bucket]
        target_hi = hi[target_bucket]

        # ── Sample hole cards until EHS falls in target bucket ───
        cards = all_cards[:]
        max_attempts = 30

        for _ in range(max_attempts):
            random.shuffle(cards)
            p0_hole = cards[0:2]

            # Quick preflop EHS estimate (no community cards)
            ehs = self.get_ehs(p0_hole, [])

            if target_lo <= ehs < target_hi:
                # Found a hand in the target bucket
                p0_strs   = set(str(c) for c in p0_hole)
                remaining = [c for c in cards if str(c) not in p0_strs]
                random.shuffle(remaining)
                p1_hole   = remaining[0:2]
                community = remaining[2:7]
                return p0_hole, p1_hole, community

        # Could not find a hand in target bucket within max_attempts
        return None, None, None


if __name__ == '__main__':
    trainer = SelfPlayCFR()
    trainer.train(num_iterations=NUM_ITERATIONS)