"use client";

import { useSyncExternalStore } from "react";

const DESKTOP = "(min-width: 1024px)";

function subscribe(onChange: () => void): () => void {
    if (typeof window === "undefined" || !window.matchMedia) return () => {};
    const query = window.matchMedia(DESKTOP);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
}

function isDesktop(): boolean {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia(DESKTOP).matches;
}

export function useIsDesktop(): boolean {
    return useSyncExternalStore(subscribe, isDesktop, () => false);
}
