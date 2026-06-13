# # backend/app.py
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from CFRPlayer_1 import CFRPlayer_1
# from pypokerengine.engine.card import Card

# app  = Flask(__name__)
# CORS(app)
# bot  = CFRPlayer_1()

# @app.route("/bot_action", methods=["POST"])
# def bot_action():
#     data            = request.json
#     valid_actions   = data["valid_actions"]
#     hole_card       = [Card.from_str(c) for c in data["hole_card"]]
#     round_state     = data["round_state"]
#     action          = bot.declare_action(
#                         valid_actions, hole_card, round_state)
#     return jsonify({ "action": action })

# if __name__ == "__main__":
#     app.run(port=5000)
# backend/app.py
# FastAPI backend exposing the trained CFR poker agent
# Run with: uvicorn app:app --reload --port 5000

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from CFRPlayer_1 import CFRPlayer_1
# from pypokerengine.engine.card import Card


# ── App setup ───────────────────────────────────────────────────

app = FastAPI(title="CFR Poker Bot API")

# Allow the React frontend (e.g. localhost:3000 / 5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single shared bot instance (loads CFR table + EHS² table once at startup)
bot = CFRPlayer_1()


# ── Request / response schemas ───────────────────────────────────

class ValidAction(BaseModel):
    action: str
    amount: Optional[Any] = None


class BotActionRequest(BaseModel):
    valid_actions: List[ValidAction]
    hole_card: List[str]                 # e.g. ["AH", "KD"]
    round_state: Any          # community_card, pot, street, etc.


class BotActionResponse(BaseModel):
    action: str
    # ehs: Optional[float] = None


# ── Routes ────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/health")
def health():
    """Simple liveness check."""
    return {"status": "ok"}


@app.post("/bot_action", response_model=BotActionResponse)
def bot_action(req: BotActionRequest):
    """
    Given the current game state, return the CFR agent's chosen action.

    Expected request body:
    {
        "valid_actions": [
            {"action": "fold"},
            {"action": "call", "amount": 20},
            {"action": "raise", "amount": {"min": 30, "max": 30}}
        ],
        "hole_card": ["AH", "KD"],
        "round_state": {
            "community_card": ["2C", "7D", "9S"],
            "street": "flop",
            "pot": {"main": {"amount": 60}}
        }
    }
    """
    try:
        print(req)
        valid_actions = [va.model_dump() for va in req.valid_actions]
        # print(valid_actions)
        # hole_card     = [Card.from_str(c) for c in req.hole_card]
        # print(hole_card)
        
        action = bot.declare_action(
            valid_actions,
            req.hole_card,
            req.round_state
        )
        print("action called:", action)

        print(BotActionResponse(action=action))

        return BotActionResponse(action=action)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/reset")
def reset_bot():
    """
    Reset the bot's per-match state (hands_seen counter, opponent
    action history). Call this when starting a new game/session.
    """
    global bot
    bot = CFRPlayer_1()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)