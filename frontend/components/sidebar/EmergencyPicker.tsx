"use client";

import { useMemo } from "react";
import { ChevronRight, Loader2, MapPin, Phone, Search, TriangleAlert } from "lucide-react";

import {
    errorMessage,
    type CategorySummary,
    type EmergencyCategory,
    type MapMarker,
    type NearestResult,
    type TrafficLevel,
    type TransportMode,
} from "../../lib/api";
import { useNearest } from "../../lib/queries";
import { styleFor } from "../map/categories";
import { CategoryGlyph } from "../map/CategoryGlyph";

interface EmergencyPickerProps {
    categories: CategorySummary[];
    locations: MapMarker[];
    origin: { lat: number; lon: number } | null;
    transportMode: TransportMode;
    trafficLevel: TrafficLevel;
    selectedId: string;
    active: EmergencyCategory | null;
    onCategoryChange: (category: EmergencyCategory | null) => void;
    subtype: string | null;
    onSubtypeChange: (subtype: string | null) => void;
    onSelect: (place: MapMarker) => void;
    onRequestLocation: () => void;
    onBrowseAll: () => void;
}

function SubtypeChip({ label, count, active, onClick }: {
    label: string;
    count: number;
    active: boolean;
    onClick: () => void;
}) {
    return (
        <button
            onClick={onClick}
            aria-pressed={active}
            disabled={count === 0}
            className={`rounded-full px-3 py-1.5 text-[11.5px] font-semibold transition disabled:opacity-40 ${
                active
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
        >
            {label}
            <span className={`ml-1.5 tabular-nums ${active ? "text-white/70" : "text-slate-400"}`}>
                {count}
            </span>
        </button>
    );
}

export default function EmergencyPicker({
    categories,
    locations,
    origin,
    transportMode,
    trafficLevel,
    selectedId,
    active,
    onCategoryChange,
    subtype,
    onSubtypeChange,
    onSelect,
    onRequestLocation,
    onBrowseAll,
}: EmergencyPickerProps) {
    const subtypes = useMemo(
        () => categories.find((entry) => entry.category === active)?.subtypes ?? [],
        [categories, active],
    );

    const nearest = useNearest(active, origin, transportMode, trafficLevel, subtype);
    const results = nearest.data ?? [];
    const loading = nearest.isFetching;
    const error = nearest.isError
        ? errorMessage(nearest.error, "Could not rank these facilities.")
        : "";

    const byCategory = useMemo(() => {
        const grouped = new Map<string, MapMarker[]>();
        for (const place of locations) {
            const list = grouped.get(place.category);
            if (list) list.push(place);
            else grouped.set(place.category, [place]);
        }
        return grouped;
    }, [locations]);

    const sortedFallback = useMemo(() => {
        if (!active) return [];
        const wanted = subtype
            ? new Set(subtypes.find((entry) => entry.key === subtype)?.types ?? [])
            : null;
        return [...(byCategory.get(active) ?? [])]
            .filter((place) => !wanted || wanted.has(place.type))
            .sort((a, b) => (a.on_campus === b.on_campus
                ? a.name.localeCompare(b.name)
                : a.on_campus ? -1 : 1));
    }, [active, byCategory, subtype, subtypes]);

    const rows: (NearestResult | MapMarker)[] =
        active && !origin ? sortedFallback : results;

    return (
        <section aria-label="Emergency services" className="space-y-4">
            <div>
                <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                    What do you need?
                </h2>
                <div className="mt-2.5 grid grid-cols-3 gap-2">
                    {categories.map((entry) => {
                        const style = styleFor(entry.category);
                        const isActive = active === entry.category;
                        const empty = entry.count === 0;
                        return (
                            <button
                                key={entry.category}
                                onClick={() => {
                                    onSubtypeChange(null);
                                    onCategoryChange(isActive ? null : entry.category);
                                }}
                                disabled={empty}
                                aria-pressed={isActive}
                                className={`flex flex-col items-center gap-1.5 rounded-2xl border p-3 transition active:scale-[.97] disabled:opacity-40 ${
                                    isActive
                                        ? "border-transparent text-white shadow-lg"
                                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                                }`}
                                style={isActive ? { background: style.color } : undefined}
                            >
                                <span
                                    className="grid h-7 w-7 place-items-center rounded-xl"
                                    style={{
                                        background: isActive ? "rgba(255,255,255,.22)" : style.ring,
                                        color: isActive ? "#fff" : style.color,
                                    }}
                                >
                                    <CategoryGlyph category={entry.category} size={16} />
                                </span>
                                <span className="text-[10.5px] font-semibold leading-tight">
                                    {entry.label}
                                </span>
                                <span className={`text-[9.5px] ${isActive ? "text-white/75" : "text-slate-400"}`}>
                                    {entry.count}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </div>

            {active && (
                <div className="space-y-2">
                    {subtypes.length > 1 && (
                        <div role="group" aria-label="Narrow by kind"
                             className="flex flex-wrap gap-1.5 pb-0.5">
                            <SubtypeChip label="All" count={subtypes.reduce((n, s) => n + s.count, 0)}
                                         active={subtype === null}
                                         onClick={() => onSubtypeChange(null)} />
                            {subtypes.map((option) => (
                                <SubtypeChip
                                    key={option.key}
                                    label={option.label}
                                    count={option.count}
                                    active={subtype === option.key}
                                    onClick={() => onSubtypeChange(option.key)}
                                />
                            ))}
                        </div>
                    )}

                    {!origin && (
                        <button
                            onClick={onRequestLocation}
                            className="flex w-full items-start gap-2.5 rounded-2xl bg-blue-50 px-3.5 py-3 text-left text-[12px] text-blue-800"
                        >
                            <MapPin size={15} className="mt-px shrink-0" />
                            <span>
                                <span className="font-semibold">Share your location</span> to rank these
                                by how fast each can be reached. Showing them alphabetically for now.
                            </span>
                        </button>
                    )}

                    {error && (
                        <p role="alert" className="flex items-start gap-2 rounded-2xl bg-red-50 px-3.5 py-3 text-[12px] text-red-700">
                            <TriangleAlert size={15} className="mt-px shrink-0" />
                            {error}
                        </p>
                    )}

                    {loading && (
                        <p className="flex items-center gap-2 px-1 py-3 text-[12px] text-slate-500">
                            <Loader2 size={14} className="animate-spin" /> Ranking by travel time…
                        </p>
                    )}

                    {!loading && rows.length === 0 && !error && (
                        <p className="px-1 py-3 text-[12px] text-slate-500">
                            Nothing mapped in this category yet.
                        </p>
                    )}

                    <ul className="space-y-1.5">
                        {rows.map((place) => {
                            const ranked = "time_min" in place ? place : null;
                            const chosen = selectedId === place.id;
                            return (
                                <li key={place.id}>
                                    <div className={`flex items-center gap-2 rounded-2xl border px-3 py-2.5 transition ${
                                        chosen ? "border-blue-500 bg-blue-50/50" : "border-slate-200 bg-white hover:border-slate-300"
                                    }`}>
                                        <button
                                            onClick={() => onSelect(place)}
                                            className="flex min-w-0 flex-1 items-center gap-3 text-left"
                                        >
                                            <span className="min-w-0 flex-1">
                                                <span className="block truncate text-[13px] font-medium text-slate-800">
                                                    {place.name}
                                                </span>
                                                <span className="block text-[11px] text-slate-500">
                                                    {ranked
                                                        ? `${ranked.time_min} min · ${ranked.distance_km} km`
                                                        : "distance unavailable"}
                                                </span>
                                            </span>
                                            <ChevronRight size={15} className="shrink-0 text-slate-300" />
                                        </button>
                                        {place.phone && (
                                            <a
                                                href={`tel:${place.phone}`}
                                                aria-label={`Call ${place.name}`}
                                                className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-50 text-emerald-700"
                                            >
                                                <Phone size={15} />
                                            </a>
                                        )}
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                </div>
            )}

            <button
                onClick={onBrowseAll}
                className="flex w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-slate-300 py-2.5 text-[12px] font-medium text-slate-500 transition hover:border-slate-400 hover:text-slate-700"
            >
                <Search size={14} /> Browse all places
            </button>
        </section>
    );
}
