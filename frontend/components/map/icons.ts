import {
    Circle,
    Construction,
    Cross,
    Eye,
    Flame,
    GraduationCap,
    Landmark,
    Navigation,
    Siren,
    TriangleAlert,
    UserX,
    Waves,
    type LucideIcon,
} from "lucide-react";
import {
    Circle as CircleSvg,
    Construction as ConstructionSvg,
    Cross as CrossSvg,
    Eye as EyeSvg,
    Flame as FlameSvg,
    GraduationCap as GraduationCapSvg,
    Landmark as LandmarkSvg,
    Navigation as NavigationSvg,
    Siren as SirenSvg,
    TriangleAlert as TriangleAlertSvg,
    UserX as UserXSvg,
    Waves as WavesSvg,
} from "lucide-static";

import type { Category } from "./categories";

type IncidentKindName =
    | "blocked_road" | "flooding" | "accident" | "suspicious_activity";

const CATEGORY_ICONS: Record<Category, LucideIcon> = {
    medical: Cross,
    police: Siren,
    fire_station: Flame,
    security: Eye,
    administration: Landmark,
    student_services: GraduationCap,
    facility: Circle,
    user: Navigation,
};

const INCIDENT_ICONS: Record<IncidentKindName, LucideIcon> = {
    blocked_road: Construction,
    flooding: Waves,
    accident: TriangleAlert,
    suspicious_activity: UserX,
};

const CATEGORY_SVG: Record<Category, string> = {
    medical: CrossSvg,
    police: SirenSvg,
    fire_station: FlameSvg,
    security: EyeSvg,
    administration: LandmarkSvg,
    student_services: GraduationCapSvg,
    facility: CircleSvg,
    user: NavigationSvg,
};

const INCIDENT_SVG: Record<IncidentKindName, string> = {
    blocked_road: ConstructionSvg,
    flooding: WavesSvg,
    accident: TriangleAlertSvg,
    suspicious_activity: UserXSvg,
};

const VIEWBOX = 24;
const TARGET_STROKE_PX = 1.75;

function inner(svg: string): string {
    return svg
        .replace(/^[\s\S]*?<svg[^>]*>/, "")
        .replace(/<\/svg>\s*$/, "")
        .trim();
}

export function categoryIcon(category: string): LucideIcon {
    return CATEGORY_ICONS[category as Category] ?? CATEGORY_ICONS.facility;
}

export function incidentIcon(kind: string): LucideIcon {
    return INCIDENT_ICONS[kind as IncidentKindName] ?? INCIDENT_ICONS.accident;
}

function glyph(markup: string, x: number, y: number, size: number, color: string): string {
    const strokeWidth = (TARGET_STROKE_PX * VIEWBOX) / size;
    return `<svg x="${x}" y="${y}" width="${size}" height="${size}" viewBox="0 0 ${VIEWBOX} ${VIEWBOX}"
 fill="none" stroke="${color}" stroke-width="${strokeWidth.toFixed(2)}"
 stroke-linecap="round" stroke-linejoin="round">${inner(markup)}</svg>`;
}

export function categoryGlyphSvg(
    category: string, x: number, y: number, size: number, color: string,
): string {
    const markup = CATEGORY_SVG[category as Category] ?? CATEGORY_SVG.facility;
    return glyph(markup, x, y, size, color);
}

export function incidentGlyphSvg(
    kind: string, x: number, y: number, size: number, color: string,
): string {
    const markup = INCIDENT_SVG[kind as IncidentKindName] ?? INCIDENT_SVG.accident;
    return glyph(markup, x, y, size, color);
}
