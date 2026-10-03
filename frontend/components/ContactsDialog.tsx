"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";
import { Phone, X } from "lucide-react";

import { useEmergencyContacts } from "../lib/queries";

interface ContactsDialogProps {
    open: boolean;
    onClose: () => void;
}

export default function ContactsDialog({ open, onClose }: ContactsDialogProps) {
    const contacts = useEmergencyContacts();

    useEffect(() => {
        if (!open) return;
        const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    if (!open) return null;

    return createPortal(
        <div
            onClick={onClose}
            className="fixed inset-0 z-[1200] flex items-end justify-center bg-slate-900/50 p-4 backdrop-blur-sm sm:items-center"
        >
            <div
                onClick={(event) => event.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-label="Emergency numbers"
                className="w-full max-w-sm rounded-3xl bg-white p-5 shadow-2xl"
            >
                <div className="flex items-center justify-between">
                    <h2 className="text-[15px] font-semibold text-slate-900">
                        Emergency numbers
                    </h2>
                    <button
                        onClick={onClose}
                        aria-label="Close"
                        className="grid h-8 w-8 place-items-center rounded-full bg-slate-100 text-slate-500"
                    >
                        <X size={15} />
                    </button>
                </div>

                <ul className="mt-4 space-y-2">
                    {contacts.map((contact) => (
                        <li key={contact.id}>
                            <a
                                href={`tel:${contact.number}`}
                                className={`flex items-center justify-between rounded-2xl px-4 py-3.5 transition active:scale-[.99] ${
                                    contact.primary
                                        ? "bg-red-600 text-white"
                                        : "bg-slate-50 text-slate-800"
                                }`}
                            >
                                <span className="text-[13.5px] font-medium">{contact.label}</span>
                                <span className="flex items-center gap-2 text-[15px] font-semibold tabular-nums">
                                    {contact.number}
                                    <Phone size={15} />
                                </span>
                            </a>
                        </li>
                    ))}
                </ul>
            </div>
        </div>,
        document.body,
    );
}
