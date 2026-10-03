import { ArrowUpDown, CircleDot, LocateFixed, MapPin } from "lucide-react";
import React from "react";

import type { MapMarker } from "../../lib/api";
import PlacePicker from "./PlacePicker";
import { campusFirst } from "../../lib/placeOrder";

interface RouteStopsProps {
    title: string;
    locations: MapMarker[];
    originId: string;
    originName: string;
    setOriginId: (id: string) => void;
    destinationId: string;
    destinationName: string;
    setDestinationId: (id: string) => void;
    locationsLoading?: boolean;
    getUserLocation: () => void;
    isWatching: boolean;
    usingGps: boolean;
    showDestinationPicker?: boolean;
    onSwap?: () => void;
}

export const RouteStops = React.memo(function RouteStops({
    title, locations, originId, originName, setOriginId,
    destinationId, destinationName, setDestinationId,
    locationsLoading = false, getUserLocation, isWatching, usingGps,
    showDestinationPicker = true, onSwap,
}: RouteStopsProps) {
    const options = React.useMemo(
        () => campusFirst(locations),
        [locations],
    );

    return (
        <section aria-label={title} className="space-y-2.5">
            <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                    {title}
                </p>
                <button
                    onClick={getUserLocation}
                    aria-pressed={usingGps}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-semibold transition active:scale-95 ${
                        usingGps
                            ? "bg-blue-600 text-white shadow-md shadow-blue-600/25"
                            : "bg-blue-50 text-blue-700 hover:bg-blue-100"
                    }`}
                >
                    <LocateFixed size={13} className={isWatching ? "animate-pulse" : ""} />
                    {isWatching ? "Live tracking on" : "Use my location"}
                </button>
            </div>

            <div className="relative space-y-2.5">
                {showDestinationPicker && (
                    <span className="pointer-events-none absolute left-[27px] top-[46px] h-[26px] w-px border-l-2 border-dotted border-slate-200" />
                )}

                {onSwap && showDestinationPicker && (
                    <button
                        onClick={onSwap}
                        aria-label="Swap start and destination"
                        className="absolute right-1.5 top-[38px] z-[95] grid h-8 w-8 place-items-center rounded-full bg-white text-slate-500 shadow-sm ring-1 ring-slate-200 transition hover:text-slate-900 active:scale-90"
                    >
                        <ArrowUpDown size={14} strokeWidth={2.3} />
                    </button>
                )}

                <PlacePicker
                    label="Start Point"
                    placeholder="Choose a starting point"
                    selectedId={originId}
                    displayValue={originName}
                    options={options}
                    onSelect={(opt) => setOriginId(opt.id)}
                    loading={locationsLoading}
                    highlighted={usingGps}
                    leading={<CircleDot size={15} strokeWidth={2.4} />}
                />

                {showDestinationPicker && (
                    <PlacePicker
                        label="Destination"
                        placeholder="Choose a destination"
                        selectedId={destinationId}
                        displayValue={destinationName}
                        options={options}
                        onSelect={(opt) => setDestinationId(opt.id)}
                        loading={locationsLoading}
                        leading={<MapPin size={15} strokeWidth={2.4} />}
                    />
                )}
            </div>
        </section>
    );
});
