# CFR Poker — Heads-Up Limit Hold'em AI Agent

An AI poker agent for two-player Limit Texas Hold'em, built around a lightweight Counterfactual Regret Minimization (CFR) strategy with Monte Carlo hand strength estimation and potential-aware opponent modelling. Includes a full-stack implementation so you can play against the trained bot in real time.

Game link: https://poker-agent-sage.vercel.app/


## Overview

The agent integrates three components into a single decision framework:

1. **Real-time Effective Hand Strength (EHS)** — Monte Carlo simulation estimating win probability against the distribution of possible opponent hands at the current street.
2. **CFR Strategy Table** — a 180-bucket abstraction over `(street, EHS bucket, pot-odds bucket, opponent range bucket)`, trained offline via self-play game tree traversal with regret matching, converging toward a Nash equilibrium strategy.
3. **EHS² Opponent Range Model** — potential-aware hand strength precomputed offline across all 1,326 hole card combinations, used to enrich the opponent range bucket at deployment with negligible runtime cost.


## Setup

### Backend

```bash
cd backend
pip install fastapi uvicorn pypokerengine numpy

# Start the API server
uvicorn app:app --reload --port 5000
```

The server exposes:

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness check |
| `/bot_action` | POST | Returns the bot's chosen action given the current game state |
| `/reset` | POST | Resets bot state between games |

### Frontend

```bash
cd frontend
npm install
echo "REACT_APP_API_URL=http://localhost:5000" > .env
npm start
```

Open `http://localhost:3000` to play against the bot.

## How the Bot Decides

```
declare_action()
   │
   ├─ Monte Carlo EHS for current hole + visible community cards
   ├─ Pot odds = call_amount / (pot + call_amount)
   ├─ Opponent range bucket via EHS² lookup
   │
   ├─ Information set I = (street, EHS_bucket, pot_odds_bucket, range_bucket)
   ├─ CFR table lookup → strategy σ(I, ·) over {fold, call, raise}   
   └─ 
```

## Training

The CFR table is trained offline via self-play: both players traverse the game tree from a freshly dealt hand, with regret updated at each information set using:

```
σ(I, a) = max(regret(I, a), 0) / Σ max(regret(I, a'), 0)
```

Training does **not** run live — the agent loads a static, pre-trained table at startup, keeping per-action latency low enough for real-time play.

```bash
python backend/strategy_module/cfr_train.py
```

## Evaluation

| Agent | Win Rate | Avg Profit/Game |
|---|---|---|
| Random | 17.0% | −$330.2 |
| Always-Raise | 52.0% | +$48.1 |
| Always-Call | 51.6% | −$10.1 |
| CFR (no EHS²) | 59.5% | +$115.4 |
| **CFR (+EHS²)** | **61.5%** | **+$120.8** |


## Game Rules

Two-player Limit Hold'em in this project: $1,000 starting stack, $10/$20 blinds, fixed $10 raise increments, maximum 4 raises per betting round, standard 4-street structure (preflop/flop/turn/river).