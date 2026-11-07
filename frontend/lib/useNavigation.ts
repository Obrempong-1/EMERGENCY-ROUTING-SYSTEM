"use client";

import { useMemo, useState } from "react";

import type { RouteResponse } from "./api";
import { cumulative, progress, type Progress } from "./navigation";

interface Coords {
    lat: number;
    lon: number;
}

interface Tracked {
    route: RouteResponse;
    here: Coords;
    state: Progress;
}

/**
 * The traveller's progress along `route`, updated on every new position.
 *
 * Each update starts its search from the previous position on the same route,
 * so progress keeps moving forward along legs the route travels twice.
 */
export function useNavigation(
    route: RouteResponse | null,
    here: Coords | null,
    active: boolean,
    heading: () => number | null,
): Progress | null {
    const along = useMemo(() => (route ? cumulative(route.path) : []), [route]);
    const [tracked, setTracked] = useState<Tracked | null>(null);

    if (!active || !route || !here) return null;
    if (tracked && tracked.route === route && tracked.here === here) return tracked.state;

    const hint = tracked && tracked.route === route ? tracked.state.along : 0;
    const next = { route, here, state: progress(route, along, here, hint, heading()) };
    setTracked(next);
    return next.state;
}
