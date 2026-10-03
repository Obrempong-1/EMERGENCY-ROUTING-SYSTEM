"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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

    const watchId = useRef<number | null>(null);
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

    const accept = useCallback((position: GeolocationPosition) => {
        const { latitude: lat, longitude: lon } = position.coords;
        if (!inside(lat, lon)) {
            setLocation(null);
            setStatus("outside");
            stopWatching();
            return;
        }
        setLocation({ lat, lon });
        setFirstFix((previous) => previous ?? { lat, lon });
        setStatus("ready");
    }, [inside, stopWatching]);

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
