import Link from "next/link";
import { Check } from "lucide-react";

import type { Role } from "../lib/api";

const ABILITIES: Record<Role, { text: string; href?: string; hint?: string }[]> = {
    student: [
        { text: "Call 112 and campus security" },
        { text: "Find the nearest help and route to it", href: "/" },
        { text: "Report an incident from where they are", href: "/" },
    ],
    security: [
        { text: "Everything a student can do", href: "/" },
        { text: "Verify, dismiss or close incident reports", href: "/security" },
    ],
    mapper: [
        { text: "Everything a student can do", href: "/" },
        { text: "Add a place the map is missing", href: "/", hint: "long-press the map" },
    ],
    admin: [
        { text: "Everything, including roles and removing places", href: "/admin" },
    ],
};

export default function RoleAbilities({ role }: { role: Role }) {
    return (
        <ul className="mt-3 space-y-1.5">
            {ABILITIES[role].map((ability) => (
                <li key={ability.text} className="flex items-start gap-2 text-[12.5px] text-slate-600">
                    <Check size={14} className="mt-0.5 shrink-0 text-emerald-600" />
                    <span>
                        {ability.href ? (
                            <Link href={ability.href} className="font-medium text-slate-800 underline underline-offset-2">
                                {ability.text}
                            </Link>
                        ) : (
                            ability.text
                        )}
                        {ability.hint && (
                            <span className="text-slate-400"> ({ability.hint})</span>
                        )}
                    </span>
                </li>
            ))}
        </ul>
    );
}
