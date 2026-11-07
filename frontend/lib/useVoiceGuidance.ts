"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { Cue } from "./navigation";

const STORAGE_KEY = "knust.voice-guidance";

const URGENT_STAGE = 3;
const AFTER_CANCEL_MS = 80;
const UNLOCK_EVENTS = ["pointerdown", "keydown", "touchend"] as const;

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

function englishVoice(): SpeechSynthesisVoice | null {
    const voices = window.speechSynthesis.getVoices();
    return voices.find((voice) => voice.lang.replace("_", "-") === "en-GB")
        ?? voices.find((voice) => voice.lang.toLowerCase().startsWith("en"))
        ?? null;
}

let unlocked = false;

/**
 * iOS only lets a page speak once speech has been started from a tap, so the
 * first tap anywhere plays a silent utterance; spoken directions, which start
 * from GPS updates rather than taps, then work for the rest of the visit.
 */
function unlockOnFirstTap(): () => void {
    if (unlocked || !supported()) return () => {};
    const unlock = () => {
        unlocked = true;
        const silent = new SpeechSynthesisUtterance(" ");
        silent.volume = 0;
        window.speechSynthesis.speak(silent);
        stop();
    };
    const stop = () => UNLOCK_EVENTS.forEach((name) => window.removeEventListener(name, unlock));
    UNLOCK_EVENTS.forEach((name) => window.addEventListener(name, unlock, { once: true }));
    return stop;
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

    useEffect(() => unlockOnFirstTap(), []);

    const say = useCallback((text: string, urgent = true) => {
        if (!supported() || !text) return;
        const synth = window.speechSynthesis;
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.05;
        utterance.lang = "en-GB";
        const voice = englishVoice();
        if (voice) utterance.voice = voice;

        synth.resume();
        if (urgent && (synth.speaking || synth.pending)) {
            synth.cancel();
            window.setTimeout(() => synth.speak(utterance), AFTER_CANCEL_MS);
        } else {
            synth.speak(utterance);
        }
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
