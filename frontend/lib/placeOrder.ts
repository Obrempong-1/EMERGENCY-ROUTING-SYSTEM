import type { MapMarker } from "./api";

export function campusFirst<T extends MapMarker>(places: T[]): T[] {
    return [...places].sort((a, b) => {
        const left = a.on_campus ? 0 : 1;
        const right = b.on_campus ? 0 : 1;
        if (left !== right) return left - right;
        return a.name.localeCompare(b.name);
    });
}

export function groupLabel(place: MapMarker): string {
    return place.on_campus ? "On campus" : "Nearby";
}
