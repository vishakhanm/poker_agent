import {
    getRankVal,
    getSuit
} from "./cards";


export function scoreHand(cards) {
    // Returns [category, ...tiebreakers] — higher = better
    const ranks = cards.map(getRankVal).sort((a, b) => b - a);
    const suits = cards.map(getSuit);
    const rankCounts = {};
    for (const r of ranks) rankCounts[r] = (rankCounts[r] || 0) + 1;
    const counts = Object.values(rankCounts).sort((a, b) => b - a);
    const uniqueRanks = [...new Set(ranks)].sort((a, b) => b - a);
    const isFlush = suits.every(s => s === suits[0]);
    const sortedRanks = [...ranks].sort((a, b) => a - b);
    const isStraight = (
        uniqueRanks.length === 5 &&
        sortedRanks[4] - sortedRanks[0] === 4
    ) || (
            // Wheel: A-2-3-4-5
            JSON.stringify(sortedRanks) === JSON.stringify([2, 3, 4, 5, 14])
        );
    const groupedRanks = Object.entries(rankCounts)
        .sort((a, b) => b[1] - a[1] || b[0] - a[0])
        .map(e => parseInt(e[0]));

    if (isFlush && isStraight) return [8, ...ranks];
    if (counts[0] === 4) return [7, ...groupedRanks];
    if (counts[0] === 3 && counts[1] === 2) return [6, ...groupedRanks];
    if (isFlush) return [5, ...ranks];
    if (isStraight) return [4, ...ranks];
    if (counts[0] === 3) return [3, ...groupedRanks];
    if (counts[0] === 2 && counts[1] === 2) return [2, ...groupedRanks];
    if (counts[0] === 2) return [1, ...groupedRanks];
    return [0, ...ranks];
}

export function bestFive(hole, community) {
    const all = [...hole, ...community];
    let best = null;
    for (let i = 0; i < all.length; i++)
        for (let j = i + 1; j < all.length; j++) {
            const five = all.filter((_, k) => k !== i && k !== j);
            const score = scoreHand(five);
            if (!best || compareScore(score, best) > 0) best = score;
        }
    return best;
}

export function compareScore(a, b) {
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
        const diff = (a[i] || 0) - (b[i] || 0);
        if (diff !== 0) return diff;
    }
    return 0;
}
