"use client";

import { X } from "lucide-react";

import type { RouteResponse } from "../../lib/api";

interface RouteSummaryProps {
    route: RouteResponse;
    destinationName: string;
    arrival: string | null;
    onClear: () => void;
}

export function RouteSummary({
    route, destinationName, arrival, onClear,
}: RouteSummaryProps) {
    return (
        <div className="flex items-center justify-between gap-3 px-5 pb-4">
            <div className="min-w-0">
                <p className="truncate text-[15px] font-semibold tracking-tight text-slate-900">
                    {destinationName || "On your way"}
                </p>
                <p className="mt-0.5 truncate text-[12px] text-slate-500">
                    {arrival ? `Arrive about ${arrival}` : `${route.distance_km} km away`}
                </p>
            </div>
            <button
                onClick={onClear}
                aria-label="Clear route"
                className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-500 transition active:scale-95"
            >
                <X size={17} />
            </button>
        </div>
    );
}
