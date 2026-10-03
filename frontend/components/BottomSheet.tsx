"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

export type SheetSnap = 'rest' | 'list';

const LIST_VH = 72;
const ORDER: SheetSnap[] = ['rest', 'list'];
const DRAG_THRESHOLD_PX = 44;

interface BottomSheetProps {
    snap: SheetSnap;
    onSnapChange: (snap: SheetSnap) => void;
    rest: React.ReactNode;
    children: React.ReactNode;
    label?: string;
    onHeightChange?: (height: number) => void;
}

export default function BottomSheet({
    snap, onSnapChange, rest, children, label, onHeightChange,
}: BottomSheetProps) {
    const [dragging, setDragging] = useState(false);
    const [dragOffset, setDragOffset] = useState(0);
    const [restHeight, setRestHeight] = useState(0);
    const sheetRef = useRef<HTMLElement>(null);
    const restRef = useRef<HTMLDivElement>(null);
    const startY = useRef(0);
    const moved = useRef(false);

    useLayoutEffect(() => {
        const node = restRef.current;
        if (!node) return;
        const measure = () => setRestHeight(node.getBoundingClientRect().height);
        measure();
        const observer = new ResizeObserver(measure);
        observer.observe(node);
        return () => observer.disconnect();
    }, []);

    const report = useCallback(() => {
        const node = sheetRef.current;
        if (!node || !onHeightChange) return;
        const box = node.getBoundingClientRect();
        onHeightChange(Math.max(0, window.innerHeight - box.top));
    }, [onHeightChange]);

    useLayoutEffect(() => {
        const node = sheetRef.current;
        if (!node || !onHeightChange || typeof ResizeObserver === 'undefined') return;
        report();
        const observer = new ResizeObserver(report);
        observer.observe(node);
        window.addEventListener('resize', report);
        return () => {
            observer.disconnect();
            window.removeEventListener('resize', report);
            onHeightChange(0);
        };
    }, [onHeightChange, report]);

    useLayoutEffect(() => {
        if (!onHeightChange) return;
        let frame = 0;
        const tick = () => { report(); frame = requestAnimationFrame(tick); };
        frame = requestAnimationFrame(tick);
        const stop = setTimeout(() => cancelAnimationFrame(frame), dragging ? 60_000 : 420);
        return () => { cancelAnimationFrame(frame); clearTimeout(stop); };
    }, [dragging, snap, onHeightChange, report]);

    const endDrag = useCallback((delta: number) => {
        const index = ORDER.indexOf(snap);
        if (delta <= -DRAG_THRESHOLD_PX && index < ORDER.length - 1) {
            onSnapChange(ORDER[index + 1]);
        } else if (delta >= DRAG_THRESHOLD_PX && index > 0) {
            onSnapChange(ORDER[index - 1]);
        }
        setDragOffset(0);
        setDragging(false);
    }, [snap, onSnapChange]);

    useEffect(() => {
        if (!dragging) return;
        const move = (event: PointerEvent) => {
            const delta = event.clientY - startY.current;
            if (Math.abs(delta) > 4) moved.current = true;
            setDragOffset(delta);
        };
        const up = (event: PointerEvent) => endDrag(event.clientY - startY.current);
        window.addEventListener('pointermove', move);
        window.addEventListener('pointerup', up);
        window.addEventListener('pointercancel', up);
        return () => {
            window.removeEventListener('pointermove', move);
            window.removeEventListener('pointerup', up);
            window.removeEventListener('pointercancel', up);
        };
    }, [dragging, endDrag]);

    const onPointerDown = (event: React.PointerEvent) => {
        moved.current = false;
        startY.current = event.clientY;
        setDragOffset(0);
        setDragging(true);
    };

    const onHandleClick = () => {
        if (moved.current) return;
        onSnapChange(snap === 'rest' ? 'list' : 'rest');
    };

    const collapsed = snap === 'rest';
    const height = collapsed
        ? `calc(${restHeight || 96}px + env(safe-area-inset-bottom))`
        : `${LIST_VH}dvh`;

    return (
        <section
            ref={sheetRef}
            aria-label={label}
            className="fixed inset-x-0 bottom-0 z-[700] flex flex-col rounded-t-3xl bg-white shadow-[0_-12px_40px_rgba(15,23,42,.18)] ring-1 ring-black/5 lg:hidden"
            style={{
                height,
                transform: `translateY(${Math.max(dragOffset, 0)}px)`,
                transition: dragging
                    ? 'none'
                    : 'height .3s cubic-bezier(.32,.72,0,1), transform .3s cubic-bezier(.32,.72,0,1)',
                paddingBottom: 'env(safe-area-inset-bottom)',
            }}
        >
            <div ref={restRef} className="shrink-0">
                <button
                    onPointerDown={onPointerDown}
                    onClick={onHandleClick}
                    aria-label={collapsed
                        ? 'Emergency panel. Tap to see the list.'
                        : 'Tap to shrink the panel.'}
                    className="flex w-full touch-none cursor-grab items-center justify-center rounded-t-3xl px-4 pb-2 pt-3.5 active:cursor-grabbing"
                >
                    <span className="h-1.5 w-11 rounded-full bg-slate-300" />
                </button>
                {rest}
            </div>

            <div
                aria-hidden={collapsed}
                inert={collapsed}
                className={`min-h-0 flex-1 ${
                    collapsed ? 'overflow-hidden opacity-0' : 'custom-scrollbar overflow-y-auto overscroll-contain opacity-100'
                } transition-opacity duration-200`}
            >
                {children}
            </div>
        </section>
    );
}
