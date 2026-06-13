# player.py
# 100 mcts 40k iter ehs2
from pypokerengine.players import BasePokerPlayer
from strategy_module.strategy import StrategyModule
from pypokerengine.engine.card import Card
from opponent_module.ehs2_lookup import EHS2Lookup 


class CFRPlayer_1(BasePokerPlayer):

    def __init__(self):
        super().__init__()
        # Load pre-trained CFR table at startup
        self.strategy = StrategyModule(
            cfr_path='cfr_strategy_stratified_10k_75.pkl',
            alpha_max=0.4
        )
        self.ehs2 = EHS2Lookup()
        self._opponent_actions = []

    def declare_action(self, valid_actions, hole_card, round_state):
        """
        Called every time the agent must act.
        Opponent range and exploit action come from black-box modules.
        """


        community_cards = round_state.get('community_card', [])
        # print("p1", hole_card, community_cards)

        hole_card = [Card.from_str(s) for s in hole_card]
        community_cards = [Card.from_str(s) for s in community_cards]

        # ── Black Box 1: Opponent Model ───────────────────────
        # Returns float in [0,1]: loose=high, tight=low
        # Replace with actual call to your opponent model
        opponent_range  = self._get_opponent_range(hole_card, round_state)

        # ── Black Box 2: Exploit Module ───────────────────────
        # Returns dict: {'action': 'raise', 'confidence': 0.7}
        # or None if no signal
        # Replace with actual call to your exploit module
        # exploit_action  = self._get_exploit_action(round_state)

        # ── Strategy Module Decision ──────────────────────────
        action = self.strategy.decide(
            valid_actions   = valid_actions,
            hole_cards      = hole_card,
            community_cards = community_cards,
            round_state     = round_state,
            opponent_range  = opponent_range,
            # exploit_action  = exploit_action
        )

        # Map action string to valid_actions format
        return self._format_action(action, valid_actions)

    def receive_game_start_message(self, game_info):
        pass

    def receive_round_start_message(self, round_count, hole_card, seats):
        self._opponent_actions = []

    def receive_street_start_message(self, street, round_state):
        pass

    def receive_game_update_message(self, action, round_state):
        self._opponent_actions.append(action)

    def receive_round_result_message(self, winners, hand_info, round_state):
        # Update hands seen counter for α scaling
        self.strategy.update_hands_seen()

    # ── Black Box Stubs (replace with real modules) ───────────

    def _get_opponent_range(self, hole_cards, round_state):
        """
        STUB — replace with opponent model module call.
        Returns float in [0, 1].
        """
        # Base range score from EHS² lookup
        base_score = self.ehs2.get_range_score(hole_cards)

        n_raises = sum(
            1 for a in self._opponent_actions
            if isinstance(a, dict) and a.get('action') == 'raise'
        )
        # # Each observed raise shifts estimate toward tight (strong)
        aggression_adjustment = min(n_raises * 0.05, 0.2)
        refined_score = max(0.0, base_score - aggression_adjustment)

        return float(refined_score)
        # return 0.5

    def _get_exploit_action(self, round_state):
        """
        STUB — replace with exploit module call.
        Returns dict or None.
        """
        return None

    def _format_action(self, action_str, valid_actions):
        """
        Convert 'fold'/'call'/'raise' string to the format
        expected by the game engine.
        """
        for a in valid_actions:
            if a['action'] == action_str:
                if action_str == 'raise':
                    # Fixed $10 raise as per project spec
                    # amount = a['amount']['min']
                    return action_str
                elif action_str == 'call':
                    return action_str
                else:  # fold
                    return action_str
        # Fallback to call if chosen action not available
        for a in valid_actions:
            if a['action'] == 'call':
                return 'call'
        return 'fold'