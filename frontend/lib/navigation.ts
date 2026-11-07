import type { RouteResponse, RouteStep, TransportMode } from "./api";
import { bearingBetween, metresBetween } from "./geo";

interface Coords {
    lat: number;
    lon: number;
}

export interface Progress {
    along: number;
    offRoute: number;
    nextIndex: number;
    toNext: number;
    remaining: number;
}

export interface Cue {
    id: string;
    stage: number;
    text: string;
}

const STAGE = { continue: 0, early: 1, soon: 2, now: 3 } as const;

interface Thresholds {
    early: number;
    soon: number;
    now: number;
    then: number;
    offRoute: number;
}

export const THRESHOLDS: Record<TransportMode, Thresholds> = {
    drive: { early: 600, soon: 200, now: 50, then: 80, offRoute: 40 },
    bike: { early: 300, soon: 100, now: 30, then: 40, offRoute: 30 },
    walk: { early: 150, soon: 60, now: 20, then: 25, offRoute: 25 },
};

const PASSED_M = 10;
const BACKTRACK_FREE_M = 5;
const BACKTRACK_COST = 0.5;
const LOOKAHEAD_FREE_M = 30;
const LOOKAHEAD_COST = 0.1;
const AGAINST_TRAVEL_DEG = 100;
const AGAINST_TRAVEL_COST_M = 25;

const EARTH_RADIUS_M = 6_371_000;
const RAD = Math.PI / 180;

export function cumulative(path: [number, number][]): number[] {
    const along = [0];
    for (let i = 1; i < path.length; i += 1) {
        const [lat1, lon1] = path[i - 1];
        const [lat2, lon2] = path[i];
        along.push(along[i - 1] + metresBetween({ lat: lat1, lon: lon1 }, { lat: lat2, lon: lon2 }));
    }
    return along;
}

/**
 * Where the traveller is along the route line.
 *
 * A route can pass the same road twice (out and back after a U-turn), so the
 * nearest piece of line is not enough on its own: candidates are charged a
 * little for lying behind the last known position or well ahead of it, which
 * keeps the position moving forward along the route rather than jumping legs.
 * With the direction of travel known, a piece of line running against it is
 * charged too, which separates two passes through the same junction.
 */
function locate(
    path: [number, number][],
    along: number[],
    here: Coords,
    hint: number,
    heading: number | null = null,
): { along: number; offRoute: number } {
    if (path.length === 1) {
        return { along: 0, offRoute: metresBetween(here, { lat: path[0][0], lon: path[0][1] }) };
    }
    const scale = Math.cos(here.lat * RAD) * RAD * EARTH_RADIUS_M;
    const toXY = ([lat, lon]: [number, number]) =>
        [(lon - here.lon) * scale, (lat - here.lat) * RAD * EARTH_RADIUS_M] as const;

    let best = { along: 0, offRoute: Infinity, cost: Infinity };
    for (let i = 0; i < path.length - 1; i += 1) {
        const [ax, ay] = toXY(path[i]);
        const [bx, by] = toXY(path[i + 1]);
        const dx = bx - ax;
        const dy = by - ay;
        const lengthSq = dx * dx + dy * dy;
        const t = lengthSq === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / lengthSq));
        const px = ax + dx * t;
        const py = ay + dy * t;
        const offRoute = Math.hypot(px, py);
        const position = along[i] + (along[i + 1] - along[i]) * t;
        const behind = Math.max(0, hint - position - BACKTRACK_FREE_M);
        const ahead = Math.max(0, position - hint - LOOKAHEAD_FREE_M);
        let cost = offRoute + behind * BACKTRACK_COST + ahead * LOOKAHEAD_COST;
        if (heading !== null && lengthSq > 0) {
            const direction = bearingBetween(
                { lat: path[i][0], lon: path[i][1] }, { lat: path[i + 1][0], lon: path[i + 1][1] });
            const difference = Math.abs(((direction - heading + 540) % 360) - 180);
            if (difference > AGAINST_TRAVEL_DEG) cost += AGAINST_TRAVEL_COST_M;
        }
        if (cost < best.cost) best = { along: position, offRoute, cost };
    }
    return { along: best.along, offRoute: best.offRoute };
}

export function progress(
    route: RouteResponse,
    along: number[],
    here: Coords,
    hint: number,
    heading: number | null = null,
): Progress {
    const found = locate(route.path, along, here, hint, heading);
    const steps = route.instructions;
    let nextIndex = steps.findIndex((step, index) => {
        const following = steps[index + 1];
        const margin = following ? Math.min(PASSED_M, (following.at_m - step.at_m) / 2) : PASSED_M;
        return step.at_m + margin > found.along;
    });
    if (nextIndex === -1) nextIndex = steps.length - 1;
    const total = along[along.length - 1] ?? 0;
    return {
        along: found.along,
        offRoute: found.offRoute,
        nextIndex,
        toNext: Math.max(0, (steps[nextIndex]?.at_m ?? total) - found.along),
        remaining: Math.max(0, total - found.along),
    };
}

export function actionOf(step: RouteStep | undefined): string {
    if (!step) return "";
    return step.text.replace(/\s+for\s+[\d.]+\s*k?m$/i, "");
}

function spokenDistance(metres: number, mode: TransportMode): string {
    if (metres >= 1000) {
        const km = (metres / 1000).toFixed(1);
        return `${km} kilometre${km === "1.0" ? "" : "s"}`;
    }
    const unit = mode === "drive" && metres >= 100 ? 50 : 10;
    const rounded = Math.max(unit, Math.round(metres / unit) * unit);
    return `${rounded} metres`;
}

function lowerFirst(text: string): string {
    return text.charAt(0).toLowerCase() + text.slice(1);
}

function identity(step: RouteStep): string {
    const [lat, lon] = step.location;
    return `${step.kind}@${lat.toFixed(5)},${lon.toFixed(5)}`;
}

/**
 * What to say now, if anything, about the next manoeuvre.
 *
 * A manoeuvre is announced in stages: early notice, a reminder as it gets
 * close, and the instruction itself at the turn. The stage, not the exact
 * distance, identifies a cue, so nothing is repeated just because the traveller
 * moved, and a listener plays each stage at most once and never an earlier one
 * after a later one. A road-name change with no turn is only said at the point
 * itself. When the next manoeuvre follows quickly, the final instruction warns
 * of it too.
 */
export function cueFor(
    route: RouteResponse,
    state: Progress,
    mode: TransportMode,
): Cue | null {
    const limits = THRESHOLDS[mode];
    if (state.offRoute > limits.offRoute) return null;

    const steps = route.instructions;
    const step = steps[state.nextIndex];
    if (!step) return null;
    const action = actionOf(step);
    const distance = state.toNext;
    const id = identity(step);

    if (distance <= limits.now) {
        if (step.kind === "arrive") {
            return { id, stage: STAGE.now, text: action.replace(/^Arrive at/, "You have arrived at") };
        }
        const following = steps[state.nextIndex + 1];
        const close = following && following.at_m - step.at_m <= limits.then;
        const text = close ? `${action}, then ${lowerFirst(actionOf(following))}` : action;
        return { id, stage: STAGE.now, text };
    }

    if (step.kind === "continue" || step.kind === "straight") return null;

    const notice = `In ${spokenDistance(distance, mode)}, ${lowerFirst(action)}`;
    if (distance <= limits.soon) return { id, stage: STAGE.soon, text: notice };
    if (distance <= limits.early) return { id, stage: STAGE.early, text: notice };

    const road = steps[state.nextIndex - 1]?.road;
    return {
        id,
        stage: STAGE.continue,
        text: road
            ? `Continue on ${road} for ${spokenDistance(distance, mode)}`
            : `Continue for ${spokenDistance(distance, mode)}`,
    };
}
