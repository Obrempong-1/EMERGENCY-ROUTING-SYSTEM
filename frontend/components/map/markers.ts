import L from 'leaflet';

import { escapeHtml, styleFor } from './categories';
import { categoryGlyphSvg, incidentGlyphSvg } from './icons';

const GLYPH_BOX = 10.5;

function pinSvg(color: string, category: string, size: number): string {
    const height = Math.round(size * 1.3);
    const offset = 16 - GLYPH_BOX / 2;
    return `
<svg width="${size}" height="${height}" viewBox="0 0 32 42" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M16 41.5c0 0-14-16.2-14-25.5a14 14 0 1128 0c0 9.3-14 25.5-14 25.5z"
        fill="${color}" stroke="#fff" stroke-width="2.4" stroke-linejoin="round"/>
  <circle cx="16" cy="15.5" r="7.9" fill="#fff" fill-opacity=".95"/>
  ${categoryGlyphSvg(category, offset, 15.5 - GLYPH_BOX / 2, GLYPH_BOX, color)}
</svg>`.trim();
}

const iconCache = new Map<string, L.DivIcon>();

function cached(key: string, build: () => L.DivIcon): L.DivIcon {
    const hit = iconCache.get(key);
    if (hit) return hit;
    const icon = build();
    iconCache.set(key, icon);
    return icon;
}

export function emergencyPin(category: string, active: boolean): L.DivIcon {
    return cached(`pin:${category}:${active}`, () => {
    const style = styleFor(category);
    const size = active ? 40 : 32;
    const height = Math.round(size * 1.3);
    return L.divIcon({
        className: 'knust-pin',
        html: `<div class="knust-pin__inner${active ? ' is-active' : ''}">${pinSvg(style.color, category, size)}</div>`,
        iconSize: [size, height],
        iconAnchor: [size / 2, height],
        popupAnchor: [0, -height + 6],
    });
    });
}

export function facilityDot(active: boolean): L.DivIcon {
    return cached(`dot:${active}`, () => {
    const size = active ? 16 : 10;
    return L.divIcon({
        className: 'knust-dot',
        html: `<span class="knust-dot__inner${active ? ' is-active' : ''}"></span>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
        popupAnchor: [0, -size / 2 - 2],
    });
    });
}

export function userPuck(): L.DivIcon {
    return cached('puck', () => L.divIcon({
        className: 'knust-puck',
        html: '<span class="knust-puck__pulse"></span><span class="knust-puck__core"></span>',
        iconSize: [22, 22],
        iconAnchor: [11, 11],
        popupAnchor: [0, -12],
    }));
}

export function labelIcon(name: string, category: string, offsetY: number): L.DivIcon {
    const style = styleFor(category);
    const emphasis = style.emergency ? ' is-emphasis' : '';
    return L.divIcon({
        className: 'knust-label',
        html: `<span class="knust-label__text${emphasis}">${escapeHtml(name)}</span>`,
        iconSize: [0, 0],
        iconAnchor: [0, -offsetY],
    });
}

const STATUS_COLORS: Record<string, string> = {
    unverified: '#a16207',
    likely: '#ea580c',
    confirmed: '#b91c1c',
    verified: '#7f1d1d',
};

export function incidentMarker(kind: string, status: string, confidence: number): L.DivIcon {
    const rounded = Math.round(confidence * 20) / 20;
    return cached(`incident:${kind}:${status}:${rounded}`, () => {
        const color = STATUS_COLORS[status] ?? '#a16207';
        const opacity = (0.45 + 0.55 * Math.min(Math.max(confidence, 0), 1)).toFixed(2);
        const size = 30;
        const box = 14;
        return L.divIcon({
            className: 'knust-incident',
            html: `<div class="knust-incident__inner" style="opacity:${opacity}">
<svg width="${size}" height="${size}" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
  <circle cx="16" cy="16" r="14" fill="${color}" stroke="#fff" stroke-width="2.4"/>
  ${incidentGlyphSvg(kind, 16 - box / 2, 16 - box / 2, box, '#fff')}
</svg></div>`,
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
            popupAnchor: [0, -size / 2],
        });
    });
}
