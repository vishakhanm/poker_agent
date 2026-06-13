import {
    cardLabel,
    isRed,
} from "../poker/cards";

// ── Card component ────────────────────────────────────────────
export default function Card({ card, hidden = false, small = false }) {
    const size = small
        ? "w-10 h-14 text-sm"
        : "w-16 h-24 text-xl";

    if (hidden) return (
        <div className={`${size} rounded-lg flex items-center justify-center
      shadow-lg border border-green-600`}
            style={{
                background: "linear-gradient(135deg, #1a4a2a 0%, #0d2b1a 100%)",
                borderColor: "#2d7a4a"
            }}>
            <span style={{ fontSize: small ? "1.2rem" : "1.8rem" }}>🂠</span>
        </div>
    );

    if (!card) return (
        <div className={`${size} rounded-lg border-2 border-dashed opacity-30`}
            style={{ borderColor: "#2d7a4a" }} />
    );

    const label = cardLabel(card);
    const red = isRed(card);

    return (
        <div className={`${size} rounded-lg flex flex-col items-center
      justify-center shadow-lg font-bold select-none`}
            style={{
                background: "linear-gradient(135deg, #fffef0 0%, #f5f0d0 100%)",
                border: "1px solid #c8b87a"
            }}>
            <span style={{
                color: red ? "#c0392b" : "#1a1a1a",
                fontSize: small ? "0.85rem" : "1.3rem",
                lineHeight: 1
            }}>
                {label.length === 3 ? label[0] + label[1] : label[0]}
            </span>
            <span style={{
                color: red ? "#c0392b" : "#1a1a1a",
                fontSize: small ? "1rem" : "1.5rem",
                lineHeight: 1
            }}>
                {label.length === 3 ? label[2] : label[1]}
            </span>
        </div>
    );
}
