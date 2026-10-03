"use client";

import { Phone } from "lucide-react";

import type { MapMarker, NearestResult } from "../../lib/api";

interface NearestCardProps {
    place: MapMarker | NearestResult;
    hero: boolean;
    chosen: boolean;
    onGo: () => void;
    onPreview: () => void;
}

function ranked(place: MapMarker | NearestResult): NearestResult | null {
    return "time_min" in place ? place : null;
}

export default function NearestCard({
    place, hero, chosen, onGo, onPreview,
}: NearestCardProps) {
    const timed = ranked(place);
    const detail = timed
        ? `${timed.time_min} min away · ${timed.distance_km} km`
        : "Tap to see on map";

    if (hero) {
        return (
            <div className="rounded-3xl bg-slate-900 p-4 text-white shadow-lg">
                <p className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-white/55">
                    Closest to you
                </p>
                <button onClick={onPreview} className="mt-1 block w-full text-left">
                    <span className="block text-[17px] font-semibold leading-tight">
                        {place.name}
                    </span>
                    <span className="mt-0.5 block text-[12.5px] text-white/70">{detail}</span>
                </button>

                <div className="mt-3.5 flex gap-2">
                    <button
                        onClick={onGo}
                        className="flex-1 rounded-2xl bg-white py-3 text-[14px] font-semibold text-slate-900 transition active:scale-[.97]"
                    >
                        Go
                    </button>
                    {place.phone && (
                        <a
                            href={`tel:${place.phone}`}
                            aria-label={`Call ${place.name}`}
                            className="flex items-center gap-2 rounded-2xl bg-white/15 px-4 py-3 text-[14px] font-semibold text-white transition active:scale-[.97]"
                        >
                            <Phone size={15} />
                            Call
                        </a>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className={`flex items-center gap-2 rounded-2xl border bg-white px-3.5 py-3 ${
            chosen ? "border-slate-900" : "border-slate-200"
        }`}>
            <button onClick={onPreview} className="min-w-0 flex-1 text-left">
                <span className="block truncate text-[14px] font-medium text-slate-800">
                    {place.name}
                </span>
                <span className="block text-[11.5px] text-slate-500">{detail}</span>
            </button>
            {place.phone && (
                <a
                    href={`tel:${place.phone}`}
                    aria-label={`Call ${place.name}`}
                    className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-emerald-50 text-emerald-700"
                >
                    <Phone size={15} />
                </a>
            )}
            <button
                onClick={onGo}
                className="shrink-0 rounded-xl bg-slate-900 px-4 py-2.5 text-[13px] font-semibold text-white transition active:scale-95"
            >
                Go
            </button>
        </div>
    );
}
