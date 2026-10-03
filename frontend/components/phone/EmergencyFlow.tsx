"use client";

import { X } from "lucide-react";

import type { CategorySummary, EmergencyCategory } from "../../lib/api";
import { styleFor } from "../map/categories";
import { CategoryGlyph } from "../map/CategoryGlyph";

const PHONE_LABELS: Partial<Record<EmergencyCategory, { label: string; hint?: string }>> = {
    medical: { label: "Hospital", hint: "& pharmacies" },
    police: { label: "Police" },
    fire_station: { label: "Fire" },
    security: { label: "Campus security" },
};

const ORDER: EmergencyCategory[] = ["medical", "police", "fire_station", "security"];

interface EmergencyFlowProps {
    categories: CategorySummary[];
    active: EmergencyCategory | null;
    onPick: (category: EmergencyCategory) => void;
    onClear: () => void;
    compact: boolean;
}

export default function EmergencyFlow({
    categories, active, onPick, onClear, compact,
}: EmergencyFlowProps) {
    const available = ORDER
        .map((key) => categories.find((entry) => entry.category === key))
        .filter((entry): entry is CategorySummary => Boolean(entry));

    const shown = active && !available.some((entry) => entry.category === active)
        ? [...categories.filter((entry) => entry.category === active), ...available]
        : available;

    if (compact) {
        return (
            <div className="flex gap-1.5 overflow-x-auto px-5 pb-3">
                <button
                    onClick={onClear}
                    aria-label="Back to the emergency list"
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 transition active:scale-95"
                >
                    <X size={16} />
                </button>
                {shown.map((entry) => {
                    const style = styleFor(entry.category);
                    const copy = PHONE_LABELS[entry.category];
                    const isActive = active === entry.category;
                    return (
                        <button
                            key={entry.category}
                            onClick={() => onPick(entry.category)}
                            aria-pressed={isActive}
                            className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-2 text-[12.5px] font-semibold transition active:scale-95 ${
                                isActive ? "text-white" : "bg-slate-100 text-slate-600"
                            }`}
                            style={isActive ? { background: style.color } : undefined}
                        >
                            <CategoryGlyph category={entry.category} size={15} />
                            {copy?.label ?? entry.label}
                        </button>
                    );
                })}
            </div>
        );
    }

    return (
        <div className="px-5 pb-4">
            <h2 className="text-[15px] font-semibold tracking-tight text-slate-900">
                What&apos;s the emergency?
            </h2>

            <div className="mt-3 grid grid-cols-2 gap-2.5">
                {available.map((entry) => {
                    const style = styleFor(entry.category);
                    const copy = PHONE_LABELS[entry.category];
                    const isActive = active === entry.category;
                    return (
                        <button
                            key={entry.category}
                            onClick={() => onPick(entry.category)}
                            aria-pressed={isActive}
                            disabled={entry.count === 0}
                            className={`flex items-center gap-3 rounded-2xl border p-3.5 text-left transition active:scale-[.97] disabled:opacity-40 ${
                                isActive
                                    ? "border-transparent text-white shadow-lg"
                                    : "border-slate-200 bg-white text-slate-800"
                            }`}
                            style={isActive ? { background: style.color } : undefined}
                        >
                            <span
                                className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl"
                                style={{
                                    background: isActive ? "rgba(255,255,255,.22)" : style.ring,
                                    color: isActive ? "#fff" : style.color,
                                }}
                            >
                                <CategoryGlyph category={entry.category} size={20} />
                            </span>
                            <span className="min-w-0">
                                <span className="block text-[13.5px] font-semibold leading-tight">
                                    {copy?.label ?? entry.label}
                                </span>
                                {copy?.hint && (
                                    <span className={`block text-[10.5px] ${
                                        isActive ? "text-white/70" : "text-slate-400"
                                    }`}>
                                        {copy.hint}
                                    </span>
                                )}
                            </span>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
