"use client";

import { useRef } from "react";
import { Route, Siren } from "lucide-react";

export type PanelMode = "emergency" | "directions";

const TABS: { value: PanelMode; label: string; Icon: typeof Siren }[] = [
    { value: "emergency", label: "Emergency", Icon: Siren },
    { value: "directions", label: "Directions", Icon: Route },
];

interface Props {
    value: PanelMode;
    onChange: (mode: PanelMode) => void;
}

export default function ModeTabs({ value, onChange }: Props) {
    const refs = useRef<(HTMLButtonElement | null)[]>([]);

    const move = (index: number, step: number) => {
        const next = (index + step + TABS.length) % TABS.length;
        onChange(TABS[next].value);
        refs.current[next]?.focus();
    };

    return (
        <div
            role="tablist"
            aria-label="Panel mode"
            className="flex gap-1 rounded-2xl bg-slate-100 p-1"
        >
            {TABS.map(({ value: tab, label, Icon }, index) => {
                const active = tab === value;
                return (
                    <button
                        key={tab}
                        ref={(node) => { refs.current[index] = node; }}
                        role="tab"
                        aria-selected={active}
                        tabIndex={active ? 0 : -1}
                        onClick={() => onChange(tab)}
                        onKeyDown={(event) => {
                            if (event.key === "ArrowRight") move(index, 1);
                            if (event.key === "ArrowLeft") move(index, -1);
                        }}
                        className={`flex flex-1 items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-[12.5px] font-semibold transition ${
                            active
                                ? "bg-white text-slate-900 shadow-sm"
                                : "text-slate-500 hover:text-slate-700"
                        }`}
                    >
                        <Icon size={14} strokeWidth={2.2} />
                        {label}
                    </button>
                );
            })}
        </div>
    );
}
