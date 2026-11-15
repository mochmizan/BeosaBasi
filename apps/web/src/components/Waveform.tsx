import { useMemo, type CSSProperties } from "react";

export default function Waveform({
  bars = 48,
  active = false,
  seed = 7,
  height = 44,
  className = "",
}: {
  bars?: number;
  active?: boolean;
  seed?: number;
  height?: number;
  className?: string;
}) {
  const heights = useMemo(() => {
    let s = seed * 9301 + 49297;
    const next = () => {
      s = (s * 9301 + 49297) % 233280;
      return s / 233280;
    };
    return Array.from({ length: bars }, (_, i) => {
      const envelope = 0.55 + 0.45 * Math.sin((i / bars) * Math.PI);
      return 0.14 + next() * 0.86 * envelope;
    });
  }, [bars, seed]);

  return (
    <div
      className={`waveform ${active ? "is-active" : ""} ${className}`}
      style={{ height }}
      aria-hidden="true"
    >
      {heights.map((h, i) => (
        <span
          key={i}
          style={
            {
              "--h": h,
              "--dur": `${0.62 + (i % 6) * 0.11}s`,
              "--delay": `${(i % 9) * 0.07}s`,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}
