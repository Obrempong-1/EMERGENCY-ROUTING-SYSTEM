import type { Role } from "./api";

export type Capability =
    | "report"
    | "resolve_incidents"
    | "add_places"
    | "edit_places"
    | "manage_roles";

const CAPABILITIES: Record<Role, readonly Capability[]> = {
    student: ["report"],
    security: ["report", "resolve_incidents"],
    mapper: ["report", "add_places"],
    admin: ["report", "resolve_incidents", "add_places", "edit_places", "manage_roles"],
};

export const ROLE_HELP: Record<Role, string> = {
    student: "Can report incidents.",
    security: "Can also resolve and override incident reports.",
    mapper: "Can also add new places to the map.",
    admin: "Can do everything, including roles and removing places.",
};

function heldRoles(value: Role | Role[] | null | undefined): Role[] {
    const held = Array.isArray(value) ? value : value ? [value] : [];
    const known = held.filter((role): role is Role => role in CAPABILITIES);
    if (!known.includes("student")) known.push("student");
    return (Object.keys(CAPABILITIES) as Role[]).filter((role) => known.includes(role));
}

export function can(
    value: Role | Role[] | null | undefined,
    capability: Capability,
): boolean {
    if (!value || (Array.isArray(value) && value.length === 0)) return false;
    return heldRoles(value).some((role) => CAPABILITIES[role].includes(capability));
}

export function holdsRole(
    value: Role | Role[] | null | undefined,
    required: Role,
): boolean {
    if (!value || (Array.isArray(value) && value.length === 0)) return false;
    return CAPABILITIES[required].every((capability) => can(value, capability));
}
