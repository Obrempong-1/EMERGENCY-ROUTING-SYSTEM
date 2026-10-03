"use client";

import { useState } from "react";
import { BadgeCheck, Loader2, MailCheck } from "lucide-react";

import { errorMessage } from "../lib/api";
import { useResetPassword, useSignIn, useSignUp } from "../lib/queries";

const MIN_PASSWORD = 8;

type Mode = "signin" | "signup";

interface SignInFormProps {
    intro: string;
}

const FIELD = "w-full rounded-2xl bg-slate-50 px-4 py-3.5 text-[16px] lg:text-[15px] text-slate-900 outline-none ring-1 ring-slate-200 transition focus:ring-2 focus:ring-red-500";
const SUBMIT = "flex w-full items-center justify-center gap-2 rounded-2xl bg-red-600 px-4 py-3.5 text-[14px] font-semibold text-white transition active:scale-[.98] disabled:opacity-50";

export default function SignInForm({ intro }: SignInFormProps) {
    const [mode, setMode] = useState<Mode>("signin");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [sent, setSent] = useState<"confirm" | "reset" | null>(null);

    const signIn = useSignIn();
    const signUp = useSignUp();
    const reset = useResetPassword();

    const address = email.trim();
    const knustAddress = /@(st\.)?knust\.edu\.gh$/i.test(address);
    const busy = signIn.isPending || signUp.isPending || reset.isPending;
    const failure = signIn.error ?? signUp.error ?? reset.error;

    const submit = async () => {
        setSent(null);
        if (mode === "signin") {
            await signIn.mutateAsync({ email: address, password }).catch(() => {});
            return;
        }
        const result = await signUp
            .mutateAsync({ email: address, password })
            .catch(() => null);
        if (result?.needsConfirmation) setSent("confirm");
    };

    const forgot = async () => {
        setSent(null);
        await reset.mutateAsync(address).catch(() => {});
        if (!reset.isError) setSent("reset");
    };

    if (sent) {
        return (
            <>
                <h1 className="mt-4 text-[20px] font-semibold tracking-tight text-slate-900">
                    Check your email
                </h1>
                <p className="mt-1.5 flex items-start gap-2 text-[13px] leading-relaxed text-slate-500">
                    <MailCheck size={16} className="mt-0.5 shrink-0 text-emerald-600" />
                    {sent === "confirm"
                        ? `We sent a confirmation link to ${address}. Click it to finish creating your account, then come back and sign in.`
                        : `We sent a reset link to ${address}. Click it to choose a new password.`}
                </p>
                <button
                    type="button"
                    onClick={() => { setSent(null); setMode("signin"); }}
                    className="mt-5 w-full py-1 text-[12.5px] font-medium text-slate-500"
                >
                    Back to sign in
                </button>
            </>
        );
    }

    return (
        <>
            <h1 className="mt-4 text-[20px] font-semibold tracking-tight text-slate-900">
                {mode === "signin" ? "Sign in" : "Create an account"}
            </h1>
            <p className="mt-1.5 text-[13px] leading-relaxed text-slate-500">
                {mode === "signin"
                    ? intro
                    : "New here? Choose a password and we will email you a link to confirm the address."}
            </p>

            <form
                onSubmit={(event) => { event.preventDefault(); submit(); }}
                className="mt-5 space-y-3"
            >
                <input
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@st.knust.edu.gh"
                    className={FIELD}
                />

                <input
                    type="password"
                    autoComplete={mode === "signin" ? "current-password" : "new-password"}
                    required
                    minLength={MIN_PASSWORD}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Password"
                    className={FIELD}
                />

                {mode === "signup" && address.length > 3 && (
                    <p className={`flex items-start gap-2 text-[12px] leading-relaxed ${
                        knustAddress ? "text-emerald-700" : "text-amber-700"
                    }`}>
                        <BadgeCheck size={14} className="mt-0.5 shrink-0" />
                        {knustAddress
                            ? "A KNUST address gives your reports full weight."
                            : "Any address can sign in, but reports from non-KNUST accounts need more corroboration."}
                    </p>
                )}

                <button
                    type="submit"
                    disabled={busy || address.length < 4 || password.length < MIN_PASSWORD}
                    className={SUBMIT}
                >
                    {busy && <Loader2 size={15} className="animate-spin" />}
                    {mode === "signin" ? "Sign in" : "Create account"}
                </button>

                {failure && (
                    <p role="alert" className="text-[12.5px] text-red-600">
                        {errorMessage(failure, mode === "signin"
                            ? "That email and password did not match."
                            : "Could not create the account.")}
                    </p>
                )}
            </form>

            <div className="mt-3 flex items-center justify-between">
                <button
                    type="button"
                    onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
                    className="py-1 text-[12.5px] font-semibold text-slate-700"
                >
                    {mode === "signin" ? "Create an account" : "I already have an account"}
                </button>

                {mode === "signin" && (
                    <button
                        type="button"
                        onClick={forgot}
                        disabled={address.length < 4 || busy}
                        className="py-1 text-[12.5px] font-medium text-slate-500 disabled:opacity-40"
                    >
                        Forgot password
                    </button>
                )}
            </div>
        </>
    );
}
