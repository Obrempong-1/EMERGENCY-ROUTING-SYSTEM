"use client";

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { HelpCircle } from 'lucide-react';

interface HelpButtonProps {
    id: string;
    label: string;
    title: string;
    active?: boolean;
    children: ReactNode;
}

export default function HelpButton({ id, label, title, active = false, children }: HelpButtonProps) {
    const [open, setOpen] = useState(false);
    const [pinned, setPinned] = useState(false);
    const rootRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!pinned) return;
        const close = (event: PointerEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) {
                setPinned(false);
                setOpen(false);
            }
        };
        const onKey = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setPinned(false);
                setOpen(false);
            }
        };
        document.addEventListener('pointerdown', close);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('pointerdown', close);
            document.removeEventListener('keydown', onKey);
        };
    }, [pinned]);

    return (
        <div
            ref={rootRef}
            className="relative h-full"
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => { if (!pinned) setOpen(false); }}
        >
            <button
                type="button"
                onClick={() => {
                    const next = !pinned;
                    setPinned(next);
                    setOpen(next);
                }}
                aria-label={label}
                aria-expanded={open}
                aria-controls={id}
                className={`flex h-full w-9 items-center justify-center rounded-r-full pr-0.5 transition active:scale-95 ${
                    active ? 'text-white/80 hover:text-white' : 'text-slate-500 hover:text-slate-800'
                }`}
            >
                <HelpCircle size={16} />
            </button>

            {open && (
                <div
                    id={id}
                    role="tooltip"
                    className="absolute right-0 top-full z-[700] mt-2 w-[min(17rem,calc(100vw-2rem))] rounded-2xl bg-white p-3.5 text-left shadow-xl ring-1 ring-black/10"
                >
                    <p className="text-[12.5px] font-semibold text-slate-900">{title}</p>
                    <div className="mt-1.5 space-y-2 text-[11.5px] leading-relaxed text-slate-600">
                        {children}
                    </div>
                </div>
            )}
        </div>
    );
}
