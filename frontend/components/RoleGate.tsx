"use client";

import Link from "next/link";
import { ArrowLeft, Eye, Loader2, ShieldAlert } from "lucide-react";

import type { Role } from "../lib/api";
import { setActingRole } from "../lib/api";
import { useSession } from "../lib/queries";
import { holdsRole } from "../lib/roles";
import RoleAbilities from "./RoleAbilities";
import SignInForm from "./SignInForm";

const NEEDED: Record<Role, string> = {
    student: "an account",
    security: "a campus security account",
    mapper: "a mapper account",
    admin: "an administrator account",
};

interface RoleGateProps {
    required: Role;
    children: React.ReactNode;
}

export default function RoleGate({ required, children }: RoleGateProps) {
    const session = useSession();

    if (session.isLoading) {
        return (
            <main className="grid min-h-[100dvh] place-items-center">
                <Loader2 className="animate-spin text-slate-400" />
            </main>
        );
    }

    const me = session.data;
    if (holdsRole(me?.roles, required)) return <>{children}</>;

    const blockedByActing = Boolean(me?.real_roles)
        && holdsRole(me?.real_roles, required);

    if (blockedByActing && me) {
        const stop = () => {
            setActingRole(null);
            session.refetch();
        };
        return (
            <main
                className="mx-auto flex min-h-[100dvh] w-full max-w-md flex-col justify-center px-5 py-10"
                style={{ paddingTop: "var(--acting-offset, 0px)" }}
            >
                <div className="rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
                    <span className="grid h-11 w-11 place-items-center rounded-2xl bg-amber-50 text-amber-600">
                        <Eye size={20} />
                    </span>
                    <h1 className="mt-4 text-[20px] font-semibold tracking-tight text-slate-900">
                        You are viewing as <span className="capitalize">{me.role}</span>
                    </h1>
                    <p className="mt-1.5 text-[13px] leading-relaxed text-slate-500">
                        This page needs {NEEDED[required]}, and a {me.role} does not have
                        one. A <span className="capitalize">{me.role}</span> can:
                    </p>
                    <RoleAbilities role={me.role} />
                    <button
                        onClick={stop}
                        disabled={session.isFetching}
                        className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-3.5 text-[14px] font-semibold text-white transition active:scale-[.98] disabled:opacity-60"
                    >
                        {session.isFetching && <Loader2 size={15} className="animate-spin" />}
                        Switch back
                    </button>
                </div>

                <Link
                    href="/"
                    className="mt-5 flex items-center justify-center gap-2 text-[13px] font-medium text-slate-500"
                >
                    <ArrowLeft size={14} />
                    Back to the map
                </Link>
            </main>
        );
    }

    return (
        <main className="mx-auto flex min-h-[100dvh] w-full max-w-md flex-col justify-center px-5 py-10" style={{ paddingTop: "var(--acting-offset, 0px)" }}>
            <div className="rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
                <span className="grid h-11 w-11 place-items-center rounded-2xl bg-red-50 text-red-600">
                    <ShieldAlert size={20} />
                </span>

                {me ? (
                    <>
                        <h1 className="mt-4 text-[20px] font-semibold tracking-tight text-slate-900">
                            This page needs {NEEDED[required]}
                        </h1>
                        <p className="mt-1.5 text-[13px] leading-relaxed text-slate-500">
                            You are signed in as {me.email}, which does not have access.
                            Sign in with an account that does.
                        </p>
                        <div className="mt-5">
                            <SignInForm intro={`Use ${NEEDED[required]} to continue.`} />
                        </div>
                    </>
                ) : (
                    <SignInForm intro={`This page needs ${NEEDED[required]}. Sign in to continue.`} />
                )}
            </div>

            <Link
                href="/"
                className="mt-5 flex items-center justify-center gap-2 text-[13px] font-medium text-slate-500"
            >
                <ArrowLeft size={14} />
                Back to the map
            </Link>
        </main>
    );
}
