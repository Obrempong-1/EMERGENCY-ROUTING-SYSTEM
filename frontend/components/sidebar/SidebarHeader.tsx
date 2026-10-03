import { PanelLeftClose, Search, Siren, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { MapMarker } from "../../lib/api";
import { styleFor } from "../map/categories";

interface SidebarHeaderProps {
    locations: MapMarker[];
    onLocationSelect: (loc: MapMarker) => void;
    onCollapse?: () => void;
}

export default function SidebarHeader({ locations, onLocationSelect, onCollapse }: SidebarHeaderProps) {
    const [query, setQuery] = useState("");
    const [open, setOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    const needle = query.trim().toLowerCase();
    const results = needle.length > 1
        ? locations.filter((loc) => loc.name.toLowerCase().includes(needle)).slice(0, 6)
        : [];

    useEffect(() => {
        const close = (event: Event) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setOpen(false);
            }
        };
        const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
        document.addEventListener("mousedown", close);
        document.addEventListener("touchstart", close);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", close);
            document.removeEventListener("touchstart", close);
            document.removeEventListener("keydown", onKey);
        };
    }, []);

    return (
        <div ref={containerRef} className="relative z-[50] shrink-0 px-6 pb-5 pt-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span className="grid h-10 w-10 place-items-center rounded-2xl bg-red-600 text-white shadow-lg shadow-red-600/25">
                        <Siren size={19} />
                    </span>
                    <div>
                        <h1 className="text-[15px] font-semibold leading-none tracking-tight text-slate-900">
                            KNUST RESPONSE
                        </h1>
                        <p className="mt-1 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">
                            EMERGENCY GIS
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-1.5">
                    {onCollapse && (
                        <button
                            onClick={onCollapse}
                            aria-label="Hide route planner"
                            title="Hide planner"
                            className="grid h-8 w-8 place-items-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 active:scale-90"
                        >
                            <PanelLeftClose size={16} />
                        </button>
                    )}
                </div>
            </div>

            <div className="relative mt-5">
                <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                    type="text"
                    value={query}
                    onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
                    onFocus={() => setOpen(true)}
                    placeholder="Search places"
                    aria-label="Search places on and near campus"
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50/70 py-3 pl-10 pr-9 text-[13.5px] text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-500/10"
                />
                {query && (
                    <button
                        onClick={() => { setQuery(""); setOpen(false); }}
                        aria-label="Clear search"
                        className="absolute right-3 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-full bg-slate-200 text-slate-600"
                    >
                        <X size={12} />
                    </button>
                )}

                {open && results.length > 0 && (
                    <ul className="absolute left-0 right-0 top-full z-[60] mt-2 overflow-hidden rounded-2xl border border-slate-100 bg-white p-1.5 shadow-2xl">
                        {results.map((loc) => {
                            const style = styleFor(loc.category);
                            return (
                                <li key={loc.id}>
                                    <button
                                        onClick={() => {
                                            onLocationSelect(loc);
                                            setQuery("");
                                            setOpen(false);
                                        }}
                                        className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-slate-50"
                                    >
                                        <span
                                            className="h-2 w-2 shrink-0 rounded-full"
                                            style={{ background: style.color }}
                                        />
                                        <span className="min-w-0 flex-1">
                                            <span className="block truncate text-[13px] font-medium text-slate-800">
                                                {loc.name}
                                            </span>
                                            <span className="block truncate text-[10.5px] text-slate-400">
                                                {loc.type.replace(/_/g, " ")}
                                            </span>
                                        </span>
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>
        </div>
    );
}
