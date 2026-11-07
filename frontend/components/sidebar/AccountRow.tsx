"use client";

import Link from "next/link";
import { ChevronRight, LogIn, UserRound } from "lucide-react";

import { useLogout, useSession } from "../../lib/queries";
import { supabaseConfigured } from "../../lib/supabase";

export default function AccountRow() {
    const session = useSession();
    const logout = useLogout();

    if (!supabaseConfigured || session.isPending) return null;

    const student = session.data;

    if (!student) {
        return (
            <Link
                href="/login"
                className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 transition hover:border-slate-300 hover:bg-slate-50"
            >
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-600">
                    <LogIn size={15} />
                </span>
                <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-semibold text-slate-900">Sign in</span>
                    <span className="block text-[11px] text-slate-500">Needed to report incidents</span>
                </span>
                <ChevronRight size={16} className="shrink-0 text-slate-400" />
            </Link>
        );
    }

    return (
        <div className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-600">
                <UserRound size={15} />
            </span>
            <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-semibold text-slate-900">Signed in</span>
                <span className="block truncate text-[11px] text-slate-500">{student.email}</span>
            </span>
            <button
                onClick={() => logout.mutate()}
                disabled={logout.isPending}
                className="shrink-0 rounded-xl bg-slate-900 px-3 py-1.5 text-[12px] font-semibold text-white transition active:scale-95 disabled:opacity-60"
            >
                {logout.isPending ? "Signing out..." : "Sign out"}
            </button>
        </div>
    );
}
