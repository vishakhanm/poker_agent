// ── Card utilities ────────────────────────────────────────────
const SUITS = ["♠", "♥", "♦", "♣"];
const SUIT_KEYS = ["S", "H", "D", "C"];
const RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"];
const RANK_VALUES = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14
};

export {
    SUITS,
    SUIT_KEYS,
    RANKS,
    RANK_VALUES
};

export function buildDeck() {
    const deck = [];
    for (const r of RANKS)
        for (const s of SUIT_KEYS)
            deck.push(r + s);
    return deck;
}

export function shuffle(deck) {
    const d = [...deck];
    for (let i = d.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [d[i], d[j]] = [d[j], d[i]];
    }
    return d;
}

export function cardLabel(card) {
    // console.log(card)
    if (!card) return "";
    const rank = card[0];
    const suitKey = card[1];
    const suitIdx = SUIT_KEYS.indexOf(suitKey);
    return (RANK_VALUES[rank] > 10 ? rank : RANK_VALUES[rank]) + SUITS[suitIdx];
}

export function isRed(card) {
    return card && (card[1] === "H" || card[1] === "D");
}

export function getRankVal(card) { return RANK_VALUES[card[0]]; }

export function getSuit(card) { return card[1]; }