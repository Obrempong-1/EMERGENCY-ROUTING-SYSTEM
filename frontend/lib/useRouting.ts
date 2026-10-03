"use client";

import { useCallback, useReducer } from "react";

import {
    api,
    errorMessage,
    type RouteResponse,
    type TrafficLevel,
    type TransportMode,
} from "./api";

interface Coords {
    lat: number;
    lon: number;
}

interface Destination extends Coords {
    name?: string;
}

interface RoutingState {
    destinationId: string;
    route: RouteResponse | null;
    computedAt: number | null;
    loading: boolean;
    error: string;
}

type Action =
    | { type: "choose"; id: string }
    | { type: "start" }
    | { type: "resolved"; route: RouteResponse; at: number }
    | { type: "failed"; message: string }
    | { type: "message"; message: string }
    | { type: "dismiss" }
    | { type: "clear" };

const INITIAL: RoutingState = {
    destinationId: "",
    route: null,
    computedAt: null,
    loading: false,
    error: "",
};

function reducer(state: RoutingState, action: Action): RoutingState {
    switch (action.type) {
        case "choose":
            return action.id === state.destinationId
                ? state
                : { ...INITIAL, destinationId: action.id };
        case "start":
            return { ...state, loading: true, route: null, computedAt: null, error: "" };
        case "resolved":
            return { ...state, loading: false, route: action.route, computedAt: action.at };
        case "failed":
            return { ...state, loading: false, error: action.message };
        case "message":
            return { ...state, error: action.message };
        case "dismiss":
            return { ...state, route: null, computedAt: null };
        case "clear":
            return INITIAL;
    }
}

export function useRouting(transportMode: TransportMode, trafficLevel: TrafficLevel) {
    const [state, dispatch] = useReducer(reducer, INITIAL);

    const plan = useCallback(async (
        start: Coords,
        destination: Destination,
        silent = false,
    ) => {
        if (!silent) dispatch({ type: "start" });
        try {
            const data = await api.calculateRoute({
                origin_lat: start.lat,
                origin_lon: start.lon,
                dest_lat: destination.lat,
                dest_lon: destination.lon,
                objective: "fastest",
                transport_mode: transportMode,
                traffic_level: trafficLevel,
                destination_name: destination.name ?? null,
            });
            dispatch({ type: "resolved", route: data, at: Date.now() });
        } catch (err) {
            dispatch({ type: "failed", message: errorMessage(err) });
        }
    }, [transportMode, trafficLevel]);

    const choose = useCallback((id: string) => dispatch({ type: "choose", id }), []);
    const dismiss = useCallback(() => dispatch({ type: "dismiss" }), []);
    const clear = useCallback(() => dispatch({ type: "clear" }), []);
    const fail = useCallback(
        (message: string) => dispatch({ type: "message", message }), []);

    return { ...state, plan, choose, dismiss, clear, fail };
}
