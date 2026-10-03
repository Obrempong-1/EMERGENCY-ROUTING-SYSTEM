"use client";

import { useMemo } from "react";
import { Loader2, MapPin, TriangleAlert } from "lucide-react";

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
import type { Coords, LocationStatus } from "../../lib/useUserLocation";
import NearestCard from "./NearestCard";

const MAX_ROWS = 5;

interface NearestListProps {
    category: EmergencyCategory;
    categories: CategorySummary[];
    locations: MapMarker[];
    origin: Coords | null;
    locationStatus: LocationStatus;
    locationMessage: string;
    onRequestLocation: () => void;
    transportMode: TransportMode;
    trafficLevel: TrafficLevel;
    subtype: string | null;
    onSubtypeChange: (subtype: string | null) => void;
    destinationId: string;
    onGo: (place: MapMarker) => void;
    onPreview: (place: MapMarker) => void;
}

export default function NearestList({
    category,
    categories,
    locations,
    origin,
    locationStatus,
    locationMessage,
    onRequestLocation,
    transportMode,
    trafficLevel,
    subtype,
    onSubtypeChange,
    destinationId,
    onGo,
    onPreview,
}: NearestListProps) {
    const subtypes = useMemo(
        () => categories.find((entry) => entry.category === category)?.subtypes ?? [],
        [categories, category],
    );

    const nearest = useNearest(category, origin, transportMode, trafficLevel, subtype);
    const ranked = nearest.data ?? [];

    const fallback = useMemo(() => {
        const wanted = subtype
            ? new Set(subtypes.find((entry) => entry.key === subtype)?.types ?? [])
            : null;
        return locations
            .filter((place) => place.category === category)
            .filter((place) => !wanted || wanted.has(place.type))
            .sort((a, b) => a.name.localeCompare(b.name));
    }, [locations, category, subtype, subtypes]);

    const rows: (NearestResult | MapMarker)[] =
        origin && ranked.length > 0 ? ranked : fallback;
    const shown = rows.slice(0, MAX_ROWS);
    const waiting = nearest.isFetching || locationStatus === "locating";
    const notice = origin ? "" : locationMessage;

    return (
        <div className="space-y-2.5 px-5 pb-6 pt-1">
            {subtypes.length > 1 && (
                <div role="group" aria-label="Kind" className="flex gap-1.5 pb-1">
                    {[{ key: null, label: "All" },
                      ...subtypes.map((entry) => ({ key: entry.key, label: entry.label }))
                    ].map((option) => (
                        <button
                            key={option.key ?? "all"}
                            onClick={() => onSubtypeChange(option.key)}
                            aria-pressed={subtype === option.key}
                            className={`rounded-full px-3.5 py-2 text-[12px] font-semibold transition ${
                                subtype === option.key
                                    ? "bg-slate-900 text-white"
                                    : "bg-slate-100 text-slate-600"
                            }`}
                        >
                            {option.label}
                        </button>
                    ))}
                </div>
            )}

            {notice && (
                <div className="flex items-start gap-2.5 rounded-2xl bg-amber-50 px-3.5 py-3 text-[12px] text-amber-900">
                    <MapPin size={15} className="mt-px shrink-0" />
                    <span className="min-w-0 flex-1">{notice}</span>
                    <button
                        onClick={onRequestLocation}
                        className="shrink-0 rounded-lg bg-amber-900 px-2.5 py-1.5 text-[11.5px] font-semibold text-white"
                    >
                        Try again
                    </button>
                </div>
            )}

            {nearest.isError && (
                <p role="alert" className="flex items-start gap-2 rounded-2xl bg-red-50 px-3.5 py-3 text-[12px] text-red-700">
                    <TriangleAlert size={15} className="mt-px shrink-0" />
                    {errorMessage(nearest.error, "Could not work out which is closest.")}
                </p>
            )}

            {waiting && shown.length === 0 && (
                <p className="flex items-center gap-2 px-1 py-3 text-[12px] text-slate-500">
                    <Loader2 size={14} className="animate-spin" /> Finding the closest&hellip;
                </p>
            )}

            {!waiting && shown.length === 0 && (
                <p className="px-1 py-3 text-[12px] text-slate-500">
                    Nothing of this kind is mapped yet.
                </p>
            )}

            {shown.map((place, index) => (
                <NearestCard
                    key={place.id}
                    place={place}
                    hero={index === 0 && Boolean(origin)}
                    chosen={place.id === destinationId}
                    onGo={() => onGo(place)}
                    onPreview={() => onPreview(place)}
                />
            ))}
        </div>
    );
}
