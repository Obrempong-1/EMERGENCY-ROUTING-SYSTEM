"use client";

import { useState } from "react";
import Link from "next/link";
import { MapPinPlus, ShieldAlert, TriangleAlert, X } from "lucide-react";

import type { Role } from "../lib/api";
import { can } from "../lib/roles";

const STORAGE_KEY = "knust.role-intro";

function dismissed(role: string): boolean {
    if (typeof window === "undefined") return true;
    try {
        return (window.localStorage.getItem(STORAGE_KEY) ?? "").split(",").includes(role);
    } catch {
        return true;
    }
}

function remember(role: string): void {
    try {
        const seen = (window.localStorage.getItem(STORAGE_KEY) ?? "").split(",").filter(Boolean);
        if (!seen.includes(role)) seen.push(role);
        window.localStorage.setItem(STORAGE_KEY, seen.join(","));
    } catch {
    }
}

interface RoleIntroCardProps {
    roles: Role[] | undefined;
    onAddPlace: () => void;
    onReport: () => void;
}

export default function RoleIntroCard({ roles, onAddPlace, onReport }: RoleIntroCardProps) {
    const which = can(roles, "add_places") && !can(roles, "manage_roles")
        ? "mapper"
        : can(roles, "resolve_incidents") && !can(roles, "manage_roles")
            ? "security"
            : roles && roles.length > 0
                ? "student"
                : null;

    const [hidden, setHidden] = useState(() => (which ? dismissed(which) : true));
    if (!which || hidden) return null;

    const close = () => {
        remember(which);
        setHidden(true);
    };

    const copy = {
        mapper: {
            Icon: MapPinPlus,
            text: "You can add places the map is missing.",
            action: <button onClick={onAddPlace} className="mt-2 rounded-xl bg-slate-900 px-3 py-2 text-[12px] font-semibold text-white">Add a place</button>,
        },
        security: {
            Icon: ShieldAlert,
            text: "You can verify and close incident reports.",
            action: <Link href="/security" className="mt-2 inline-block rounded-xl bg-slate-900 px-3 py-2 text-[12px] font-semibold text-white">Open the queue</Link>,
        },
        student: {
            Icon: TriangleAlert,
            text: "You can report a hazard from where you are.",
            action: <button onClick={onReport} className="mt-2 rounded-xl bg-slate-900 px-3 py-2 text-[12px] font-semibold text-white">Report something</button>,
        },
    }[which];

    return (
        <div className="mx-5 mb-3 flex items-start gap-2.5 rounded-2xl bg-slate-50 p-3.5 ring-1 ring-slate-200">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-white text-slate-700 shadow-sm">
                <copy.Icon size={15} />
            </span>
            <span className="min-w-0 flex-1">
                <span className="block text-[12.5px] leading-snug text-slate-700">{copy.text}</span>
                {copy.action}
            </span>
            <button
                onClick={close}
                aria-label="Dismiss"
                className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-slate-400"
            >
                <X size={14} />
            </button>
        </div>
    );
}
