"use client";

import { useEffect, useRef } from "react";
import { Bike, Car, ChevronDown, Footprints, X } from "lucide-react";

import type { TrafficLevel, TransportMode } from "../lib/api";

const MODES: { value: TransportMode; label: string; Icon: typeof Car }[] = [
    { value: "drive", label: "Drive", Icon: Car },
    { value: "bike", label: "Bike", Icon: Bike },
    { value: "walk", label: "Walk", Icon: Footprints },
];

const TRAFFIC: { value: TrafficLevel; label: string }[] = [
    { value: "low", label: "Clear" },
    { value: "normal", label: "Normal" },
    { value: "heavy", label: "Heavy" },
];

function minutesLabel(value: number): string {
    const rounded = Math.round(value * 10) / 10;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

interface Props {
    destinationName: string;
    onClear: () => void;
    transportMode: TransportMode;
    onModeChange: (mode: TransportMode) => void;
    trafficLevel: TrafficLevel;
    onTrafficChange: (level: TrafficLevel) => void;
    etas: Record<TransportMode, number | null>;
    routeMinutes: number | null;
    loading: boolean;
    inline: boolean;
    compact: boolean;
    onExpand: () => void;
    onHeightChange: (height: number) => void;
}

export default function TopBar({
    destinationName, onClear, transportMode, onModeChange,
    trafficLevel, onTrafficChange, etas, routeMinutes, loading, inline, compact,
    onExpand, onHeightChange,
}: Props) {
    const minutesFor = (mode: TransportMode) =>
        mode === transportMode && routeMinutes !== null ? routeMinutes : etas[mode];
    const barRef = useRef<HTMLDivElement>(null);
    const chosen = Boolean(destinationName);
    const driving = transportMode === "drive";

    useEffect(() => {
        const node = barRef.current;
        if (!node || typeof ResizeObserver === "undefined") {
            onHeightChange(0);
            return;
        }
        const observer = new ResizeObserver(([entry]) => {
            onHeightChange(entry.target.getBoundingClientRect().bottom);
        });
        observer.observe(node);
        return () => {
            observer.disconnect();
            onHeightChange(0);
        };
    }, [onHeightChange, chosen, driving]);

    if (!chosen) return null;

    if (compact) {
        const minutes = minutesFor(transportMode);
        const Active = MODES.find((mode) => mode.value === transportMode)?.Icon ?? Car;
        return (
            <div
                className="pointer-events-none absolute inset-x-0 top-0 z-[680] px-3"
                style={{ paddingTop: "calc(env(safe-area-inset-top) + 0.75rem)" }}
            >
                <button
                    onClick={onExpand}
                    aria-label="Show travel options"
                    className="pointer-events-auto flex items-center gap-2 rounded-full bg-white/95 py-2 pl-3 pr-2.5 shadow-[0_6px_20px_rgba(15,23,42,.2)] ring-1 ring-slate-900/5 backdrop-blur transition active:scale-95"
                >
                    <Active size={15} strokeWidth={2.2} className="text-slate-700" />
                    <span className="text-[12.5px] font-semibold tabular-nums text-slate-900">
                        {minutes === null || minutes === undefined
                            ? "\u2026"
                            : `${minutesLabel(minutes)} min`}
                    </span>
                    <ChevronDown size={14} className="text-slate-400" />
                </button>
            </div>
        );
    }

    return (
        <div
            className={inline
                ? "pointer-events-none relative z-[680] w-full px-4"
                : "pointer-events-none absolute inset-x-0 top-0 z-[680] px-3"}
            style={inline
                ? undefined
                : { paddingTop: "calc(env(safe-area-inset-top) + 0.75rem)" }}
        >
            <div ref={barRef} className="mx-auto w-full max-w-md lg:max-w-lg">
                <div className="pointer-events-auto rounded-[22px] bg-white p-1.5 shadow-[0_8px_30px_rgba(15,23,42,.22)] ring-1 ring-slate-900/5">
                    <div role="group" aria-label="Travel mode" className="flex items-stretch gap-1">
                        {MODES.map(({ value, label, Icon }) => {
                            const active = transportMode === value;
                            const minutes = minutesFor(value);
                            return (
                                <button
                                    key={value}
                                    onClick={() => onModeChange(value)}
                                    aria-pressed={active}
                                    aria-label={label}
                                    className={`flex flex-1 flex-col items-center gap-0.5 rounded-2xl px-1 py-2 transition active:scale-[.97] ${
                                        active ? "bg-slate-900 text-white" : "text-slate-500 hover:bg-slate-50"
                                    }`}
                                >
                                    <Icon size={17} strokeWidth={2.1} />
                                    <span className={`text-[11.5px] font-semibold tabular-nums ${
                                        active ? "text-white" : "text-slate-700"
                                    }`}>
                                        {minutes === null || minutes === undefined
                                            ? (loading ? "\u2026" : label)
                                            : `${minutesLabel(minutes)} min`}
                                    </span>
                                </button>
                            );
                        })}

                        <button
                            onClick={onClear}
                            aria-label="Clear destination"
                            className="ml-0.5 grid w-10 shrink-0 place-items-center rounded-2xl bg-slate-100 text-slate-500 transition active:scale-95"
                        >
                            <X size={15} />
                        </button>
                    </div>

                    {driving && (
                        <div
                            role="group"
                            aria-label="Traffic"
                            className="mt-1.5 flex gap-1 rounded-2xl bg-slate-100 p-1"
                        >
                            {TRAFFIC.map(({ value, label }) => (
                                <button
                                    key={value}
                                    onClick={() => onTrafficChange(value)}
                                    aria-pressed={trafficLevel === value}
                                    className={`flex-1 rounded-xl py-1.5 text-[11.5px] font-semibold transition active:scale-95 ${
                                        trafficLevel === value
                                            ? "bg-white text-slate-900 shadow-sm"
                                            : "text-slate-500"
                                    }`}
                                >
                                    {label}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
