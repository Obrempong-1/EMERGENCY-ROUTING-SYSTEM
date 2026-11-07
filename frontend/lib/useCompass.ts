"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type CompassEvent = DeviceOrientationEvent & { webkitCompassHeading?: number };

interface PermissionGate {
    requestPermission?: () => Promise<"granted" | "denied">;
}

const MIN_CHANGE_DEG = 3;

function gate(): PermissionGate | null {
    if (typeof DeviceOrientationEvent === "undefined") return null;
    return DeviceOrientationEvent as unknown as PermissionGate;
}

function screenAngle(): number {
    return typeof window === "undefined" ? 0 : (window.screen?.orientation?.angle ?? 0);
}

function readHeading(event: CompassEvent): number | null {
    const webkit = event.webkitCompassHeading;
    if (typeof webkit === "number" && Number.isFinite(webkit)) {
        return (webkit + screenAngle()) % 360;
    }
    if (event.absolute && event.alpha !== null) {
        return (360 - event.alpha + screenAngle()) % 360;
    }
    return null;
}

/**
 * The direction the device is facing, in degrees from north, or null.
 *
 * iOS only reports it after `request()` is called from a tap; elsewhere it
 * starts as soon as `active` is true. Changes under a few degrees are dropped
 * so the pointer does not shiver.
 */
export function useCompass(active: boolean) {
    const [heading, setHeading] = useState<number | null>(null);
    const [allowed, setAllowed] = useState(() => !gate()?.requestPermission);
    const last = useRef<number | null>(null);

    const request = useCallback(async () => {
        const requester = gate()?.requestPermission;
        if (!requester) return;
        try {
            setAllowed((await requester()) === "granted");
        } catch {
            setAllowed(false);
        }
    }, []);

    useEffect(() => {
        if (!active || !allowed || typeof window === "undefined") return;
        const onOrientation = (event: Event) => {
            const value = readHeading(event as CompassEvent);
            if (value === null) return;
            const previous = last.current;
            if (previous !== null
                && Math.abs(((value - previous + 540) % 360) - 180) < MIN_CHANGE_DEG) return;
            last.current = value;
            setHeading(value);
        };
        const name = "ondeviceorientationabsolute" in window
            ? "deviceorientationabsolute"
            : "deviceorientation";
        window.addEventListener(name, onOrientation);
        return () => {
            window.removeEventListener(name, onOrientation);
            last.current = null;
        };
    }, [active, allowed]);

    return { heading: active && allowed ? heading : null, request };
}
