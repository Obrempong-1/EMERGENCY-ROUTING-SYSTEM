"use client";

import { useEffect } from "react";
import { Eye, Loader2 } from "lucide-react";

import { setActingRole } from "../lib/api";
import { useSession } from "../lib/queries";

const BAR_HEIGHT = "2.25rem";

export default function ActingBanner() {
    const session = useSession();
    const me = session.data;
    const acting = Boolean(me?.real_role && me.real_role !== me.role);

    useEffect(() => {
        const root = document.documentElement;
        if (!acting) return;
        root.style.setProperty("--acting-offset", BAR_HEIGHT);
        return () => { root.style.removeProperty("--acting-offset"); };
    }, [acting]);

    if (!acting || !me) return null;

    const stop = () => {
        setActingRole(null);
        session.refetch();
    };

    return (
        <div
            className="pointer-events-auto fixed inset-x-0 top-0 z-[1100] flex items-center justify-center gap-3 bg-amber-500 px-4 text-[12.5px] font-semibold text-amber-950 shadow-lg"
            style={{ height: BAR_HEIGHT }}
        >
            <Eye size={14} className="shrink-0" />
            <span className="min-w-0 truncate">
                Viewing as <span className="capitalize">{me.role}</span>
            </span>
            <button
                onClick={stop}
                disabled={session.isFetching}
                className="flex shrink-0 items-center gap-1.5 rounded-full bg-amber-950 px-3 py-1 text-[11.5px] font-semibold text-amber-50 transition active:scale-95 disabled:opacity-60"
            >
                {session.isFetching && <Loader2 size={11} className="animate-spin" />}
                Switch back
            </button>
        </div>
    );
}
