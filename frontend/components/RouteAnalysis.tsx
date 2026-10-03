"use client";

import { useState } from "react";
import {
    ArrowUp,
    ArrowUpLeft,
    ArrowUpRight,
    ChevronDown,
    Clock,
    CornerUpLeft,
    CornerUpRight,
    Flag,
    Navigation,
    RefreshCw,
    RotateCcw,
    Route,
    TriangleAlert,
    Volume2,
    VolumeX,
    type LucideIcon,
} from "lucide-react";

import type { RouteResponse, RouteStep, TrafficLevel, TransportMode } from "../lib/api";
import { useVoiceGuidance } from "../lib/useVoiceGuidance";

const MODE_LABEL: Record<TransportMode, string> = {
    drive: "Driving",
    walk: "Walking",
    bike: "Cycling",
};

const TRAFFIC_NOTE: Record<TrafficLevel, string> = {
    low: "timed for a clear network.",
    normal: "timed for normal traffic.",
    heavy: "timed for heavy traffic, avoiding busy roads where a quicker way exists.",
};

const MANOEUVRE: Record<string, LucideIcon> = {
    depart: Navigation,
    continue: ArrowUp,
    straight: ArrowUp,
    "turn-left": CornerUpLeft,
    "turn-right": CornerUpRight,
    "slight-left": ArrowUpLeft,
    "slight-right": ArrowUpRight,
    "sharp-left": CornerUpLeft,
    "sharp-right": CornerUpRight,
    uturn: RotateCcw,
    roundabout: RefreshCw,
    arrive: Flag,
};

const NEAR_M = 40;

function actionOf(step: RouteStep | undefined): string {
    if (!step) return "";
    return step.text.replace(/\s+for\s+[\d.]+\s*k?m$/i, "");
}

function distanceLabel(metres: number): string {
    if (metres >= 1000) return `${(metres / 1000).toFixed(1)} km`;
    return `${Math.max(0, Math.round(metres / 10) * 10)} m`;
}

function spokenDistance(metres: number): string {
    if (metres >= 1000) {
        const km = (metres / 1000).toFixed(1);
        return `${km} kilometre${km === "1.0" ? "" : "s"}`;
    }
    return `${Math.max(10, Math.round(metres / 10) * 10)} metres`;
}

interface RouteAnalysisProps {
    route: RouteResponse | null;
    transportMode: TransportMode;
    trafficLevel: TrafficLevel;
    navigating: boolean;
    top: number;
    maxHeight: string;
}

export default function RouteAnalysis({
    route, transportMode, trafficLevel, navigating, top, maxHeight,
}: RouteAnalysisProps) {
    const [open, setOpen] = useState(false);

    const steps = route?.instructions ?? [];
    const arriving = steps.length <= 1;
    const next = arriving ? steps[0] : steps[1];
    const toNext = arriving ? 0 : (steps[0]?.distance_m ?? 0);
    const action = actionOf(next);
    const near = toNext <= NEAR_M;
    const phrase = !action
        ? ""
        : next?.kind === "arrive" || near
            ? action
            : `In ${spokenDistance(toNext)}, ${action.charAt(0).toLowerCase()}${action.slice(1)}`;

    const voice = useVoiceGuidance(phrase, navigating && Boolean(route));

    if (!route) return null;

    const congested = transportMode === "drive" && trafficLevel === "heavy";
    const hazards = route.hazards ?? [];
    const Icon = MANOEUVRE[next?.kind ?? "continue"] ?? ArrowUp;

    return (
        <div
            className="pointer-events-none absolute inset-x-0 z-[660] px-3 lg:px-4"
            style={{ top }}
        >
            <div className="pointer-events-auto mx-auto w-full max-w-md overflow-hidden rounded-2xl bg-white/95 shadow-[0_8px_30px_rgba(15,23,42,.18)] ring-1 ring-slate-900/5 backdrop-blur lg:max-w-lg">
                <div className="flex items-center gap-2.5 px-3 py-2.5">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-slate-900 text-white">
                        <Icon size={20} strokeWidth={2.2} />
                    </span>

                    <button
                        onClick={() => setOpen((value) => !value)}
                        aria-expanded={open}
                        className="min-w-0 flex-1 text-left"
                    >
                        {action ? (
                            <>
                                {next?.kind !== "arrive" && (
                                    <span className="block text-[10.5px] font-semibold uppercase tracking-[0.1em] text-slate-400">
                                        {near ? "Now" : `In ${distanceLabel(toNext)}`}
                                    </span>
                                )}
                                <span className="block truncate text-[14px] font-semibold leading-tight text-slate-900">
                                    {action}
                                </span>
                            </>
                        ) : (
                            <span className="block text-[13.5px] font-semibold text-slate-900">
                                {route.distance_km} km
                            </span>
                        )}
                        <span className="mt-0.5 block truncate text-[11px] text-slate-400">
                            {route.distance_km} km · {steps.length}{" "}
                            {steps.length === 1 ? "step" : "steps"}
                            {congested ? " · heavy traffic" : ""}
                        </span>
                    </button>

                    {voice.supported && (
                        <button
                            onClick={voice.toggle}
                            aria-pressed={voice.enabled}
                            aria-label={voice.enabled
                                ? "Turn off voice directions"
                                : "Turn on voice directions"}
                            className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl transition active:scale-95 ${
                                voice.enabled
                                    ? "bg-slate-900 text-white"
                                    : "bg-slate-100 text-slate-500"
                            }`}
                        >
                            {voice.enabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
                        </button>
                    )}

                    <button
                        onClick={() => setOpen((value) => !value)}
                        aria-expanded={open}
                        aria-label={open ? "Hide route detail" : "Show route detail"}
                        className="grid h-9 w-6 shrink-0 place-items-center text-slate-400"
                    >
                        <ChevronDown
                            size={16}
                            className={`transition-transform ${open ? "rotate-180" : ""}`}
                        />
                    </button>
                </div>

                {hazards.length > 0 && (
                    <p role="alert" className="mx-3 mb-3 flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2.5 text-[11.5px] text-amber-900">
                        <TriangleAlert size={14} className="mt-px shrink-0" />
                        <span>
                            <span className="font-semibold">No clear way around: </span>
                            this route passes a reported{" "}
                            {hazards.map((hazard) => hazard.label.toLowerCase()).join(" and ")}.
                            Take care there.
                        </span>
                    </p>
                )}

                {open && (
                    <div className="border-t border-slate-100">
                        <div className="grid grid-cols-2 gap-2 p-3">
                            <div className="rounded-xl bg-slate-50 p-3">
                                <span className="grid h-7 w-7 place-items-center rounded-lg bg-white text-blue-600 shadow-sm">
                                    <Route size={14} />
                                </span>
                                <p className="mt-2 text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
                                    Distance
                                </p>
                                <p className="mt-0.5 flex items-baseline gap-1">
                                    <span className="text-xl font-semibold tracking-tight text-slate-900">
                                        {route.distance_km}
                                    </span>
                                    <span className="text-[10.5px] font-medium text-slate-400">km</span>
                                </p>
                            </div>

                            <div className="rounded-xl bg-slate-50 p-3">
                                <span className="grid h-7 w-7 place-items-center rounded-lg bg-white text-emerald-600 shadow-sm">
                                    <Clock size={14} />
                                </span>
                                <p className="mt-2 text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
                                    Response
                                </p>
                                <p className="mt-0.5 flex items-baseline gap-1">
                                    <span className="text-xl font-semibold tracking-tight text-slate-900">
                                        {route.time_min}
                                    </span>
                                    <span className="text-[10.5px] font-medium text-slate-400">min</span>
                                </p>
                            </div>
                        </div>

                        <p className={`mx-3 flex items-start gap-2 rounded-xl px-3 py-2.5 text-[11.5px] ${
                            congested ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"
                        }`}>
                            {congested
                                ? <TriangleAlert size={14} className="mt-px shrink-0" />
                                : <Route size={14} className="mt-px shrink-0" />}
                            <span>
                                <span className="font-semibold">{MODE_LABEL[transportMode]}</span>
                                {transportMode === "drive"
                                    ? ` route ${TRAFFIC_NOTE[trafficLevel]}`
                                    : " route. Traffic does not affect this mode."}
                            </span>
                        </p>

                        {steps.length > 0 && (
                            <ol
                                className="custom-scrollbar mt-2 divide-y divide-slate-50 overflow-y-auto overscroll-contain border-t border-slate-100"
                                style={{ maxHeight }}
                            >
                                {steps.map((step: RouteStep, index: number) => (
                                    <li key={index} className="flex gap-3 px-4 py-2.5">
                                        <span className="mt-px text-[10.5px] font-semibold tabular-nums text-slate-300">
                                            {String(index + 1).padStart(2, "0")}
                                        </span>
                                        <span className="text-[12.5px] leading-snug text-slate-700">
                                            {step.text}
                                        </span>
                                    </li>
                                ))}
                            </ol>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
