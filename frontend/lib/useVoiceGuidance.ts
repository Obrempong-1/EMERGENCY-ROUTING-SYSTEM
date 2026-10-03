"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "knust.voice-guidance";

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

export function useVoiceGuidance(phrase: string, active: boolean) {
    const [enabled, setEnabled] = useState<boolean>(stored);
    const spoken = useRef("");

    const say = useCallback((text: string) => {
        if (!supported() || !text) return;
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.05;
        utterance.lang = "en-GB";
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
    }, []);

    const toggle = useCallback(() => {
        const next = !enabled;
        if (next) {
            spoken.current = phrase;
            say(phrase || "Voice directions on");
        } else if (supported()) {
            window.speechSynthesis.cancel();
            spoken.current = "";
        }
        remember(next);
        setEnabled(next);
    }, [enabled, phrase, say]);

    useEffect(() => {
        if (!enabled || !active || !phrase) return;
        if (phrase === spoken.current) return;
        spoken.current = phrase;
        say(phrase);
    }, [enabled, active, phrase, say]);

    useEffect(() => {
        if (active || !supported()) return;
        window.speechSynthesis.cancel();
    }, [active]);

    useEffect(() => {
        if (phrase) return;
        spoken.current = "";
    }, [phrase]);

    useEffect(() => () => {
        if (supported()) window.speechSynthesis.cancel();
    }, []);

    return { enabled, toggle, supported: supported() };
}
