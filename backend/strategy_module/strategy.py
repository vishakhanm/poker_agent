# strategy/strategy_module.py
# Core decision logic integrating EHS, pot odds, CFR, and exploit signal
# Literature:
#   EV:     Russell & Norvig AIMA Ch.16; Sklansky (1994) Ch.1
#   CFR:    Zinkevich et al. (NIPS 2007)
#   Blend:  Johanson & Bowling (AISTATS 2009);
#           Johanson, Zinkevich & Bowling (NIPS 2007)

import numpy as np
from pypokerengine.utils.card_utils import estimate_hole_card_win_rate
from strategy_module.cfr_table import CFRTable, make_info_set, ACTIONS

class StrategyModule:

    def __init__(self, cfr_path='cfr_strategy.pkl', alpha_max=0.4):
        """
        Args:
            cfr_path:  path to pre-trained CFR table
            alpha_max: maximum weight given to exploit strategy.
                       Scales from 0 → alpha_max as opponent
                       model confidence grows
        """
        self.cfr_table  = CFRTable()
        self.alpha_max  = alpha_max
        self.hands_seen = 0  # tracks opponent model confidence

        try:
            self.cfr_table.load(cfr_path)
        except FileNotFoundError:
            print(f"[Strategy] No CFR table at {cfr_path}."
                  " Using uniform strategy. Run cfr_train.py first.")

    # ── Public API ────────────────────────────────────────────

    def decide(self,
               valid_actions,
               hole_cards,
               community_cards,
               round_state,
               opponent_range,   # BLACK BOX INPUT 1
            #    exploit_action
               ):  # BLACK BOX INPUT 2
        """
        Main decision function called by declare_action().

        Args:
            valid_actions:    list from game engine
                              e.g. [{'action':'fold'},
                                    {'action':'call','amount':20},
                                    {'action':'raise','amount':{'min':30,'max':30}}]
            hole_cards:       list of 2 strings e.g. ['Ah', 'Kd']
            community_cards:  list of 0–5 strings
            round_state:      dict from game engine
            opponent_range:   float in [0,1] from opponent model
                              (0=tight/strong range, 1=loose/weak range)
            exploit_action:   dict from exploit module
                              {'action': 'raise', 'confidence': 0.7}
                              or None if no signal

        Returns:
            str: 'fold', 'call', or 'raise'
        """

        # ── 1. Compute EHS via Monte Carlo ────────────────────
        ehs = estimate_hole_card_win_rate(500, 2, hole_cards, community_cards)
        # print("ehs: ", ehs)

        # ── 2. Compute pot odds ───────────────────────────────
        pot_odds = self._compute_pot_odds(valid_actions, round_state)
        # print("pot_odds: ", pot_odds)

        # ── 3. Compute EV for each action ─────────────────────
        # action_evs = self._compute_evs(ehs, valid_actions, round_state)

        # ── 4. CFR table lookup ───────────────────────────────
        street    = round_state.get('street', 'preflop')
        info_set  = make_info_set(street, ehs, pot_odds, opponent_range)
        cfr_probs = self.cfr_table.get_average_strategy(info_set)

        # ── 5. Blend CFR with exploit signal ──────────────────
        #    π* = (1-α)·π_CFR + α·π_exploit
        # alpha = self._compute_alpha(exploit_action)
        # exploit_probs = self._exploit_to_probs(exploit_action, action_evs)
        # final_probs  = ((1 - alpha) * cfr_probs + alpha * exploit_probs)

        # ── 6. Select action ──────────────────────────────────
        chosen = self._select_action(cfr_probs, valid_actions)
        return chosen

    # ── Private helpers ───────────────────────────────────────

    def _compute_pot_odds(self, valid_actions, round_state):
        """
        pot_odds = call_amount / (pot_size + call_amount)
        Returns 0 if no call action exists (e.g. can check for free).
        """
        pot_size    = round_state.get('pot', {}).get('main', {}).get('amount', 0)
        call_amount = 0
        for a in valid_actions:
            if a['action'] == 'call':
                call_amount = a.get('amount', 0)
                break
        if call_amount == 0:
            return 0.0
        return call_amount / (pot_size + call_amount)

    def _compute_evs(self, ehs, valid_actions, round_state):
        """
        Compute EV for fold, call, raise.

        EV(fold)  = 0
        EV(call)  = EHS × pot_after_call - (1-EHS) × call_amount
        EV(raise) = EHS × pot_after_raise - (1-EHS) × raise_amount
        """
        pot = round_state.get('pot', {}).get('main', {}).get('amount', 0)
        evs = np.zeros(3)  # [fold, call, raise]

        # EV(fold) = 0 always
        evs[0] = 0.0

        for a in valid_actions:
            if a['action'] == 'call':
                c = a.get('amount', 0)
                evs[1] = ehs * (pot + c) - (1 - ehs) * c

            if a['action'] == 'raise':
                amt = a.get('amount', {})
                # use min raise amount (fixed $10 in this game)
                r = amt.get('min', pot + 10) if isinstance(amt, dict) else amt
                evs[2]  = ehs * (pot + r) - (1 - ehs) * r

        return evs

    def _compute_alpha(self, exploit_action):
        """
        α scales with exploit module confidence and hands observed.
        Capped at alpha_max to preserve Nash floor.
        """
        if exploit_action is None:
            return 0.0
        confidence = exploit_action.get('confidence', 0.0)
        # Scale confidence by how many hands we have seen
        # (more data → trust exploit more)
        data_factor  = min(self.hands_seen / 50.0, 1.0)
        return self.alpha_max * confidence * data_factor

    def _exploit_to_probs(self, exploit_action, action_evs):
        """
        Convert exploit module signal to a probability distribution.
        If exploit says 'raise' with high confidence, concentrate
        probability on raise. Falls back to EV-softmax otherwise.
        """
        if exploit_action is None:
            return self._ev_to_probs(action_evs)

        action_str = exploit_action.get('action', None)
        if action_str not in ACTIONS:
            return self._ev_to_probs(action_evs)

        # Concentrate mass on exploit action
        probs = np.zeros(3)
        idx   = ACTIONS.index(action_str)
        probs[idx] = 1.0
        return probs

    def _ev_to_probs(self, action_evs):
        """
        Convert EV array to probability distribution via softmax.
        Used as fallback when no exploit signal is present.
        """
        shifted = action_evs - action_evs.max()
        exp     = np.exp(shifted)
        return exp / exp.sum()

    def _select_action(self, probs, valid_actions):
        """
        Sample from final probability distribution.
        Masks out actions not in valid_actions.
        """
        valid_names = [a['action'] for a in valid_actions]
        mask        = np.array([
            1.0 if name in valid_names else 0.0
            for name in ACTIONS
        ])

        masked = probs * mask
        total  = masked.sum()
        if total == 0:
            # Fallback: call or fold
            return 'call' if 'call' in valid_names else 'fold'

        masked /= total
        chosen_idx = np.random.choice(len(ACTIONS), p=masked)
        return ACTIONS[chosen_idx]

    def update_hands_seen(self):
        """Call once per round from receive_round_result_message."""
        self.hands_seen += 1