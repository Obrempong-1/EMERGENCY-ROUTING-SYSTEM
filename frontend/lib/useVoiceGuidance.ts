"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { Cue } from "./navigation";

const STORAGE_KEY = "knust.voice-guidance";

const URGENT_STAGE = 3;

function supported(): boolean {
    return typeof window !== "undefined" && "speechSynthesis" in window;
}

function stored(): boolean {
    if (typeof window === "undefined") return true;
    try {
        return window.localStorage.getItem(STORAGE_KEY) !== "off";
    } catch {
        return true;
    }
}

function remember(on: boolean): void {
    try {
        window.localStorage.setItem(STORAGE_KEY, on ? "on" : "off");
    } catch {
    }
}

export function useVoiceGuidance(cue: Cue | null, active: boolean) {
    const [enabled, setEnabled] = useState<boolean>(stored);
    const reached = useRef(new Map<string, number>());

    const say = useCallback((text: string, urgent = true) => {
        if (!supported() || !text) return;
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.05;
        utterance.lang = "en-GB";
        if (urgent) window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
    }, []);

    const toggle = useCallback(() => {
        const next = !enabled;
        if (next) {
            if (cue) reached.current.set(cue.id, cue.stage);
            say(cue?.text || "Voice directions on");
        } else if (supported()) {
            window.speechSynthesis.cancel();
        }
        remember(next);
        setEnabled(next);
    }, [enabled, cue, say]);

    const id = cue?.id;
    const stage = cue?.stage;
    const text = cue?.text;

    useEffect(() => {
        if (!enabled || !active || id === undefined || stage === undefined || !text) return;
        if (stage <= (reached.current.get(id) ?? -1)) return;
        reached.current.set(id, stage);
        say(text, stage === URGENT_STAGE);
    }, [enabled, active, id, stage, text, say]);

    useEffect(() => {
        if (active) return;
        reached.current.clear();
        if (supported()) window.speechSynthesis.cancel();
    }, [active]);

    useEffect(() => () => {
        if (supported()) window.speechSynthesis.cancel();
    }, []);

    return { enabled, toggle, supported: supported() };
}
