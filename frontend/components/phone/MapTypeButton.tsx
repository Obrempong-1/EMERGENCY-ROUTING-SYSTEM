"use client";

import { useEffect, useState } from "react";
import type L from "leaflet";

interface MapTypeButtonProps {
    map: L.Map | null;
    label: string;
    tileUrl: string;
    maxNativeZoom: number;
    onToggle: () => void;
}

function tileFor(url: string, lat: number, lon: number, zoom: number): string {
    const scale = 2 ** zoom;
    const x = Math.floor(((lon + 180) / 360) * scale);
    const radians = (lat * Math.PI) / 180;
    const y = Math.floor(
        ((1 - Math.log(Math.tan(radians) + 1 / Math.cos(radians)) / Math.PI) / 2) * scale,
    );
    const clamp = (value: number) => Math.min(Math.max(value, 0), scale - 1);
    return url
        .replace("{s}", "a")
        .replace("{z}", String(zoom))
        .replace("{x}", String(clamp(x)))
        .replace("{y}", String(clamp(y)));
}

export default function MapTypeButton({
    map, label, tileUrl, maxNativeZoom, onToggle,
}: MapTypeButtonProps) {
    const [preview, setPreview] = useState<string | null>(null);

    useEffect(() => {
        if (!map) return;
        const update = () => {
            const centre = map.getCenter();
            const zoom = Math.min(Math.round(map.getZoom()), maxNativeZoom);
            setPreview(tileFor(tileUrl, centre.lat, centre.lng, zoom));
        };
        update();
        map.on("moveend", update);
        map.on("zoomend", update);
        return () => {
            map.off("moveend", update);
            map.off("zoomend", update);
        };
    }, [map, tileUrl, maxNativeZoom]);

    return (
        <button
            onClick={onToggle}
            aria-label={`Switch to ${label.toLowerCase()} view`}
            className="relative block h-[4.5rem] w-[4.5rem] overflow-hidden rounded-2xl bg-slate-200 shadow-[0_6px_20px_rgba(15,23,42,.3)] ring-1 ring-black/10 transition active:scale-95 lg:hidden"
        >
            {preview && (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                    src={preview}
                    alt=""
                    width={72}
                    height={72}
                    className="absolute inset-0 h-full w-full object-cover"
                />
            )}
            <span className="absolute inset-x-0 bottom-0 bg-slate-900/75 py-1 text-center text-[11px] font-semibold leading-none text-white backdrop-blur-sm">
                {label}
            </span>
        </button>
    );
}
