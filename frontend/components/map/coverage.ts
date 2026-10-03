import type { EmergencyCategory } from '@/lib/api';

const COLORS = ["#16a34a", "#eab308", "#f97316", "#dc2626", "#a21caf"];
const WEIGHTS = [4.5, 4, 3.5, 3, 3];

export type CoverageScope = 'all' | 'medical' | 'police' | 'fire_station';

export const COVERAGE_SCOPES: { key: CoverageScope; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'medical', label: 'Medical' },
    { key: 'police', label: 'Police' },
    { key: 'fire_station', label: 'Fire' },
];

export function scopeCategories(scope: CoverageScope): EmergencyCategory[] | undefined {
    return scope === 'all' ? undefined : [scope];
}

export function coverageColor(index: number): string {
    return COLORS[Math.min(index, COLORS.length - 1)];
}

export function coverageWeight(index: number): number {
    return WEIGHTS[Math.min(index, WEIGHTS.length - 1)];
}
