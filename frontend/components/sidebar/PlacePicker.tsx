"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Search } from "lucide-react";

import type { MapMarker } from "@/lib/api";
import { styleFor } from "../map/categories";
import { CategoryGlyph } from "../map/CategoryGlyph";

export interface PickerProps {
    label: string;
    placeholder: string;
    selectedId: string;
    displayValue: string;
    options: MapMarker[];
    onSelect: (option: MapMarker) => void;
    loading?: boolean;
    highlighted?: boolean;
    leading: React.ReactNode;
}

export default function PlacePicker({
    label, placeholder, selectedId, displayValue, options, onSelect,
    loading = false, highlighted = false, leading,
}: PickerProps) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const rootRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const close = () => { setOpen(false); setQuery(""); };

    useEffect(() => {
        const onPointer = (event: Event) => {
            if (rootRef.current && !rootRef.current.contains(event.target as Node)) close();
        };
        const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
        document.addEventListener("mousedown", onPointer);
        document.addEventListener("touchstart", onPointer);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onPointer);
            document.removeEventListener("touchstart", onPointer);
            document.removeEventListener("keydown", onKey);
        };
    }, []);

    useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

    const needle = query.trim().toLowerCase();
    const filtered = needle
        ? options.filter((opt) => opt.name.toLowerCase().includes(needle))
        : options;

    return (
        <div ref={rootRef} className="relative">
            <button
                type="button"
                aria-haspopup="listbox"
                aria-expanded={open}
                aria-label={label}
                disabled={loading}
                onClick={() => (open ? close() : setOpen(true))}
                className={`flex w-full items-center gap-3 rounded-2xl border px-3.5 py-3 text-left transition disabled:cursor-wait disabled:opacity-60 ${
                    highlighted
                        ? "border-blue-500 bg-blue-50/40 ring-4 ring-blue-500/10"
                        : open
                            ? "border-blue-500 bg-white ring-4 ring-blue-500/10"
                            : "border-slate-200 bg-slate-50/70 hover:border-slate-300"
                }`}
            >
                <span className="shrink-0 text-slate-400">{leading}</span>
                <span className={`min-w-0 flex-1 truncate text-[13.5px] ${
                    displayValue ? "font-medium text-slate-800" : "text-slate-400"
                }`}>
                    {displayValue || placeholder}
                </span>
                {loading
                    ? <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-blue-500/30 border-t-blue-500" />
                    : <ChevronDown size={16} className={`shrink-0 text-slate-300 transition ${open ? "rotate-180 text-blue-500" : ""}`} />}
            </button>

            <div
                role="listbox"
                aria-label={label}
                aria-hidden={!open}
                inert={!open}
                className={`absolute left-0 right-0 top-full z-[90] mt-2 overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-2xl transition-all ${
                    open ? "opacity-100" : "pointer-events-none -translate-y-1 opacity-0"
                }`}
            >
                <div className="border-b border-slate-100 p-2">
                    <div className="relative">
                        <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                            ref={inputRef}
                            type="text"
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            placeholder="Filter places..."
                            className="w-full rounded-xl bg-slate-50 py-2.5 pl-9 pr-3 text-[12.5px] text-slate-700 outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-blue-500/20"
                        />
                    </div>
                </div>

                <div className="custom-scrollbar max-h-60 overflow-y-auto p-1.5">
                    {filtered.slice(0, 200).map((opt) => {
                        const style = styleFor(opt.category);
                        const selected = selectedId === opt.id;
                        return (
                            <button
                                key={opt.id}
                                type="button"
                                role="option"
                                aria-selected={selected}
                                onClick={() => { onSelect(opt); close(); }}
                                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition ${
                                    selected ? "bg-blue-50" : "hover:bg-slate-50"
                                }`}
                            >
                                <span
                                    className="grid h-5 w-5 shrink-0 place-items-center rounded-md"
                                    style={{ background: style.ring, color: style.color }}
                                >
                                    <CategoryGlyph category={opt.category} size={11} strokeWidth={2.4} />
                                </span>
                                <span className="min-w-0 flex-1">
                                    <span className={`block truncate text-[12.5px] ${
                                        selected ? "font-semibold text-blue-700" : "font-medium text-slate-700"
                                    }`}>
                                        {opt.name}
                                    </span>
                                    <span className="block truncate text-[10.5px] text-slate-400">
                                        {opt.type.replace(/_/g, " ")}
                                    </span>
                                </span>
                                {selected && <Check size={14} className="shrink-0 text-blue-600" />}
                            </button>
                        );
                    })}
                    {filtered.length === 0 && (
                        <p className="px-3 py-8 text-center text-[12px] text-slate-400">
                            No place matches that search.
                        </p>
                    )}
                    {filtered.length > 200 && (
                        <p className="px-3 py-2.5 text-center text-[11px] text-slate-400">
                            Showing 200 of {filtered.length}. Keep typing to narrow down.
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
}
