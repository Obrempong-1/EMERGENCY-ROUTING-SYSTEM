import Link from "next/link";
import { ChevronRight } from "lucide-react";

export default function CreatorFooter() {
    return (
        <div className="p-4 bg-white border-t border-slate-100 shrink-0">
            <Link
                href="/creator"
                className="group block w-full bg-slate-50 hover:bg-blue-50 border border-slate-100 hover:border-blue-200 rounded-xl p-3 transition-all duration-300"
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-slate-200 overflow-hidden relative border border-white shadow-sm group-hover:scale-105 transition-transform">
                            <img src="/Obrempong.jpg" alt="Dev" className="w-full h-full object-cover" />
                        </div>
                        <div>
                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider group-hover:text-blue-500 transition-colors">Meet the Developer</p>
                            <p className="text-xs font-bold text-slate-800 leading-none mt-0.5">Obrempong Kwabena Osei-Wusu</p>
                        </div>
                    </div>
                    <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center shadow-sm text-slate-300 group-hover:text-blue-500 group-hover:translate-x-1 transition-all">
                        <ChevronRight size={14} />
                    </div>
                </div>
            </Link>
        </div>
    );
}
