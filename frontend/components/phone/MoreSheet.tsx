"use client";

import Link from "next/link";
import { ChevronRight, type LucideIcon } from "lucide-react";

export interface MoreRow {
    id: string;
    label: string;
    hint: string;
    Icon: LucideIcon;
    href?: string;
    onSelect?: () => void;
    active?: boolean;
}

interface MoreSheetProps {
    rows: MoreRow[];
}

const SHELL = "flex w-full items-center gap-3 rounded-2xl border px-4 py-3.5 text-left transition active:scale-[.98]";

export default function MoreSheet({ rows }: MoreSheetProps) {
    return (
        <ul className="space-y-2 px-5 pb-6 pt-1">
            {rows.map(({ id, label, hint, Icon, href, onSelect, active }) => {
                const body = (
                    <>
                        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${
                            active ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"
                        }`}>
                            <Icon size={16} />
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="block text-[13.5px] font-semibold text-slate-900">{label}</span>
                            <span className="block text-[11px] text-slate-500">{hint}</span>
                        </span>
                        <ChevronRight size={16} className="shrink-0 text-slate-300" />
                    </>
                );
                const shell = `${SHELL} ${active ? "border-slate-900 bg-slate-50" : "border-slate-200 bg-white"}`;
                return (
                    <li key={id}>
                        {href
                            ? <Link href={href} className={shell}>{body}</Link>
                            : <button onClick={onSelect} className={shell}>{body}</button>}
                    </li>
                );
            })}
        </ul>
    );
}
