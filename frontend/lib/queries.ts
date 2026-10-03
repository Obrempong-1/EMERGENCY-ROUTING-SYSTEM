"use client";

import { useSyncExternalStore } from "react";
import {
    keepPreviousData,
    useMutation,
    useQuery,
    useQueryClient,
    type UseQueryResult,
} from "@tanstack/react-query";

import {
    api,
    FALLBACK_CONTACTS,
    type CategorySummary,
    type CoverageResponse,
    type EmergencyContact,
    type EmergencyCategory,
    type Facility,
    type NearestResult,
    type NewPlace,
    type ServiceBounds,
    type Incident,
    type IncidentKind,
    type IncidentKindInfo,
    type AdminStudent,
    type Role,
    type Student,
    type TrafficLevel,
    type TransportMode,
} from "./api";
import { supabase, supabaseConfigured } from "./supabase";

const COORD_PRECISION = 4;

function quantize(value: number): number {
    return Number(value.toFixed(COORD_PRECISION));
}

const queryKeys = {
    locations: ["locations"] as const,
    bounds: ["bounds"] as const,
    categories: ["categories"] as const,
    publicConfig: ["public-config"] as const,
    session: ["session"] as const,
    incidents: ["incidents"] as const,
    adminStudents: ["admin", "students"] as const,
    incidentQueue: ["incidents", "queue"] as const,
    nearest: (
        category: EmergencyCategory | null,
        lat: number | null,
        lon: number | null,
        mode: TransportMode,
        traffic: TrafficLevel,
        subtype: string | null,
    ) => ["nearest", category, lat, lon, mode, traffic, subtype] as const,
    coverage: (categories: EmergencyCategory[] | undefined, mode: TransportMode, traffic: TrafficLevel) =>
        ["coverage", categories ?? "all", mode, traffic] as const,
};

export function useLocations(): UseQueryResult<Facility[]> {
    return useQuery({ queryKey: queryKeys.locations, queryFn: api.getLocations });
}

export function useBounds(): UseQueryResult<ServiceBounds> {
    return useQuery({
        queryKey: queryKeys.bounds,
        queryFn: api.getBounds,
        staleTime: Infinity,
    });
}

export function useEmergencyContacts(): EmergencyContact[] {
    const query = useQuery({
        queryKey: queryKeys.publicConfig,
        queryFn: api.getPublicConfig,
        staleTime: Infinity,
        gcTime: Infinity,
    });
    return query.data?.emergency_contacts ?? FALLBACK_CONTACTS;
}

export function useCategories(): UseQueryResult<CategorySummary[]> {
    return useQuery({ queryKey: queryKeys.categories, queryFn: api.getCategories });
}

export function useNearest(
    category: EmergencyCategory | null,
    origin: { lat: number; lon: number } | null,
    transportMode: TransportMode,
    trafficLevel: TrafficLevel,
    subtype: string | null = null,
): UseQueryResult<NearestResult[]> {
    const lat = origin ? quantize(origin.lat) : null;
    const lon = origin ? quantize(origin.lon) : null;

    return useQuery({
        queryKey: queryKeys.nearest(category, lat, lon, transportMode, trafficLevel, subtype),
        enabled: Boolean(category && origin),
        staleTime: 60_000,
        queryFn: async ({ signal }) => {
            const data = await api.nearest({
                lat: lat!,
                lon: lon!,
                category: category!,
                transport_mode: transportMode,
                traffic_level: trafficLevel,
                limit: 5,
                subtype,
            }, signal);
            return data.results;
        },
    });
}

export function useCoverage(
    enabled: boolean,
    transportMode: TransportMode,
    trafficLevel: TrafficLevel,
    categories?: EmergencyCategory[],
): UseQueryResult<CoverageResponse> {
    return useQuery({
        queryKey: queryKeys.coverage(categories, transportMode, trafficLevel),
        enabled,
        staleTime: 10 * 60_000,
        placeholderData: keepPreviousData,
        queryFn: () => api.coverage({
            categories,
            transport_mode: transportMode,
            traffic_level: trafficLevel,
        }),
    });
}

export function useCreatePlace() {
    const client = useQueryClient();
    return useMutation({
        mutationFn: (place: NewPlace) => api.createPlace(place),
        onSuccess: () => {
            client.invalidateQueries({ queryKey: queryKeys.locations });
            client.invalidateQueries({ queryKey: queryKeys.categories });
            client.invalidateQueries({ queryKey: ["coverage"] });
            client.invalidateQueries({ queryKey: ["nearest"] });
        },
    });
}

function subscribeAuth(onChange: () => void): () => void {
    if (!supabaseConfigured) return () => {};
    const { data } = supabase().auth.onAuthStateChange(() => onChange());
    return () => data.subscription.unsubscribe();
}

let authEpoch = 0;
let lastUserId: string | null | undefined;

function authSnapshot(): number {
    return authEpoch;
}

if (supabaseConfigured && typeof window !== "undefined") {
    supabase().auth.onAuthStateChange((_event, session) => {
        const userId = session?.user?.id ?? null;
        if (userId !== lastUserId) {
            lastUserId = userId;
            authEpoch += 1;
        }
    });
}

export function useSession(): UseQueryResult<Student | null> {
    const epoch = useSyncExternalStore(subscribeAuth, authSnapshot, () => 0);
    return useQuery({
        queryKey: [...queryKeys.session, epoch],
        enabled: supabaseConfigured,
        staleTime: 5 * 60_000,
        retry: false,
        queryFn: async () => {
            const { data } = await supabase().auth.getSession();
            if (!data.session) return null;
            return (await api.me()).student;
        },
    });
}

export function useSignIn() {
    const client = useQueryClient();
    return useMutation({
        mutationFn: async ({ email, password }: { email: string; password: string }) => {
            const { error } = await supabase().auth.signInWithPassword({ email, password });
            if (error) throw error;
        },
        onSuccess: () => {
            client.invalidateQueries({ queryKey: queryKeys.session });
        },
    });
}

export function useSignUp() {
    const client = useQueryClient();
    return useMutation({
        mutationFn: async ({ email, password }: { email: string; password: string }) => {
            const { data, error } = await supabase().auth.signUp({
                email,
                password,
                options: typeof window === "undefined"
                    ? undefined
                    : { emailRedirectTo: window.location.origin },
            });
            if (error) throw error;
            return { needsConfirmation: data.session === null };
        },
        onSuccess: () => {
            client.invalidateQueries({ queryKey: queryKeys.session });
        },
    });
}

export function useResetPassword() {
    return useMutation({
        mutationFn: async (email: string) => {
            const { error } = await supabase().auth.resetPasswordForEmail(
                email,
                typeof window === "undefined"
                    ? undefined
                    : { redirectTo: window.location.origin },
            );
            if (error) throw error;
        },
    });
}

export function useLogout() {
    const client = useQueryClient();
    return useMutation({
        mutationFn: async () => {
            await supabase().auth.signOut();
        },
        onSettled: () => {
            client.removeQueries({ queryKey: queryKeys.session });
        },
    });
}

export function useIncidents(): UseQueryResult<{
    kinds: IncidentKindInfo[];
    incidents: Incident[];
}> {
    return useQuery({
        queryKey: queryKeys.incidents,
        queryFn: api.getIncidents,
        refetchInterval: 60_000,
        staleTime: 30_000,
        retry: false,
    });
}

export function useReportIncident() {
    const client = useQueryClient();
    return useMutation({
        mutationFn: (body: { kind: IncidentKind; lat: number; lon: number; note?: string }) =>
            api.reportIncident(body),
        onSuccess: () => {
            client.invalidateQueries({ queryKey: queryKeys.incidents });
        },
    });
}

export function useAdminStudents(enabled: boolean): UseQueryResult<AdminStudent[]> {
    return useQuery({
        queryKey: queryKeys.adminStudents,
        enabled,
        retry: false,
        queryFn: async () => (await api.adminStudents()).students,
    });
}

export function useSetRoles() {
    const client = useQueryClient();
    return useMutation({
        mutationFn: ({ id, roles }: { id: number; roles: Role[] }) =>
            api.adminSetRoles(id, roles),
        onSuccess: () => {
            client.invalidateQueries({ queryKey: queryKeys.adminStudents });
        },
    });
}

export function useIncidentQueue(enabled: boolean) {
    return useQuery({
        queryKey: queryKeys.incidentQueue,
        enabled,
        retry: false,
        queryFn: async () => (await api.incidentQueue()).incidents,
    });
}

export function useOverrideIncident() {
    const client = useQueryClient();
    return useMutation({
        mutationFn: ({ id, override }: { id: number; override: "verified" | "false" }) =>
            api.overrideIncident(id, override),
        onSuccess: () => {
            client.invalidateQueries({ queryKey: queryKeys.incidentQueue });
            client.invalidateQueries({ queryKey: queryKeys.incidents });
        },
    });
}

export function useResolveIncident() {
    const client = useQueryClient();
    return useMutation({
        mutationFn: (id: number) => api.resolveIncident(id),
        onSuccess: () => {
            client.invalidateQueries({ queryKey: queryKeys.incidentQueue });
            client.invalidateQueries({ queryKey: queryKeys.incidents });
        },
    });
}

export function useDeletePlace() {
    const client = useQueryClient();
    return useMutation({
        mutationFn: (id: string) => api.deletePlace(id),
        onSuccess: () => {
            client.invalidateQueries({ queryKey: queryKeys.locations });
            client.invalidateQueries({ queryKey: queryKeys.categories });
        },
    });
}

const MODE_LIST: TransportMode[] = ["drive", "bike", "walk"];

export function useModeEtas(
    origin: { lat: number; lon: number } | null,
    destination: { lat: number; lon: number } | null,
    trafficLevel: TrafficLevel,
): Record<TransportMode, number | null> {
    const lat = origin ? Number(origin.lat.toFixed(3)) : null;
    const lon = origin ? Number(origin.lon.toFixed(3)) : null;
    const dLat = destination ? Number(destination.lat.toFixed(4)) : null;
    const dLon = destination ? Number(destination.lon.toFixed(4)) : null;

    const query = useQuery({
        queryKey: ["mode-etas", lat, lon, dLat, dLon, trafficLevel],
        enabled: Boolean(origin && destination),
        staleTime: 60_000,
        retry: false,
        queryFn: async () => {
            const results = await Promise.all(MODE_LIST.map(async (mode) => {
                try {
                    const route = await api.calculateRoute({
                        origin_lat: lat!, origin_lon: lon!,
                        dest_lat: dLat!, dest_lon: dLon!,
                        transport_mode: mode, traffic_level: trafficLevel,
                    });
                    return [mode, route.time_min] as const;
                } catch {
                    return [mode, null] as const;
                }
            }));
            return Object.fromEntries(results) as Record<TransportMode, number | null>;
        },
    });

    return query.data ?? { drive: null, bike: null, walk: null };
}
