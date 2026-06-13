import { useState, useEffect, useCallback, useRef } from "react";

import {
    SMALL_BLIND,
    BIG_BLIND,
    RAISE_SIZE,
    MAX_RAISES,
    INITIAL_STACK,
    HAND_NAMES
} from "./poker/constants";

import {
    buildDeck,
    shuffle
} from "./poker/cards";

import {
    bestFive,
    compareScore
} from "./poker/handEvaluator";

import {
    getCallAmount,
    isBettingRoundComplete
} from "./poker/gameUtils";

import Card from "./components/Card";
import LogEntry from "./components/LogEntry"


// ── Main Game ─────────────────────────────────────────────────
export default function PokerGame() {

    // Stacks
    const [userStack, setUserStack] = useState(INITIAL_STACK);
    const [botStack, setBotStack] = useState(INITIAL_STACK);

    // Cards
    const [userHole, setUserHole] = useState([]);
    const [botHole, setBotHole] = useState([]);
    const [community, setCommunity] = useState([]);

    // Betting
    const [pot, setPot] = useState(0);
    const [userBet, setUserBet] = useState(0);
    const [botBet, setBotBet] = useState(0);
    const [raisesThisStreet, setRaisesThisStreet] = useState(0);
    const [userActedThisStreet, setUserActedThisStreet] = useState(false);
    const [botActedThisStreet, setbotActedThisStreet] = useState(false);

    // Game flow
    const [street, setStreet] = useState("preflop");
    const [phase, setPhase] = useState("idle");
    // phase: idle | userTurn | botTurn | showdown | gameOver
    const [isUserSB, setIsUserSB] = useState(true);
    const [handNum, setHandNum] = useState(0);
    const [showBotCards, setShowBotCards] = useState(false);
    const [winner, setWinner] = useState(null);
    const [log, setLog] = useState([]);
    const [botThinking, setBotThinking] = useState(false);
    const [lastBotInfo, setLastBotInfo] = useState(null);

    const logRef = useRef(null);

    function addLog(text, type = "action") {
        setLog(prev => [...prev.slice(-60), { text, type }]);
    }

    useEffect(() => {
        if (logRef.current)
            logRef.current.scrollTop = logRef.current.scrollHeight;
    }, [log]);

    // ── Deal new hand ─────────────────────────────────────────
    const dealHand = useCallback((userSB, uStack, bStack) => {
        if (uStack <= 0 || bStack <= 0) {
            setPhase("gameOver");
            return;
        }
        const d = shuffle(buildDeck());
        const uHole = [d[0], d[1]];
        const bHole = [d[2], d[3]];
        const comm = d.slice(4, 9); // deal all 5 upfront

        const sbAmt = Math.min(SMALL_BLIND, userSB ? uStack : bStack);
        const bbAmt = Math.min(BIG_BLIND, userSB ? bStack : uStack);

        let uBet = userSB ? sbAmt : bbAmt;
        let bBet = userSB ? bbAmt : sbAmt;
        const newPot = uBet + bBet;

        // setDeck(d);
        setUserHole(uHole);
        setBotHole(bHole);
        setCommunity(comm);
        setPot(newPot);
        setUserBet(uBet);
        setBotBet(bBet);
        setStreet("preflop");
        setRaisesThisStreet(0);
        setShowBotCards(false);
        setWinner(null);
        setLastBotInfo(null);
        setHandNum(n => n + 1);

        // Deduct blinds from stacks
        setUserStack(uStack - uBet);
        setBotStack(bStack - bBet);

        addLog(`── Hand ${handNum + 1} ──`, "system");
        addLog(`Blinds: You ${userSB ? "SB" : "BB"} $${uBet} · Bot ${userSB ? "BB" : "SB"} $${bBet}`, "system");

        // SB acts first preflop
        if (userSB) {
            setPhase("userTurn");
            addLog("Your turn (preflop)", "system");
        } else {
            setPhase("botTurn");
        }
    }, [handNum]);

    // ── Start game ────────────────────────────────────────────
    function startGame() {
        setUserStack(INITIAL_STACK);
        setBotStack(INITIAL_STACK);
        setLog([]);
        setHandNum(0);
        dealHand(true, INITIAL_STACK, INITIAL_STACK);
    }

    // Reset game
    async function resetGame() {
        try {
            const baseUrl = process.env.REACT_APP_API_URL;
            await fetch(`${baseUrl}/reset`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            });
        } catch (err) {
            console.error("Failed to reset bot:", err);
        }

        // Stacks
        setUserStack(INITIAL_STACK);
        setBotStack(INITIAL_STACK);

        // Cards
        setUserHole([]);
        setBotHole([]);
        setCommunity([]);

        // Betting
        setPot(0);
        setUserBet(0);
        setBotBet(0);
        setRaisesThisStreet(0);
        setUserActedThisStreet(false);
        setbotActedThisStreet(false);

        // Game Flow
        setStreet("preflop");
        setPhase("idle");
        setIsUserSB(true);
        setHandNum(0);
        setShowBotCards(false);
        setWinner(null);
        setBotThinking(false);
        setLastBotInfo(null);

        // Logs
        setLog([]);

        addLog("Game reset", "system");
    }



    // ── Advance street ────────────────────────────────────────
    function advanceStreet(currentStreet, currentPot,
        uStack, bStack, uBet, bBet) {

        setPhase("");
        const streets = ["preflop", "flop", "turn", "river"];
        const idx = streets.indexOf(currentStreet);
        if (idx >= streets.length - 1) {
            // Showdown
            doShowdown(currentPot, uStack, bStack);
            return;
        }
        const next = streets[idx + 1];
        setStreet(next);
        setUserBet(0);
        setBotBet(0);
        setRaisesThisStreet(0);
        setUserActedThisStreet(false);
        setbotActedThisStreet(false);
        addLog(`── ${next.toUpperCase()} ──`, "system");

        if (isUserSB) {
            setPhase("userTurn");
            addLog("Your turn", "system");
        } else {
            setPhase("botTurn");
        }

    }

    // ── Showdown ──────────────────────────────────────────────
    function doShowdown(currentPot, uStack, bStack) {
        setShowBotCards(true);
        const uScore = bestFive(userHole, community.slice(0, 5));
        const bScore = bestFive(botHole, community.slice(0, 5));
        const cmp = compareScore(uScore, bScore);
        const uHand = HAND_NAMES[uScore[0]];
        const bHand = HAND_NAMES[bScore[0]];

        addLog(`Showdown: You ${uHand} · Bot ${bHand}`, "result");

        let newUS = uStack, newBS = bStack;
        let w;
        if (cmp > 0) {
            newUS += currentPot;
            w = "user";
            addLog(`You win $${currentPot} 🏆`, "result");
        } else if (cmp < 0) {
            newBS += currentPot;
            w = "bot";
            addLog(`Bot wins $${currentPot}`, "warning");
        } else {
            const half = Math.floor(currentPot / 2);
            newUS += half; newBS += currentPot - half;
            w = "tie";
            addLog(`Split pot ($${half} each)`, "result");
        }
        setUserStack(newUS);
        setBotStack(newBS);
        setWinner(w);
        setPhase("showdown");
    }

    // ── User fold ─────────────────────────────────────────────
    function userFold() {
        addLog("You fold", "action");
        setBotStack(bs => bs + pot);
        setWinner("bot");
        setPhase("showdown");
        setShowBotCards(true);
        addLog(`Bot wins $${pot}`, "warning");
    }

    // ── User call ─────────────────────────────────────────────
    function userCall() {
        setUserActedThisStreet(true);
        const callAmt = getCallAmount(userBet, botBet, true);
        const actual = Math.min(callAmt, userStack);
        const newPot = pot + actual;
        const newUS = userStack - actual;
        const newUBet = userBet + actual;

        setUserStack(newUS);
        setPot(newPot);
        setUserBet(newUBet);
        addLog(`You call $${actual} (pot $${newPot})`, "action");

        // Check if bets are equal → advance street
        if (isBettingRoundComplete(true, botActedThisStreet, newUBet, botBet)) {
            advanceStreet(street, newPot, newUS, botStack,
                newUBet, botBet);
        } else {
            setPhase("botTurn");
        }
    }

    // ── User raise ────────────────────────────────────────────
    function userRaise() {
        setUserActedThisStreet(true)
        if (raisesThisStreet >= MAX_RAISES) {
            addLog("Raise cap reached", "warning");
            return;
        }
        const callAmt = getCallAmount(userBet, botBet, true);
        const total = callAmt + RAISE_SIZE;
        const actual = Math.min(total, userStack);
        const newPot = pot + actual;
        const newUS = userStack - actual;
        const newUBet = userBet + actual;

        setUserStack(newUS);
        setPot(newPot);
        setUserBet(newUBet);
        setRaisesThisStreet(r => r + 1);
        addLog(`You raise to $${newUBet} (pot $${newPot})`, "action");
        setPhase("botTurn");
    }

    // ── Bot turn ──────────────────────────────────────────────
    useEffect(() => {

        if (phase !== "botTurn") return;
        setBotThinking(true);
        setbotActedThisStreet(true)
        const timer = setTimeout(() => {
            const callAmt = getCallAmount(userBet, botBet, false);
            const visComm = {
                preflop: [], flop: community.slice(0, 3),
                turn: community.slice(0, 4), river: community.slice(0, 5)
            }[street] || [];

            async function bot_action(validActions) {

                const baseUrl = process.env.REACT_APP_API_URL;
                const res = await fetch(`${baseUrl}/bot_action`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        valid_actions: validActions,
                        hole_card: botHole,
                        round_state: { community_card: visComm, street, pot: { main: { amount: pot } } }
                    })
                });
                const data = await res.json();
                return data.action;
            }

            const validActions = [
                { action: "fold" },
                { action: "call", amount: callAmt },
            ];
            if (callAmt < pot) validActions.push({ action: "raise" });

            bot_action(validActions).then((action) => {

                setBotThinking(false);

                // console.log(action)
                if (action === "fold") {
                    addLog(`Bot folds `, "action");
                    setUserStack(us => us + pot);
                    setWinner("user");
                    setPhase("showdown");
                    setShowBotCards(true);
                    addLog(`You win $${pot} 🏆`, "result");

                } else if (action === "call") {
                    const actual = Math.min(callAmt, botStack);
                    const newPot = pot + actual;
                    const newBS = botStack - actual;
                    const newBBet = botBet + actual;

                    setBotStack(newBS);
                    setPot(newPot);
                    setBotBet(newBBet);
                    addLog(`Bot calls $${actual} (pot $${newPot})`, "action");

                    // console.log(userActedThisStreet, newBBet, userBet)

                    if (isBettingRoundComplete(userActedThisStreet, true, userBet, newBBet)) {
                        advanceStreet(street, newPot, userStack, newBS,
                            userBet, newBBet);
                    } else {
                        setPhase("userTurn");
                        addLog("Your turn", "system");
                    }

                } else { // raise
                    if (raisesThisStreet >= MAX_RAISES) {
                        // Can't raise — call instead
                        const actual = Math.min(callAmt, botStack);
                        const newPot = pot + actual;
                        const newBS = botStack - actual;
                        const newBBet = botBet + actual;
                        setBotStack(newBS); setPot(newPot); setBotBet(newBBet);
                        addLog(`Bot calls $${actual} (raise cap, pot $${newPot})`, "action");
                        if (newBBet === userBet || actual === 0) {
                            advanceStreet(street, newPot, userStack, newBS,
                                userBet, newBBet);
                        } else {
                            setPhase("userTurn");
                        }
                    } else {
                        const total = callAmt + RAISE_SIZE;
                        const actual = Math.min(total, botStack);
                        const newPot = pot + actual;
                        const newBS = botStack - actual;
                        const newBBet = botBet + actual;

                        setBotStack(newBS);
                        setPot(newPot);
                        setBotBet(newBBet);
                        setRaisesThisStreet(r => r + 1);
                        addLog(`Bot raises to $${newBBet}  pot $${newPot})`, "action");
                        setPhase("userTurn");
                        addLog("Your turn", "system");
                    }
                }
            });
        }, 800 + Math.random() * 600);

        return () => clearTimeout(timer);
    }, [phase]); // eslint-disable-line

    // ── Next hand ─────────────────────────────────────────────
    function nextHand() {
        const newSB = !isUserSB;
        setIsUserSB(newSB);
        dealHand(newSB, userStack, botStack);
    }

    // ── Visible community cards ───────────────────────────────
    const visibleComm = {
        preflop: 0, flop: 3, turn: 4, river: 5
    }[street] ?? 0;

    const canRaise = raisesThisStreet < MAX_RAISES && userStack > 0;
    const callAmt = getCallAmount(userBet, botBet, true);

    // ── Hand name display ─────────────────────────────────────
    function myHandName() {
        if (userHole.length < 2 || community.length < 5) return "";
        const score = bestFive(userHole, community.slice(0, 5));
        return HAND_NAMES[score[0]];
    }

    // ── Styles ────────────────────────────────────────────────
    const felt = {
        background: "radial-gradient(ellipse at center, #1a5c30 0%, #0d3a1c 60%, #081f0f 100%)"
    };

    const btn = (color) => ({
        padding: "10px 22px",
        borderRadius: "8px",
        fontWeight: "700",
        fontSize: "0.9rem",
        border: "none",
        cursor: "pointer",
        letterSpacing: "0.04em",
        transition: "opacity 0.15s, transform 0.1s",
        background: color,
        color: "#fff",
        boxShadow: "0 3px 8px rgba(0,0,0,0.4)",
    });

    return (
        <div style={{
            minHeight: "100vh", fontFamily: "'Georgia', serif",
            background: "#050e07", display: "flex",
            flexDirection: "column", alignItems: "center",
            padding: "16px", boxSizing: "border-box"
        }}>

            {/* Header */}
            <div style={{ textAlign: "center", marginBottom: "12px" }}>
                <h1 style={{
                    color: "#c8a84a", fontSize: "1.6rem",
                    fontWeight: "bold", letterSpacing: "0.12em",
                    textShadow: "0 2px 8px rgba(200,168,74,0.4)",
                    margin: 0
                }}>
                    ♠ CFR POKER ♠
                </h1>
                <div style={{
                    color: "#5a8a6a", fontSize: "0.72rem",
                    letterSpacing: "0.2em", marginTop: "2px"
                }}>
                    HEADS-UP LIMIT HOLD'EM
                </div>
            </div>

            {/* Main table */}
            <div style={{
                width: "100%", maxWidth: "720px",
                borderRadius: "24px", padding: "20px",
                boxShadow: "0 0 60px rgba(0,0,0,0.8), inset 0 0 40px rgba(0,0,0,0.3)",
                border: "6px solid #3a2a10", ...felt
            }}>

                {/* Bot area */}
                <div style={{
                    display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginBottom: "16px"
                }}>
                    <div>
                        <div style={{
                            color: "#7ec8a0", fontSize: "0.8rem",
                            letterSpacing: "0.1em"
                        }}>CFR BOT</div>
                        <div style={{
                            color: "#c8a84a", fontSize: "1.3rem",
                            fontWeight: "bold"
                        }}>${botStack}</div>
                        {lastBotInfo && (
                            <div style={{
                                color: "#5a7a6a", fontSize: "0.65rem",
                                marginTop: "2px"
                            }}>
                                EHS: {lastBotInfo.ehs} ·
                                F:{(lastBotInfo.probs[0] * 100).toFixed(0)}%
                                C:{(lastBotInfo.probs[1] * 100).toFixed(0)}%
                                R:{(lastBotInfo.probs[2] * 100).toFixed(0)}%
                            </div>
                        )}
                    </div>
                    <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                        {botBet > 0 && (
                            <div style={{
                                color: "#c8a84a", fontSize: "0.75rem",
                                background: "rgba(0,0,0,0.4)",
                                padding: "2px 8px", borderRadius: "4px"
                            }}>
                                Bet: ${botBet}
                            </div>
                        )}
                        {botHole.map((c, i) => (
                            <Card key={i} card={c}
                                hidden={!showBotCards && phase !== "showdown"} />
                        ))}
                    </div>
                </div>

                {/* Community cards + pot */}
                <div style={{
                    display: "flex", flexDirection: "column",
                    alignItems: "center", margin: "16px 0",
                    gap: "10px"
                }}>
                    <div style={{
                        display: "flex", gap: "8px", flexWrap: "wrap",
                        justifyContent: "center"
                    }}>
                        {[0, 1, 2, 3, 4].map(i => (
                            <Card key={i}
                                card={i < visibleComm ? community[i] : null} />
                        ))}
                    </div>

                    <div style={{
                        display: "flex", alignItems: "center",
                        gap: "16px"
                    }}>
                        <div style={{
                            background: "rgba(0,0,0,0.4)",
                            borderRadius: "20px",
                            padding: "6px 20px",
                            border: "1px solid #3a5a3a"
                        }}>
                            <span style={{
                                color: "#7ec8a0", fontSize: "0.75rem",
                                letterSpacing: "0.1em"
                            }}>POT </span>
                            <span style={{
                                color: "#c8a84a", fontSize: "1.1rem",
                                fontWeight: "bold"
                            }}>${pot}</span>
                        </div>
                        <div style={{
                            background: "rgba(0,0,0,0.3)",
                            borderRadius: "12px", padding: "4px 14px",
                            border: "1px solid #2a4a2a"
                        }}>
                            <span style={{
                                color: "#5a8a6a", fontSize: "0.72rem",
                                letterSpacing: "0.12em",
                                textTransform: "uppercase"
                            }}>
                                {street}
                            </span>
                        </div>
                    </div>
                </div>

                {/* User area */}
                <div style={{
                    display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginTop: "16px"
                }}>
                    <div>
                        <div style={{
                            color: "#7ec8a0", fontSize: "0.8rem",
                            letterSpacing: "0.1em"
                        }}>YOU</div>
                        <div style={{
                            color: "#c8a84a", fontSize: "1.3rem",
                            fontWeight: "bold"
                        }}>${userStack}</div>
                        {phase !== "idle" && userHole.length === 2 &&
                            community.length >= 3 && (
                                <div style={{
                                    color: "#7a9a7a", fontSize: "0.7rem",
                                    marginTop: "2px"
                                }}>
                                    {myHandName()}
                                </div>
                            )}
                    </div>
                    <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                        {userBet > 0 && (
                            <div style={{
                                color: "#c8a84a", fontSize: "0.75rem",
                                background: "rgba(0,0,0,0.4)",
                                padding: "2px 8px", borderRadius: "4px"
                            }}>
                                Bet: ${userBet}
                            </div>
                        )}
                        {userHole.map((c, i) => (
                            <Card key={i} card={c} />
                        ))}
                    </div>
                </div>
            </div>

            {/* Action buttons */}
            <div style={{
                marginTop: "16px", display: "flex",
                gap: "10px", flexWrap: "wrap",
                justifyContent: "center"
            }}>

                {phase === "idle" && (
                    <button style={btn("linear-gradient(135deg,#2d7a4a,#1a5c30)")}
                        onClick={startGame}>
                        Deal Cards
                    </button>
                )}

                {phase === "userTurn" && (
                    <>
                        <button style={btn("linear-gradient(135deg,#8a3030,#5c1a1a)")}
                            onClick={userFold}>
                            Fold
                        </button>
                        <button style={btn("linear-gradient(135deg,#3a6a9a,#1a3a6a)")}
                            onClick={userCall}>
                            {callAmt > 0 ? `Call $${callAmt}` : "Check"}
                        </button>
                        {canRaise && (
                            <button style={btn("linear-gradient(135deg,#8a6a20,#5c4a10)")}
                                onClick={userRaise}>
                                Raise +${RAISE_SIZE}
                            </button>
                        )}
                    </>
                )}

                {phase === "botTurn" && (
                    <div style={{
                        color: "#7ec8a0", fontSize: "0.9rem",
                        padding: "10px 24px",
                        background: "rgba(0,0,0,0.4)",
                        borderRadius: "8px",
                        border: "1px solid #2d5a3a",
                        animation: botThinking
                            ? "pulse 1s infinite" : "none"
                    }}>
                        {botThinking ? "Bot thinking…" : "Bot acting…"}
                    </div>
                )}

                {phase === "showdown" && (
                    <>
                        <div style={{
                            color: winner === "user" ? "#7ec8a0"
                                : winner === "bot" ? "#c07070"
                                    : "#c8a84a",
                            fontSize: "1.1rem", fontWeight: "bold",
                            padding: "8px 20px",
                            background: "rgba(0,0,0,0.4)",
                            borderRadius: "8px"
                        }}>
                            {winner === "user" ? "🏆 You win!"
                                : winner === "bot" ? "Bot wins"
                                    : "Split pot"}
                        </div>
                        {userStack > 0 && botStack > 0 ? (
                            <button style={btn("linear-gradient(135deg,#2d7a4a,#1a5c30)")}
                                onClick={nextHand}>
                                Next Hand →
                            </button>
                        ) : (
                            <button style={btn("linear-gradient(135deg,#2d7a4a,#1a5c30)")}
                                onClick={startGame}>
                                New Game
                            </button>
                        )}
                    </>
                )}

                {phase === "gameOver" && (
                    <>
                        <div style={{
                            color: "#c8a84a", fontSize: "1rem",
                            padding: "8px 20px"
                        }}>
                            {userStack <= 0 ? "You're out of chips!"
                                : "Bot is out of chips!"}
                        </div>
                        <button style={btn("linear-gradient(135deg,#2d7a4a,#1a5c30)")}
                            onClick={startGame}>
                            New Game
                        </button>
                    </>
                )}

                {phase !== "idle" && (
                    <button
                        style={btn("linear-gradient(135deg,#555,#333)")}
                        onClick={resetGame}
                    >
                        Reset Game
                    </button>
                )}
            </div>

            {/* Stats row */}
            {phase !== "idle" && (
                <div style={{
                    display: "flex", gap: "20px",
                    marginTop: "12px", flexWrap: "wrap",
                    justifyContent: "center"
                }}>
                    {[
                        { label: "Hand", value: handNum },
                        { label: "Street", value: street },
                        { label: "Raises", value: `${raisesThisStreet}/${MAX_RAISES}` },
                        { label: isUserSB ? "You: SB" : "You: BB", value: "" },
                    ].map(({ label, value }) => (
                        <div key={label} style={{ textAlign: "center" }}>
                            <div style={{
                                color: "#3a6a4a", fontSize: "0.65rem",
                                letterSpacing: "0.12em",
                                textTransform: "uppercase"
                            }}>
                                {label}
                            </div>
                            <div style={{
                                color: "#7ec8a0", fontSize: "0.85rem",
                                fontWeight: "bold"
                            }}>
                                {value}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Action log */}
            <div ref={logRef}
                style={{
                    width: "100%", maxWidth: "720px",
                    height: "120px", overflowY: "auto",
                    background: "#050e07",
                    border: "1px solid #1a3a2a",
                    borderRadius: "8px", padding: "8px 12px",
                    marginTop: "12px", boxSizing: "border-box"
                }}>
                {log.length === 0
                    ? <div style={{ color: "#2a4a3a", fontSize: "0.75rem" }}>
                        Press Deal Cards to begin…
                    </div>
                    : log.map((e, i) => <LogEntry key={i} entry={e} />)
                }
            </div>

            {/* Footer */}
            <div style={{
                color: "#1a4a2a", fontSize: "0.65rem",
                marginTop: "10px", letterSpacing: "0.15em",
                textAlign: "center"
            }}>
                CFR strategy · Monte Carlo EHS · EHS² opponent model
            </div>

            <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.5; }
        }
        button:hover { opacity: 0.88; transform: translateY(-1px); }
        button:active { transform: translateY(0); }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #050e07; }
        ::-webkit-scrollbar-thumb { background: #1a4a2a; border-radius: 2px; }
      `}</style>
        </div>
    );
}