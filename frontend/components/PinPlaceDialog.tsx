"use client";

import { useEffect, useRef, useState } from "react";
import { MapPin, X } from "lucide-react";

import {
    errorMessage,
    type CategorySummary,
    type EmergencyCategory,
    type Facility,
} from "../lib/api";
import { useCreatePlace } from "../lib/queries";
import { styleFor } from "./map/categories";

interface PinPlaceDialogProps {
    point: { lat: number; lon: number };
    categories: CategorySummary[];
    onCancel: () => void;
    onCreated: (place: Facility) => void;
}

export default function PinPlaceDialog({
    point, categories, onCancel, onCreated,
}: PinPlaceDialogProps) {
    const [name, setName] = useState("");
    const [category, setCategory] = useState<EmergencyCategory>(
        categories[0]?.category ?? "student_services");
    const [error, setError] = useState("");
    const inputRef = useRef<HTMLInputElement>(null);
    const createPlace = useCreatePlace();
    const saving = createPlace.isPending;

    useEffect(() => { inputRef.current?.focus(); }, []);
    useEffect(() => {
        const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [onCancel]);

    const submit = async () => {
        if (!name.trim() || saving) return;
        setError("");
        try {
            const result = await createPlace.mutateAsync({
                name: name.trim(), category, lat: point.lat, lon: point.lon,
            });
            onCreated(result.place);
        } catch (err) {
            setError(errorMessage(err, "Could not save that place."));
        }
    };

    return (
        <div className="fixed inset-0 z-[900] flex items-end justify-center bg-slate-900/40 p-4 backdrop-blur-sm sm:items-center">
            <div
                role="dialog"
                aria-modal="true"
                aria-label="Add a campus place"
                className="w-full max-w-sm rounded-3xl bg-white p-5 shadow-2xl"
            >
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                        <span className="grid h-9 w-9 place-items-center rounded-xl bg-slate-900 text-white">
                            <MapPin size={16} />
                        </span>
                        <div>
                            <h2 className="text-[15px] font-semibold text-slate-900">Add a place</h2>
                            <p className="text-[11px] text-slate-500">
                                {point.lat.toFixed(5)}, {point.lon.toFixed(5)}
                            </p>
                        </div>
                    </div>
                    <button onClick={onCancel} aria-label="Cancel"
                        className="grid h-8 w-8 place-items-center rounded-full bg-slate-100 text-slate-500">
                        <X size={15} />
                    </button>
                </div>

                <label className="mt-4 block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    Name
                </label>
                <input
                    ref={inputRef}
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    onKeyDown={(event) => { if (event.key === "Enter") submit(); }}
                    placeholder="J. Harper Building"
                    className="mt-1.5 w-full rounded-2xl border border-slate-200 bg-slate-50/70 px-3.5 py-3 text-[13.5px] outline-none focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-500/10"
                />

                <label className="mt-4 block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    Category
                </label>
                <div className="mt-1.5 grid grid-cols-3 gap-1.5">
                    {categories.map((entry) => {
                        const style = styleFor(entry.category);
                        const chosen = category === entry.category;
                        return (
                            <button
                                key={entry.category}
                                onClick={() => setCategory(entry.category)}
                                aria-pressed={chosen}
                                className={`rounded-xl px-2 py-2 text-[10.5px] font-semibold transition ${
                                    chosen ? "text-white" : "bg-slate-100 text-slate-600"
                                }`}
                                style={chosen ? { background: style.color } : undefined}
                            >
                                {entry.label}
                            </button>
                        );
                    })}
                </div>

                {error && (
                    <p role="alert" className="mt-3 rounded-2xl bg-red-50 px-3.5 py-2.5 text-[12px] text-red-700">
                        {error}
                    </p>
                )}

                <button
                    onClick={submit}
                    disabled={!name.trim() || saving}
                    className="mt-4 w-full rounded-2xl bg-slate-900 py-3.5 text-[13px] font-semibold text-white transition active:scale-[.99] disabled:bg-slate-300"
                >
                    {saving ? "Saving…" : "Save place"}
                </button>
            </div>
        </div>
    );
}
