"use client";

import { useState } from "react";
import { Phone, ShieldAlert } from "lucide-react";

import { useEmergencyContacts } from "../lib/queries";
import ContactsDialog from "./ContactsDialog";

export default function EmergencyBar() {
    const contacts = useEmergencyContacts();
    const [open, setOpen] = useState(false);
    const primary = contacts.filter((contact) => contact.primary).slice(0, 2);

    return (
        <>
            <div className="flex items-center gap-1.5 px-5 pb-3">
                {primary.map((contact) => (
                    <a
                        key={contact.id}
                        href={`tel:${contact.number}`}
                        className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-red-600 px-3 py-2.5 text-[12.5px] font-semibold text-white shadow-sm transition active:scale-[.97]"
                    >
                        <Phone size={14} />
                        {contact.number}
                    </a>
                ))}
                <button
                    onClick={() => setOpen(true)}
                    aria-label="All emergency numbers"
                    className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-red-50 text-red-700 transition active:scale-95"
                >
                    <ShieldAlert size={16} />
                </button>
            </div>

            <ContactsDialog open={open} onClose={() => setOpen(false)} />
        </>
    );
}
