import { useEffect, useRef, useState } from "react";
import { Search, CornerDownLeft, Command, type LucideIcon } from "lucide-react";

export interface PaletteAction {
  label: string;
  desc?: string;
  hint?: string;
  icon: LucideIcon;
  run: () => void;
}

export default function CommandPalette({
  open,
  onClose,
  actions,
}: {
  open: boolean;
  onClose: () => void;
  actions: PaletteAction[];
}) {
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const list = actions.filter((a) => a.label.toLowerCase().includes(q.toLowerCase()));

  useEffect(() => {
    if (!open) return;
    setQ("");
    setIdx(0);
    const t = setTimeout(() => inputRef.current?.focus(), 40);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setIdx((i) => Math.min(i + 1, Math.max(list.length - 1, 0)));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setIdx((i) => Math.max(i - 1, 0));
      }
      if (e.key === "Enter" && list[idx]) {
        list[idx].run();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, list, idx, onClose]);

  if (!open) return null;

  return (
    <div className="palette-overlay" onMouseDown={onClose}>
      <div className="palette" onMouseDown={(e) => e.stopPropagation()}>
        <div className="palette-input">
          <Search size={17} />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setIdx(0);
            }}
            placeholder="Ketik perintah atau cari…"
            aria-label="Pencarian perintah"
          />
          <kbd>ESC</kbd>
        </div>

        <div className="palette-label">Aksi cepat</div>
        <ul className="palette-list">
          {list.map((a, i) => {
            const Icon = a.icon;
            return (
              <li key={a.label}>
                <button
                  className={i === idx ? "is-active" : ""}
                  onMouseEnter={() => setIdx(i)}
                  onClick={() => {
                    a.run();
                    onClose();
                  }}
                >
                  <span className="palette-icon">
                    <Icon size={16} />
                  </span>
                  <span className="palette-copy">
                    <b>{a.label}</b>
                    {a.desc ? <span>{a.desc}</span> : null}
                  </span>
                  {a.hint ? <kbd>{a.hint}</kbd> : null}
                </button>
              </li>
            );
          })}
        </ul>

        {list.length === 0 ? (
          <div className="palette-empty">Tidak ada perintah yang cocok.</div>
        ) : null}

        <div className="palette-foot">
          <span>
            <Command size={12} /> Beosabasi
          </span>
          <span>
            <CornerDownLeft size={12} /> pilih · ESC tutup
          </span>
        </div>
      </div>
    </div>
  );
}
