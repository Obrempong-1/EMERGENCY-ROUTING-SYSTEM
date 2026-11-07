"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { bearingBetween, metresBetween } from "./geo";

export interface Coords {
    lat: number;
    lon: number;
}

export type ServiceBounds = {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
} | null;

export type LocationStatus =
    | "idle"
    | "locating"
    | "ready"
    | "denied"
    | "unavailable"
    | "outside";

const GEO_OPTIONS: PositionOptions = {
    enableHighAccuracy: true,
    maximumAge: 0,
    timeout: 15000,
};

const AUTO_REQUEST_DELAY_MS = 500;

const MOVING_MPS = 0.8;
const HEADING_BASELINE_M = 8;
const HEADING_FRESH_MS = 20_000;
const TRAVEL_HOLD_MS = 5_000;

const MESSAGES: Record<LocationStatus, string> = {
    idle: "",
    locating: "",
    ready: "",
    denied: "Location is off, so we cannot tell which one is closest.",
    unavailable: "We could not find your location. Try again outdoors.",
    outside: "You are outside campus, so we cannot route from where you are.",
};

export function useUserLocation(bounds: ServiceBounds, auto: boolean) {
    const [location, setLocation] = useState<Coords | null>(null);
    const [firstFix, setFirstFix] = useState<Coords | null>(null);
    const [status, setStatus] = useState<LocationStatus>("idle");
    const [watching, setWatching] = useState(false);
    const heading = useRef<{ degrees: number; at: number } | null>(null);
    const [travelHeading, setTravelHeading] = useState<number | null>(null);
    const [accuracy, setAccuracy] = useState<number | null>(null);

    const watchId = useRef<number | null>(null);
    const lastMoved = useRef<Coords | null>(null);
    const boundsRef = useRef<ServiceBounds>(bounds);
    const asked = useRef(false);

    useEffect(() => {
        boundsRef.current = bounds;
    }, [bounds]);

    const inside = useCallback((lat: number, lon: number) => {
        const box = boundsRef.current;
        if (!box) return true;
        return lat >= box.min_lat && lat <= box.max_lat
            && lon >= box.min_lon && lon <= box.max_lon;
    }, []);

    const stopWatching = useCallback(() => {
        if (watchId.current !== null) {
            navigator.geolocation.clearWatch(watchId.current);
            watchId.current = null;
        }
        setWatching(false);
    }, []);

    const track = useCallback((coords: GeolocationCoordinates, here: Coords) => {
        const moving = (degrees: number) => {
            heading.current = { degrees, at: Date.now() };
            lastMoved.current = here;
            setTravelHeading(degrees);
        };
        const reported = coords.heading;
        const from = lastMoved.current;
        if (reported !== null && Number.isFinite(reported)
                && coords.speed !== null && coords.speed >= MOVING_MPS) {
            moving(reported);
        } else if (!from) {
            lastMoved.current = here;
        } else if (metresBetween(from, here) >= HEADING_BASELINE_M) {
            moving(bearingBetween(from, here));
        } else if (!heading.current || Date.now() - heading.current.at > TRAVEL_HOLD_MS) {
            setTravelHeading(null);
        }
    }, []);

    const accept = useCallback((position: GeolocationPosition) => {
        const { latitude: lat, longitude: lon } = position.coords;
        if (!inside(lat, lon)) {
            setLocation(null);
            setStatus("outside");
            stopWatching();
            return;
        }
        track(position.coords, { lat, lon });
        setAccuracy(position.coords.accuracy);
        setLocation({ lat, lon });
        setFirstFix((previous) => previous ?? { lat, lon });
        setStatus("ready");
    }, [inside, stopWatching, track]);

    const currentHeading = useCallback((): number | null => {
        const known = heading.current;
        if (!known || Date.now() - known.at > HEADING_FRESH_MS) return null;
        return known.degrees;
    }, []);

    const reject = useCallback((error: GeolocationPositionError) => {
        setStatus(error.code === error.PERMISSION_DENIED ? "denied" : "unavailable");
        stopWatching();
    }, [stopWatching]);

    const request = useCallback(() => {
        asked.current = true;
        if (typeof navigator === "undefined" || !navigator.geolocation) {
            setStatus("unavailable");
            return;
        }
        setStatus("locating");
        navigator.geolocation.getCurrentPosition(accept, reject, GEO_OPTIONS);
    }, [accept, reject]);

    const startWatching = useCallback(() => {
        if (typeof navigator === "undefined" || !navigator.geolocation) {
            setStatus("unavailable");
            return;
        }
        if (watchId.current !== null) return;
        asked.current = true;
        setWatching(true);
        if (!location) setStatus("locating");
        watchId.current = navigator.geolocation.watchPosition(accept, reject, GEO_OPTIONS);
    }, [accept, reject, location]);

    const setTracking = useCallback((on: boolean) => {
        if (on) startWatching();
        else stopWatching();
    }, [startWatching, stopWatching]);

    const toggle = useCallback(() => {
        if (watching) stopWatching();
        else startWatching();
    }, [watching, startWatching, stopWatching]);

    useEffect(() => {
        if (!auto || asked.current || status !== "idle") return;
        const timer = setTimeout(request, AUTO_REQUEST_DELAY_MS);
        return () => clearTimeout(timer);
    }, [auto, status, request]);

    useEffect(() => () => {
        if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
    }, []);

    return {
        location,
        currentHeading,
        travelHeading,
        accuracy,
        firstFix,
        status,
        message: MESSAGES[status],
        watching,
        request,
        setTracking,
        toggle,
        stopWatching,
    };
}
