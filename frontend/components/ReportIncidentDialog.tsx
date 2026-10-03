"use client";

import Link from "next/link";
import { useState } from "react";
import { AlertTriangle, Check, Loader2, MapPin, X } from "lucide-react";

import { errorMessage, type IncidentKind } from "../lib/api";
import { useIncidents, useReportIncident, useSession } from "../lib/queries";

interface Props {
    open: boolean;
    onClose: () => void;
    point: { lat: number; lon: number } | null;
    outside: boolean;
    locating: boolean;
    onRequestLocation: () => void;
}

export default function ReportIncidentDialog({
    open, onClose, point, outside, locating, onRequestLocation,
}: Props) {
    const session = useSession();
    const { data } = useIncidents();
    const report = useReportIncident();

    const [kind, setKind] = useState<IncidentKind | null>(null);
    const [note, setNote] = useState("");

    if (!open) return null;

    const signedIn = Boolean(session.data);
    const kinds = data?.kinds ?? [];
    const selected = kind ?? kinds[0]?.kind ?? null;
    const ttl = kinds.find((entry) => entry.kind === selected)?.ttl_hours;

    const submit = async () => {
        if (!point || !selected) return;
        try {
            await report.mutateAsync({
                kind: selected,
                lat: point.lat,
                lon: point.lon,
                note: note.trim(),
            });
        } catch {
        }
    };

    const result = report.data;

    return (
        <div className="fixed inset-0 z-[860] flex items-end justify-center bg-slate-900/50 p-4 backdrop-blur-sm sm:items-center">
            <div
                role="dialog"
                aria-modal="true"
                aria-label="Report an incident"
                className="w-full max-w-sm rounded-3xl bg-white p-5 shadow-2xl"
            >
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                        <span className="grid h-9 w-9 place-items-center rounded-xl bg-amber-50 text-amber-600">
                            <AlertTriangle size={17} />
                        </span>
                        <h2 className="text-[15px] font-semibold text-slate-900">
                            Report an incident
                        </h2>
                    </div>
                    <button
                        onClick={onClose}
                        aria-label="Close"
                        className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500"
                    >
                        <X size={15} />
                    </button>
                </div>

                {result ? (
                    <div className="mt-5">
                        <div className="flex items-center gap-2.5 rounded-2xl bg-emerald-50 p-4">
                            <Check size={18} className="shrink-0 text-emerald-600" />
                            <p className="text-[13px] font-medium text-emerald-900">
                                {result.counted
                                    ? result.corroborated
                                        ? "Thank you. Your report corroborates an existing one."
                                        : "Thank you. Your report is on the map."
                                    : "You had already reported this one."}
                            </p>
                        </div>
                        <dl className="mt-3 space-y-2 rounded-2xl bg-slate-50 p-4 text-[12.5px]">
                            <div className="flex items-center justify-between">
                                <dt className="text-slate-500">Status</dt>
                                <dd className="font-semibold text-slate-900">{result.status}</dd>
                            </div>
                            <div className="flex items-center justify-between">
                                <dt className="text-slate-500">Independent reports</dt>
                                <dd className="font-semibold tabular-nums text-slate-900">
                                    {result.reports}
                                </dd>
                            </div>
                        </dl>
                        <p className="mt-3 text-[11.5px] leading-relaxed text-slate-500">
                            It stays on the map until it expires, or sooner if security resolves it.
                            More independent reports raise its confidence.
                        </p>
                        <button
                            onClick={onClose}
                            className="mt-4 w-full rounded-2xl bg-slate-900 px-4 py-3 text-[13.5px] font-semibold text-white"
                        >
                            Done
                        </button>
                    </div>
                ) : !signedIn ? (
                    <div className="mt-5">
                        <p className="text-[13px] leading-relaxed text-slate-600">
                            Reporting needs an account, so every report is accountable and one
                            person cannot corroborate their own.
                        </p>
                        <p className="mt-2 text-[12px] leading-relaxed text-slate-500">
                            Calling 112 and sharing your location with security never need an
                            account.
                        </p>
                        <Link
                            href="/login"
                            className="mt-4 block w-full rounded-2xl bg-red-600 px-4 py-3 text-center text-[13.5px] font-semibold text-white"
                        >
                            Sign in to report
                        </Link>
                    </div>
                ) : (
                    <div className="mt-4">
                        {kinds.length === 0 ? (
                            <p className="rounded-2xl bg-slate-50 p-4 text-[12.5px] text-slate-500">
                                Incident types could not be loaded. Reporting needs a
                                connection.
                            </p>
                        ) : (
                            <div className="grid grid-cols-2 gap-2">
                                {kinds.map((entry) => (
                                    <button
                                        key={entry.kind}
                                        onClick={() => setKind(entry.kind)}
                                        className={`rounded-2xl px-3 py-3 text-[12.5px] font-medium transition active:scale-[.98] ${
                                            selected === entry.kind
                                                ? "bg-slate-900 text-white"
                                                : "bg-slate-50 text-slate-700 ring-1 ring-slate-200"
                                        }`}
                                    >
                                        {entry.label}
                                    </button>
                                ))}
                            </div>
                        )}

                        <textarea
                            value={note}
                            onChange={(event) => setNote(event.target.value)}
                            maxLength={280}
                            rows={2}
                            placeholder="Anything useful to add? (optional)"
                            className="mt-3 w-full resize-none rounded-2xl bg-slate-50 px-4 py-3 text-[16px] lg:text-[13.5px] text-slate-900 outline-none ring-1 ring-slate-200 transition focus:ring-2 focus:ring-red-500"
                        />

                        {point && (
                            <p className="mt-3 flex items-center gap-1.5 text-[11.5px] text-slate-500">
                                <MapPin size={12} className="shrink-0" />
                                {point.lat.toFixed(5)}, {point.lon.toFixed(5)}
                                {ttl ? ` · expires in ${ttl}h unless corroborated` : ""}
                            </p>
                        )}

                        {!point && outside && (
                            <p role="alert" className="mt-3 flex items-start gap-2 rounded-2xl bg-amber-50 px-3.5 py-3 text-[12px] text-amber-900">
                                <AlertTriangle size={14} className="mt-px shrink-0" />
                                You are outside the KNUST area, so you cannot report from
                                here. Reports must come from the scene. If this is on
                                campus, report it when you get there — or call 112 now.
                            </p>
                        )}

                        {!point && !outside && (
                            <button
                                onClick={onRequestLocation}
                                disabled={locating}
                                className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-50 px-4 py-3 text-[12.5px] font-medium text-slate-700 ring-1 ring-slate-200 disabled:opacity-60"
                            >
                                {locating
                                    ? <><Loader2 size={13} className="animate-spin" /> Finding you…</>
                                    : <><MapPin size={13} /> Use my current location</>}
                            </button>
                        )}

                        <button
                            onClick={submit}
                            disabled={report.isPending || !point || !selected}
                            className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl bg-red-600 px-4 py-3.5 text-[14px] font-semibold text-white transition active:scale-[.98] disabled:opacity-50"
                        >
                            {report.isPending && <Loader2 size={15} className="animate-spin" />}
                            {report.isPending ? "Sending..." : "Submit report"}
                        </button>

                        {report.isError && (
                            <p className="mt-2 text-[12.5px] text-red-600">
                                {errorMessage(report.error, "Could not send the report.")}
                            </p>
                        )}

                        <p className="mt-3 text-[11px] leading-relaxed text-slate-400">
                            False reports lower the weight of everything you report afterwards.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
