import { useCallback, useMemo, useRef, useSyncExternalStore } from 'react';
import type { Map as LeafletMap } from 'leaflet';
import type { MapMarker } from '@/lib/api';
import { styleFor } from './categories';

export interface PlacedMarker {
    marker: MapMarker;
    showLabel: boolean;
    isEmergency: boolean;
}

const PIN_ZOOM = { emergency: 0, facility: 16 };
const LABEL_ZOOM = { emergency: 15, facility: 17 };

const MAX_PINS = 320;
const LABEL_HEIGHT = 15;
const CHAR_WIDTH = 6.7;
const LABEL_PADDING = 7;
const LABEL_GAP = 4;
const VIEWPORT_MARGIN = 0.18;

interface Box {
    left: number;
    right: number;
    top: number;
    bottom: number;
}

function overlaps(a: Box, b: Box): boolean {
    return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
}

function viewportSignature(map: LeafletMap | null): string {
    if (!map) return '';
    const bounds = map.getBounds();
    const size = map.getSize();
    return [
        map.getZoom().toFixed(3),
        bounds.getSouth().toFixed(5), bounds.getWest().toFixed(5),
        bounds.getNorth().toFixed(5), bounds.getEast().toFixed(5),
        size.x, size.y,
    ].join('|');
}

export function useMapLabels(map: LeafletMap | null, markers: MapMarker[],
                             activeId: string | null): PlacedMarker[] {
    const cached = useRef('');

    const subscribe = useCallback((onChange: () => void) => {
        if (!map) return () => undefined;
        map.on('moveend', onChange);
        map.on('zoomend', onChange);
        map.on('resize', onChange);
        return () => {
            map.off('moveend', onChange);
            map.off('zoomend', onChange);
            map.off('resize', onChange);
        };
    }, [map]);

    const getSnapshot = useCallback(() => {
        const next = viewportSignature(map);
        if (next !== cached.current) cached.current = next;
        return cached.current;
    }, [map]);

    const signature = useSyncExternalStore(subscribe, getSnapshot, () => '');

    return useMemo(() => {
        if (!map) return [];
        void signature;

        const zoom = map.getZoom();
        const bounds = map.getBounds().pad(VIEWPORT_MARGIN);

        const narrow = map.getSize().x < 640;
        const facilityLabelZoom = LABEL_ZOOM.facility + (narrow ? 1 : 0);
        const maxPins = narrow ? 160 : MAX_PINS;

        const candidates = markers
            .filter((m) => bounds.contains([m.lat, m.lon]))
            .map((m) => {
                const style = styleFor(m.category);
                const isEmergency = style.emergency;
                const isUser = m.category === 'user';
                const isActive = m.id === activeId;
                return { marker: m, style, isEmergency, isUser, isActive };
            })
            .filter(({ isEmergency, isUser, isActive }) =>
                isUser || isActive || isEmergency || zoom >= PIN_ZOOM.facility);

        candidates.sort((a, b) => {
            if (a.isActive !== b.isActive) return a.isActive ? -1 : 1;
            return b.style.priority - a.style.priority;
        });

        const visible = candidates.slice(0, maxPins);
        const placed: Box[] = [];
        const out: PlacedMarker[] = [];

        for (const entry of visible) {
            const { marker, isEmergency, isUser, isActive } = entry;
            const threshold = isEmergency ? LABEL_ZOOM.emergency : facilityLabelZoom;
            let showLabel = !isUser && (isActive || zoom >= threshold);

            if (showLabel) {
                const point = map.latLngToContainerPoint([marker.lat, marker.lon]);
                const halfWidth = (marker.name.length * CHAR_WIDTH) / 2 + LABEL_PADDING;
                const offset = isEmergency || isActive ? 46 : 14;
                const top = point.y + offset;
                const box: Box = {
                    left: point.x - halfWidth - LABEL_GAP,
                    right: point.x + halfWidth + LABEL_GAP,
                    top: top - LABEL_GAP,
                    bottom: top + LABEL_HEIGHT + LABEL_GAP,
                };
                if (placed.some((other) => overlaps(box, other))) {
                    showLabel = false;
                } else {
                    placed.push(box);
                }
            }

            out.push({ marker, showLabel, isEmergency });
        }

        return out;
    }, [map, markers, activeId, signature]);
}
