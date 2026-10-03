"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
    ArrowLeft,
    BadgeCheck,
    Check,
    Loader2,
    MapPin,
    ShieldAlert,
    ThumbsDown,
    TriangleAlert,
} from "lucide-react";

import { errorMessage, type Incident } from "../../lib/api";
import {
    useIncidentQueue,
    useOverrideIncident,
    useResolveIncident,
    useSession,
} from "../../lib/queries";
import RoleGate from "../../components/RoleGate";
import { can } from "../../lib/roles";

type Filter = "open" | "all";

const STATUS_STYLE: Record<string, string> = {
    confirmed: "bg-red-100 text-red-700",
    verified: "bg-red-100 text-red-700",
    likely: "bg-orange-100 text-orange-700",
    unverified: "bg-amber-50 text-amber-700",
    false: "bg-slate-100 text-slate-500",
};

export default function SecurityPage() {
    return (
        <RoleGate required="security">
            <SecurityQueue />
        </RoleGate>
    );
}

function SecurityQueue() {
    const session = useSession();
    const allowed = can(session.data?.roles, "resolve_incidents");
    const queue = useIncidentQueue(allowed);
    const override = useOverrideIncident();
    const resolve = useResolveIncident();
    const [filter, setFilter] = useState<Filter>("open");

    const rows = useMemo(() => {
        const all = (queue.data ?? []) as (Incident & { live: boolean })[];
        const sorted = [...all].sort((a, b) =>
            Number(b.live) - Number(a.live) || b.confidence - a.confidence);
        return filter === "open" ? sorted.filter((row) => row.live) : sorted;
    }, [queue.data, filter]);

    const openCount = ((queue.data ?? []) as (Incident & { live: boolean })[])
        .filter((row) => row.live).length;
    const busy = override.isPending || resolve.isPending;
    const failure = override.error ?? resolve.error;

    return (
        <main
            className="mx-auto w-full max-w-3xl px-5 py-8"
            style={{ paddingTop: "var(--acting-offset, 0px)" }}
        >
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="flex items-center gap-2 text-[22px] font-semibold tracking-tight text-slate-900">
                        <ShieldAlert size={20} className="text-red-600" />
                        Incident queue
                    </h1>
                    <p className="mt-0.5 text-[12.5px] text-slate-500">
                        {openCount} open {openCount === 1 ? "report" : "reports"}
                        {session.data ? ` · ${session.data.email}` : ""}
                    </p>
                </div>
                <Link href="/" className="flex items-center gap-1.5 text-[13px] font-medium text-slate-500">
                    <ArrowLeft size={14} /> Map
                </Link>
            </div>

            <div role="group" aria-label="Filter" className="mt-5 flex gap-2">
                {(["open", "all"] as Filter[]).map((value) => (
                    <button
                        key={value}
                        onClick={() => setFilter(value)}
                        aria-pressed={filter === value}
                        className={`rounded-full px-4 py-2 text-[12.5px] font-semibold capitalize transition ${
                            filter === value
                                ? "bg-slate-900 text-white"
                                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                        }`}
                    >
                        {value === "open" ? "Open" : "Everything"}
                    </button>
                ))}
            </div>

            {queue.isPending && (
                <p className="mt-6 flex items-center gap-2 text-[13px] text-slate-500">
                    <Loader2 size={15} className="animate-spin" /> Loading the queue…
                </p>
            )}

            {queue.isError && (
                <p role="alert" className="mt-6 rounded-2xl bg-red-50 px-4 py-3 text-[12.5px] text-red-700">
                    {errorMessage(queue.error, "Could not load the queue.")}
                </p>
            )}

            {failure && (
                <p role="alert" className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-[12.5px] text-red-700">
                    {errorMessage(failure, "That action did not go through.")}
                </p>
            )}

            {queue.isSuccess && rows.length === 0 && (
                <p className="mt-6 rounded-3xl bg-white px-5 py-8 text-center text-[13px] text-slate-500 ring-1 ring-slate-200">
                    {filter === "open"
                        ? "Nothing open. Reports appear here the moment someone sends one."
                        : "No reports have ever been sent."}
                </p>
            )}

            <ul className="mt-4 space-y-3">
                {rows.map((incident) => {
                    const acting = (override.isPending && override.variables?.id === incident.id)
                        || (resolve.isPending && resolve.variables === incident.id);
                    const settled = incident.status === "verified" || incident.status === "false";
                    return (
                        <li
                            key={incident.id}
                            className={`rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200 ${
                                incident.live ? "" : "opacity-60"
                            }`}
                        >
                            <div className="flex flex-wrap items-start justify-between gap-2">
                                <div className="min-w-0">
                                    <p className="flex items-center gap-2 text-[14.5px] font-semibold text-slate-900">
                                        <TriangleAlert size={15} className="shrink-0 text-amber-600" />
                                        {incident.label}
                                    </p>
                                    <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px] text-slate-500">
                                        <span className={`rounded-full px-2 py-0.5 font-semibold capitalize ${
                                            STATUS_STYLE[incident.status] ?? "bg-slate-100 text-slate-600"
                                        }`}>
                                            {incident.status}
                                        </span>
                                        <span>{Math.round(incident.confidence * 100)}% confidence</span>
                                        <span>·</span>
                                        <span>{incident.reports} {incident.reports === 1 ? "report" : "reports"}</span>
                                        <span>·</span>
                                        <span>
                                            {incident.live
                                                ? `${incident.expires_in_minutes} min left`
                                                : "closed"}
                                        </span>
                                    </p>
                                </div>
                                <a
                                    href={`/?lat=${incident.lat}&lon=${incident.lon}`}
                                    className="flex shrink-0 items-center gap-1.5 rounded-xl bg-slate-50 px-3 py-2 text-[11.5px] font-medium text-slate-600 ring-1 ring-slate-200"
                                >
                                    <MapPin size={12} />
                                    {incident.lat.toFixed(4)}, {incident.lon.toFixed(4)}
                                </a>
                            </div>

                            {incident.live && !settled && (
                                <div className="mt-3 flex flex-wrap gap-2">
                                    <button
                                        onClick={() => override.mutate({ id: incident.id, override: "verified" })}
                                        disabled={busy}
                                        className="flex items-center gap-1.5 rounded-xl bg-red-600 px-3.5 py-2 text-[12.5px] font-semibold text-white transition active:scale-95 disabled:opacity-50"
                                    >
                                        {acting && override.variables?.override === "verified"
                                            ? <Loader2 size={13} className="animate-spin" />
                                            : <BadgeCheck size={13} />}
                                        Verify
                                    </button>
                                    <button
                                        onClick={() => override.mutate({ id: incident.id, override: "false" })}
                                        disabled={busy}
                                        className="flex items-center gap-1.5 rounded-xl bg-slate-100 px-3.5 py-2 text-[12.5px] font-semibold text-slate-700 transition active:scale-95 disabled:opacity-50"
                                    >
                                        {acting && override.variables?.override === "false"
                                            ? <Loader2 size={13} className="animate-spin" />
                                            : <ThumbsDown size={13} />}
                                        Mark false
                                    </button>
                                    <button
                                        onClick={() => resolve.mutate(incident.id)}
                                        disabled={busy}
                                        className="flex items-center gap-1.5 rounded-xl bg-slate-100 px-3.5 py-2 text-[12.5px] font-semibold text-slate-700 transition active:scale-95 disabled:opacity-50"
                                    >
                                        <Check size={13} /> Dealt with
                                    </button>
                                </div>
                            )}

                            {settled && (
                                <p className="mt-2 text-[11.5px] text-slate-500">
                                    {incident.status === "false"
                                        ? "Marked false. Every reporter's weight was halved."
                                        : "Verified by security."}
                                </p>
                            )}
                        </li>
                    );
                })}
            </ul>

            <p className="mt-6 text-[11.5px] leading-relaxed text-slate-400">
                Marking a report false permanently halves the weight of everyone who sent
                it, so use it for pranks rather than honest mistakes. &ldquo;Dealt
                with&rdquo; just closes it.
            </p>
        </main>
    );
}
