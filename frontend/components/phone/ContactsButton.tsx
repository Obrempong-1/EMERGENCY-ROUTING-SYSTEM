"use client";

import { useState } from "react";
import { Phone } from "lucide-react";

import ContactsDialog from "../ContactsDialog";

interface ContactsButtonProps {
    onOpen?: () => void;
}

export default function ContactsButton({ onOpen }: ContactsButtonProps) {
    const [open, setOpen] = useState(false);

    return (
        <>
            <button
                onClick={() => { setOpen(true); onOpen?.(); }}
                aria-label="Emergency contacts"
                className="grid h-11 w-11 place-items-center rounded-full bg-red-600 text-white shadow-lg ring-1 ring-black/5 transition active:scale-95 lg:hidden"
            >
                <Phone size={18} strokeWidth={2.3} />
            </button>

            <ContactsDialog open={open} onClose={() => setOpen(false)} />
        </>
    );
}
