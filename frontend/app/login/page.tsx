"use client";

import Link from "next/link";
import { ArrowLeft, Mail, ShieldCheck } from "lucide-react";

import { useLogout, useSession } from "../../lib/queries";
import SignInForm from "../../components/SignInForm";

export default function LoginPage() {
    const session = useSession();
    const logout = useLogout();

    const student = session.data;

    if (student) {
        return (
            <main className="mx-auto flex min-h-[100dvh] w-full max-w-md flex-col justify-center px-5 py-10" style={{ paddingTop: "var(--acting-offset, 0px)" }}>
                <div className="rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
                    <div className="flex items-center gap-3">
                        <span className="grid h-11 w-11 place-items-center rounded-2xl bg-emerald-50 text-emerald-600">
                            <ShieldCheck size={20} />
                        </span>
                        <div className="min-w-0">
                            <p className="truncate text-[15px] font-semibold text-slate-900">
                                {student.email}
                            </p>
                            <p className="text-[12px] text-slate-500">
                                {student.knust_verified ? "Verified KNUST member" : "Community account"}
                            </p>
                        </div>
                    </div>

                    <dl className="mt-5 space-y-2 rounded-2xl bg-slate-50 p-4 text-[12.5px]">
                        <div className="flex items-center justify-between">
                            <dt className="text-slate-500">Report weight</dt>
                            <dd className="font-semibold tabular-nums text-slate-900">
                                {student.trust.toFixed(2)}
                            </dd>
                        </div>
                        <div className="flex items-center justify-between">
                            <dt className="text-slate-500">Role</dt>
                            <dd className="font-semibold text-slate-900">{student.role}</dd>
                        </div>
                    </dl>

                    <p className="mt-4 text-[12px] leading-relaxed text-slate-500">
                        {student.knust_verified
                            ? "Your reports carry full weight because your address belongs to KNUST."
                            : "Reports from community accounts carry less weight, so they need more independent corroboration before an incident is shown as confirmed."}
                    </p>

                    <button
                        onClick={() => logout.mutate()}
                        disabled={logout.isPending}
                        className="mt-5 w-full rounded-2xl bg-slate-900 px-4 py-3 text-[13.5px] font-semibold text-white transition active:scale-[.98] disabled:opacity-60"
                    >
                        {logout.isPending ? "Signing out..." : "Sign out"}
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
                    <Mail size={20} />
                </span>

                <SignInForm intro="Reporting an incident needs an account, so every report is accountable. Calling 112 and sharing your location never do." />
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
