export type Category =
    | 'medical' | 'police' | 'fire_station' | 'security'
    | 'administration' | 'student_services' | 'facility' | 'user';

export interface CategoryStyle {
    color: string;
    ring: string;
    label: string;
    priority: number;
    emergency: boolean;
}

export const CATEGORY_STYLES: Record<Category, CategoryStyle> = {
    medical: {
        color: '#dc2626', ring: 'rgba(220,38,38,.28)',
        label: 'Medical', emergency: true, priority: 100,
    },
    police: {
        color: '#1d4ed8', ring: 'rgba(29,78,216,.28)',
        label: 'Police', emergency: true, priority: 90,
    },
    fire_station: {
        color: '#ea580c', ring: 'rgba(234,88,12,.28)',
        label: 'Fire', emergency: true, priority: 90,
    },
    security: {
        color: '#7c3aed', ring: 'rgba(124,58,237,.26)',
        label: 'Security', emergency: true, priority: 85,
    },
    administration: {
        color: '#0f766e', ring: 'rgba(15,118,110,.24)',
        label: 'Administration', emergency: false, priority: 45,
    },
    student_services: {
        color: '#b45309', ring: 'rgba(180,83,9,.24)',
        label: 'Student services', emergency: false, priority: 45,
    },
    facility: {
        color: '#475569', ring: 'rgba(71,85,105,.22)',
        label: 'Facility', emergency: false, priority: 10,
    },
    user: {
        color: '#2563eb', ring: 'rgba(37,99,235,.3)',
        label: 'You', emergency: false, priority: 1000,
    },
};

export function styleFor(category: string): CategoryStyle {
    return CATEGORY_STYLES[(category as Category)] ?? CATEGORY_STYLES.facility;
}

export function escapeHtml(value: unknown): string {
    return String(value ?? '').replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string
    ));
}
