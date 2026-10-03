"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowLeft, ChevronRight, Crown, Eye, Loader2, Search, ShieldAlert, Trash2 } from "lucide-react";

import { errorMessage, setActingRole, type Role } from "../../lib/api";
import RoleGate from "../../components/RoleGate";
import { ROLE_HELP } from "../../lib/roles";
import {
    useAdminStudents,
    useDeletePlace,
    useLocations,
    useSession,
    useSetRoles,
} from "../../lib/queries";

const ROLES: Role[] = ["student", "security", "mapper", "admin"];

export default function AdminPage() {
    return (
        <RoleGate required="admin">
            <AdminTools />
        </RoleGate>
    );
}

function AdminTools() {
    const session = useSession();
    const [search, setSearch] = useState("");

    const me = session.data;
    const viewing = me?.real_role && me.real_role !== me.role ? me.role : null;
    const effective = me?.role;
    const isAdmin = effective === "admin";

    const students = useAdminStudents(isAdmin);
    const locations = useLocations();
    const setRoles = useSetRoles();
    const deletePlace = useDeletePlace();

    const curated = (locations.data ?? []).filter((p) => p.id.startsWith("curated/"));

    const accounts = useMemo(() => {
        const needle = search.trim().toLowerCase();
        const all = students.data ?? [];
        return needle ? all.filter((student) => student.email.includes(needle)) : all;
    }, [students.data, search]);

    const act = (role: Role | null) => {
        setActingRole(role === "admin" ? null : role);
        session.refetch();
    };

    return (
        <main className="mx-auto w-full max-w-4xl px-5 py-8" style={{ paddingTop: "var(--acting-offset, 0px)" }}>
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="text-[22px] font-semibold tracking-tight text-slate-900">
                        Administration
                    </h1>
                    <p className="mt-0.5 text-[12.5px] text-slate-500">{me?.email}</p>
                </div>
                <Link href="/" className="flex items-center gap-1.5 text-[13px] font-medium text-slate-500">
                    <ArrowLeft size={14} /> Map
                </Link>
            </div>

            <section className="mt-6 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
                <h2 className="flex items-center gap-2 text-[14px] font-semibold text-slate-900">
                    <Eye size={15} /> View the app as
                </h2>
                <p className="mt-1 text-[12px] leading-relaxed text-slate-500">
                    Acting as a role only ever reduces what you can do. Everything you
                    change is still recorded against your own account.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                    {[null, ...ROLES].map((role) => (
                        <button
                            key={role ?? "self"}
                            onClick={() => act(role)}
                            className={`rounded-full px-4 py-2 text-[12.5px] font-semibold transition ${
                                viewing === role
                                    ? "bg-slate-900 text-white"
                                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                            }`}
                        >
                            {role ? role : "myself (admin)"}
                        </button>
                    ))}
                </div>
            </section>

            {viewing === null && (
                <>
                    <section className="mt-5 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <h2 className="text-[14px] font-semibold text-slate-900">
                                Accounts ({(students.data ?? []).length})
                            </h2>
                            <label className="relative w-full sm:w-64">
                                <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                <input
                                    type="search"
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                    placeholder="Search by email"
                                    aria-label="Search accounts by email"
                                    className="w-full rounded-xl bg-slate-50 py-2 pl-8 pr-3 text-[16px] lg:text-[12.5px] text-slate-800 outline-none ring-1 ring-slate-200 focus:ring-2 focus:ring-blue-500/40"
                                />
                            </label>
                        </div>
                        <ul className="mt-3 grid gap-x-4 gap-y-1 text-[11.5px] text-slate-500 sm:grid-cols-3">
                            {ROLES.map((role) => (
                                <li key={role}>
                                    <span className="font-semibold capitalize text-slate-700">{role}</span>: {ROLE_HELP[role]}
                                </li>
                            ))}
                        </ul>
                        {students.isError && (
                            <p className="mt-2 text-[12.5px] text-red-600">
                                {errorMessage(students.error, "Could not load accounts.")}
                            </p>
                        )}
                        <p className="mt-3 text-[11.5px] text-slate-400">
                            People appear here after they sign in for the first time.
                        </p>
                        <ul className="mt-1 divide-y divide-slate-100">
                            {accounts.map((student) => {
                                const isMe = student.id === me?.id;
                                const locked = student.owner || isMe;
                                const saving = setRoles.isPending && setRoles.variables?.id === student.id;
                                return (
                                    <li key={student.id} className="flex flex-wrap items-center gap-3 py-3">
                                        <span className="min-w-0 flex-1">
                                            <span className="flex items-center gap-2">
                                                <span className="truncate text-[13.5px] font-medium text-slate-900">
                                                    {student.email}
                                                </span>
                                                {student.owner && (
                                                    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10.5px] font-semibold text-amber-700">
                                                        <Crown size={11} /> Owner
                                                    </span>
                                                )}
                                                {isMe && !student.owner && (
                                                    <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10.5px] font-semibold text-slate-500">
                                                        You
                                                    </span>
                                                )}
                                            </span>
                                            <span className="text-[11.5px] text-slate-500">
                                                weight {student.trust.toFixed(2)}
                                                {student.knust_verified ? " · KNUST verified" : ""}
                                            </span>
                                        </span>
                                        {saving && <Loader2 size={14} className="animate-spin text-slate-400" />}
                                        <div
                                            role="group"
                                            aria-label={`Roles for ${student.email}`}
                                            title={student.owner
                                                ? "Owner accounts always stay admin"
                                                : isMe ? "Ask another admin to change your own roles" : undefined}
                                            className="flex flex-wrap gap-1.5"
                                        >
                                            {ROLES.map((role) => {
                                                const held = (student.roles ?? [student.role]).includes(role);
                                                const fixed = role === "student";
                                                return (
                                                    <button
                                                        key={role}
                                                        type="button"
                                                        aria-pressed={held}
                                                        disabled={locked || saving || fixed}
                                                        onClick={() => {
                                                            const current = new Set(student.roles ?? [student.role]);
                                                            if (held) current.delete(role);
                                                            else current.add(role);
                                                            current.add("student");
                                                            setRoles.mutate({
                                                                id: student.id,
                                                                roles: ROLES.filter((r) => current.has(r)),
                                                            });
                                                        }}
                                                        className={`rounded-full px-3 py-1.5 text-[11.5px] font-semibold capitalize transition disabled:cursor-not-allowed disabled:opacity-50 ${
                                                            held
                                                                ? "bg-slate-900 text-white"
                                                                : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                                                        }`}
                                                    >
                                                        {role}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </li>
                                );
                            })}
                        </ul>
                        {students.isSuccess && accounts.length === 0 && (
                            <p className="py-3 text-[12.5px] text-slate-500">
                                {search ? "No account matches that email." : "No accounts yet."}
                            </p>
                        )}
                        {setRoles.isError && (
                            <p className="mt-2 text-[12.5px] text-red-600">
                                {errorMessage(setRoles.error, "Could not change that role.")}
                            </p>
                        )}
                    </section>

                    <section className="mt-5 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
                        <h2 className="text-[14px] font-semibold text-slate-900">
                            Added places ({curated.length})
                        </h2>
                        {curated.length === 0 && (
                            <p className="mt-2 text-[12.5px] text-slate-500">
                                Nothing has been added to the map yet.
                            </p>
                        )}
                        <ul className="mt-3 divide-y divide-slate-100">
                            {curated.map((place) => (
                                <li key={place.id} className="flex items-center gap-3 py-3">
                                    <span className="min-w-0 flex-1">
                                        <span className="block truncate text-[13.5px] font-medium text-slate-900">
                                            {place.name}
                                        </span>
                                        <span className="text-[11.5px] text-slate-500">
                                            {place.category} · {place.lat.toFixed(5)}, {place.lon.toFixed(5)}
                                        </span>
                                    </span>
                                    <button
                                        onClick={() => deletePlace.mutate(place.id)}
                                        aria-label={`Remove ${place.name}`}
                                        className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-red-50 text-red-600 transition hover:bg-red-100"
                                    >
                                        <Trash2 size={15} />
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </section>

                    <Link
                        href="/security"
                        className="mt-5 flex items-center gap-3 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200 transition hover:ring-slate-300"
                    >
                        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-red-50 text-red-600">
                            <ShieldAlert size={17} />
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="block text-[14px] font-semibold text-slate-900">
                                Incident queue
                            </span>
                            <span className="block text-[12px] text-slate-500">
                                Verify, dismiss and close reports
                            </span>
                        </span>
                        <ChevronRight size={16} className="shrink-0 text-slate-400" />
                    </Link>
                </>
            )}
        </main>
    );
}
