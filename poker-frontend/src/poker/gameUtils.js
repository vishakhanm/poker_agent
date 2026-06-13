// ── Call amount ───────────────────────────────────────────
export function getCallAmount(userBet,
    botBet,
    forUser) {
    if (forUser) return Math.max(0, botBet - userBet);
    else return Math.max(0, userBet - botBet);
}

export function isBettingRoundComplete(userActedThisStreet,
    botActedThisStreet,
    userBet,
    botBet) {
    return userActedThisStreet && botActedThisStreet &&
        userBet === botBet;
}