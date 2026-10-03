import { createElement } from "react";

import { categoryIcon, incidentIcon } from "./icons";

interface Props {
    category: string;
    size?: number;
    strokeWidth?: number;
    className?: string;
}

export function CategoryGlyph({ category, size = 16, strokeWidth = 2.1, className }: Props) {
    return createElement(categoryIcon(category), { size, strokeWidth, className });
}

export function IncidentGlyph({ category, size = 16, strokeWidth = 2.1, className }: Props) {
    return createElement(incidentIcon(category), { size, strokeWidth, className });
}
