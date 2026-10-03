"use client";

import { useState } from 'react';
import { Radar } from 'lucide-react';

import type { CoverageResponse, TransportMode } from '@/lib/api';
import { COVERAGE_SCOPES, coverageColor, type CoverageScope } from './coverage';

const TRAVEL: { value: TransportMode; label: string }[] = [
    { value: 'drive', label: 'Drive' },
    { value: 'bike', label: 'Bike' },
    { value: 'walk', label: 'Walk' },
];

interface CoverageKeyProps {
    coverage: CoverageResponse | null;
    loading: boolean;
    scope: CoverageScope;
    onScopeChange: (scope: CoverageScope) => void;
    mode: TransportMode;
    onModeChange: (mode: TransportMode) => void;
}

export default function CoverageKey({
    coverage, loading, scope, onScopeChange, mode, onModeChange,
}: CoverageKeyProps) {
    const [shown, setShown] = useState(coverage);
    if (coverage && coverage !== shown) setShown(coverage);

    const visible = coverage !== null;
    if (!shown) return null;

    const bands = shown.bands.filter((band) => band.lines.length > 0);
    const facilities = shown.facility_count;

    return (
        <div
            inert={!visible}
            aria-hidden={!visible}
            className={`relative w-[13.5rem] origin-bottom-left rounded-2xl bg-white/85 p-3 shadow-[0_12px_40px_-12px_rgba(15,23,42,0.45)] ring-1 ring-black/5 backdrop-blur-xl motion-safe:transition-all motion-safe:duration-300 motion-safe:ease-out lg:absolute lg:bottom-0 lg:left-0 lg:w-[15.5rem] lg:p-3.5 ${
                visible ? 'translate-y-0 scale-100 opacity-100' : 'pointer-events-none translate-y-2 scale-95 opacity-0'
            }`}
        >
            <div className="flex items-center gap-2">
                <span className="grid h-6 w-6 place-items-center rounded-full bg-slate-900 text-white">
                    <Radar size={12} className={loading ? 'motion-safe:animate-spin' : ''} />
                </span>
                <p className="text-[12px] font-semibold text-slate-900 lg:text-[12.5px]">
                    Response time
                </p>
                {loading && (
                    <span className="ml-auto text-[10px] font-medium text-slate-400">Updating…</span>
                )}
            </div>

            <div role="group" aria-label="Coverage for" className="mt-2 grid grid-cols-4 rounded-full bg-slate-900/[0.06] p-0.5 lg:mt-3">
                {COVERAGE_SCOPES.map((option) => {
                    const selected = scope === option.key;
                    return (
                        <button
                            key={option.key}
                            type="button"
                            onClick={() => onScopeChange(option.key)}
                            aria-pressed={selected}
                            className={`rounded-full py-1 text-[10.5px] font-semibold motion-safe:transition ${
                                selected
                                    ? 'bg-white text-slate-900 shadow-sm ring-1 ring-black/5'
                                    : 'text-slate-500 hover:text-slate-800'
                            }`}
                        >
                            {option.label}
                        </button>
                    );
                })}
            </div>

            <div role="group" aria-label="Responder travels by"
                 className="mt-1.5 grid grid-cols-3 rounded-full bg-slate-900/[0.06] p-0.5">
                {TRAVEL.map((option) => {
                    const selected = mode === option.value;
                    return (
                        <button
                            key={option.value}
                            type="button"
                            onClick={() => onModeChange(option.value)}
                            aria-pressed={selected}
                            className={`rounded-full py-1 text-[10.5px] font-semibold motion-safe:transition ${
                                selected
                                    ? 'bg-white text-slate-900 shadow-sm ring-1 ring-black/5'
                                    : 'text-slate-500 hover:text-slate-800'
                            }`}
                        >
                            {option.label}
                        </button>
                    );
                })}
            </div>

            <p className="mt-2 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-slate-400 lg:mt-3">
                Help gets here in
            </p>
            <ul className={`mt-1.5 grid grid-cols-2 gap-x-2 gap-y-1 lg:grid-cols-1 lg:gap-y-1.5 ${
                loading ? 'opacity-50' : ''
            } motion-safe:transition-opacity`}>
                {bands.map((band) => (
                    <li key={band.index} className="flex items-center gap-1.5 lg:gap-2.5">
                        <span className="h-1.5 w-4 shrink-0 rounded-full lg:w-7"
                              style={{ background: coverageColor(band.index) }} />
                        <span className="truncate text-[10px] font-medium text-slate-600 lg:text-[11px]">
                            {band.label}
                        </span>
                    </li>
                ))}
            </ul>

            <p className="mt-3 hidden border-t border-slate-900/[0.06] pt-2 text-[10px] text-slate-400 lg:block">
                From {facilities} {facilities === 1 ? 'facility' : 'facilities'}
            </p>
        </div>
    );
}
