export default function LogEntry({ entry }) {
    const colors = {
        action: "#7ec8a0",
        result: "#f0c060",
        system: "#8ec8f0",
        warning: "#f08080",
    };
    return (
        <div style={{
            color: colors[entry.type] || "#a0c0a0",
            fontSize: "0.78rem", padding: "2px 0",
            borderBottom: "1px solid #1a3a2a"
        }}>
            {entry.text}
        </div>
    );
}
