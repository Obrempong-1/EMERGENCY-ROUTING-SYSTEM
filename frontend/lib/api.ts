import axios from 'axios';

import { accessToken } from './supabase';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api';

export type TransportMode = 'drive' | 'walk' | 'bike';
export type EmergencyCategory =
    | 'medical' | 'police' | 'fire_station'
    | 'security' | 'administration' | 'student_services';
export type TrafficLevel = 'low' | 'normal' | 'heavy';

type Objective = 'fastest' | 'shortest';

export interface MapMarker {
    id: string;
    name: string;
    type: string;
    category: string;
    lat: number;
    lon: number;
    phone?: string | null;
    opening_hours?: string | null;
    description?: string | null;
    on_campus?: boolean;
}

export interface Facility extends MapMarker {
    phone: string | null;
    opening_hours: string | null;
    description: string | null;
}

interface RouteRequest {
    origin_lat: number;
    origin_lon: number;
    dest_lat: number;
    dest_lon: number;
    objective?: Objective;
    transport_mode?: TransportMode;
    traffic_level?: TrafficLevel;
    destination_name?: string | null;
}

export interface RouteStep {
    text: string;
    kind: 'depart' | 'continue' | 'straight' | 'arrive' | 'uturn' | 'roundabout'
        | 'turn-left' | 'turn-right' | 'slight-left' | 'slight-right'
        | 'sharp-left' | 'sharp-right';
    distance_m: number;
    road: string;
}

export interface RouteResponse {
    objective: Objective;
    transport_mode: TransportMode;
    traffic_level: TrafficLevel;
    distance_km: number;
    time_min: number;
    path: [number, number][];
    instructions: RouteStep[];
    hazards?: RouteHazard[];
}

interface RouteHazard {
    id: number;
    kind: string;
    label: string;
    status: string;
}

export interface NearestResult extends Facility {
    time_min: number;
    distance_km: number;
}

interface SubtypeSummary {
    key: string;
    label: string;
    types: string[];
    count: number;
}

export interface CategorySummary {
    category: EmergencyCategory;
    label: string;
    count: number;
    subtypes: SubtypeSummary[];
}

interface CoverageBand {
    index: number;
    max_seconds: number | null;
    label: string;
    lines: [number, number][][];
}

export interface CoverageResponse {
    transport_mode: TransportMode;
    traffic_level: TrafficLevel;
    facility_count: number;
    unreachable_segments: number;
    bands: CoverageBand[];
}

export interface NewPlace {
    name: string;
    category: EmergencyCategory;
    lat: number;
    lon: number;
    description?: string | null;
}

export interface EmergencyContact {
    id: string;
    label: string;
    number: string;
    primary: boolean;
}

export const FALLBACK_CONTACTS: EmergencyContact[] = [
    { id: 'national', label: 'National emergency', number: '112', primary: true },
    { id: 'police', label: 'Police', number: '191', primary: false },
    { id: 'fire', label: 'Fire service', number: '192', primary: false },
    { id: 'ambulance', label: 'Ambulance', number: '193', primary: false },
];

export type Role = 'student' | 'security' | 'mapper' | 'admin';

export interface Student {
    id: number;
    email: string;
    trust: number;
    knust_verified: boolean;
    role: Role;
    roles: Role[];
    real_role?: Role;
    real_roles?: Role[];
}

export interface AdminStudent {
    id: number;
    email: string;
    role: Role;
    roles: Role[];
    trust: number;
    knust_verified: boolean;
    created_at: string;
    owner: boolean;
}

export type IncidentKind =
    | 'suspicious_activity' | 'accident' | 'flooding' | 'blocked_road';

type IncidentStatus =
    | 'unverified' | 'likely' | 'confirmed' | 'verified' | 'false';

export interface Incident {
    id: number;
    kind: IncidentKind;
    label: string;
    lat: number;
    lon: number;
    confidence: number;
    status: IncidentStatus;
    reports: number;
    created_at: string;
    expires_at: string;
    expires_in_minutes: number;
}

export interface IncidentKindInfo {
    kind: IncidentKind;
    label: string;
    ttl_hours: number;
}

export interface ReportedIncident extends Incident {
    counted: boolean;
    corroborated: boolean;
}

export interface ServiceBounds {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
}

const client = axios.create({ baseURL: API_BASE_URL, timeout: 20000 });

const ACTING_KEY = 'knust.acting-role';

function storedRole(): Role | null {
    if (typeof window === 'undefined') return null;
    try {
        return (window.sessionStorage.getItem(ACTING_KEY) as Role | null) ?? null;
    } catch {
        return null;
    }
}

let actingRole: Role | null = storedRole();

export function setActingRole(role: Role | null): void {
    actingRole = role;
    if (typeof window === 'undefined') return;
    try {
        if (role) window.sessionStorage.setItem(ACTING_KEY, role);
        else window.sessionStorage.removeItem(ACTING_KEY);
    } catch {
    }
}

client.interceptors.request.use(async (request) => {
    const token = await accessToken();
    if (token) request.headers.Authorization = `Bearer ${token}`;
    if (actingRole) request.headers['X-Acting-Role'] = actingRole;
    return request;
});

export function errorMessage(error: unknown, fallback = 'Could not reach the routing server.'): string {
    if (error && typeof error === 'object' && !axios.isAxiosError(error)) {
        const message = (error as { message?: unknown }).message;
        if (typeof message === 'string' && message.trim()) return message;
    }
    if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
        if (error.code === 'ECONNABORTED') return 'The routing server took too long to respond.';
        if (!error.response) return fallback;
        return `Routing server error (${error.response.status}).`;
    }
    return fallback;
}

export const api = {
    getBounds: async (): Promise<ServiceBounds> =>
        (await client.get('/bounds')).data,

    getLocations: async (): Promise<Facility[]> =>
        (await client.get('/locations')).data,

    calculateRoute: async (params: RouteRequest): Promise<RouteResponse> =>
        (await client.post('/route', params)).data,

    getCategories: async (): Promise<CategorySummary[]> =>
        (await client.get('/categories')).data,

    getPublicConfig: async (): Promise<{ emergency_contacts: EmergencyContact[] }> =>
        (await client.get('/config/public')).data,

    nearest: async (
        body: {
            lat: number;
            lon: number;
            category: EmergencyCategory;
            transport_mode?: TransportMode;
            traffic_level?: TrafficLevel;
            limit?: number;
            subtype?: string | null;
        },
        signal?: AbortSignal,
    ): Promise<{ category: EmergencyCategory; results: NearestResult[] }> =>
        (await client.post('/nearest', body, { signal })).data,

    coverage: async (body: {
        categories?: EmergencyCategory[];
        transport_mode?: TransportMode;
        traffic_level?: TrafficLevel;
    }): Promise<CoverageResponse> =>
        (await client.post('/coverage', body, { timeout: 60000 })).data,

    createPlace: async (body: NewPlace): Promise<{ place: Facility; drive_reachable: boolean }> =>
        (await client.post('/places', body)).data,

    me: async (): Promise<{ student: Student | null }> =>
        (await client.get('/auth/me')).data,

    adminStudents: async (): Promise<{ students: AdminStudent[] }> =>
        (await client.get('/admin/students')).data,

    adminSetRoles: async (id: number, roles: Role[]): Promise<AdminStudent> =>
        (await client.post(`/admin/students/${id}/role`, { roles })).data,

    incidentQueue: async (): Promise<{ incidents: (Incident & { live: boolean })[] }> =>
        (await client.get('/incidents/queue')).data,

    overrideIncident: async (id: number, override: 'verified' | 'false') =>
        (await client.post(`/incidents/${id}/override`, { override })).data,

    resolveIncident: async (id: number): Promise<void> => {
        await client.post(`/incidents/${id}/resolve`);
    },

    editPlace: async (id: string, changes: Partial<NewPlace>): Promise<unknown> =>
        (await client.patch(`/places/${id}`, changes)).data,

    deletePlace: async (id: string): Promise<void> => {
        await client.delete(`/places/${id}`);
    },

    getIncidents: async (): Promise<{ kinds: IncidentKindInfo[]; incidents: Incident[] }> =>
        (await client.get('/incidents')).data,

    reportIncident: async (body: {
        kind: IncidentKind;
        lat: number;
        lon: number;
        note?: string | null;
    }): Promise<ReportedIncident> => (await client.post('/incidents', body)).data,
};
