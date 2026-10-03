import { CATEGORY_STYLES, type Category } from "./map/categories";
import { CategoryGlyph } from "./map/CategoryGlyph";

const ORDER: Category[] = [
    "medical",
    "police",
    "fire_station",
    "security",
    "administration",
    "student_services",
    "facility",
    "user",
];

export default function MapLegend() {
    return (
        <div
            aria-label="Map legend"
            className="rounded-2xl bg-white/90 px-3.5 py-3 shadow-lg ring-1 ring-black/5 backdrop-blur"
        >
            <p className="mb-2 text-[9.5px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Legend
            </p>
            <ul className="space-y-1.5">
                {ORDER.map((key) => {
                    const style = CATEGORY_STYLES[key];
                    return (
                        <li key={key} className="flex items-center gap-2.5">
                            <span
                                className="grid h-5 w-5 shrink-0 place-items-center rounded-full"
                                style={{ background: style.ring, color: style.color }}
                            >
                                <CategoryGlyph category={key} size={11} strokeWidth={2.4} />
                            </span>
                            <span className="text-[11.5px] font-medium text-slate-600">
                                {style.label}
                            </span>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}
