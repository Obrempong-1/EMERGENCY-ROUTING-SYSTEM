"use client";

import Image from "next/image";
import Link from "next/link";
import dynamic from "next/dynamic";
import { ChevronLeft, Github, Linkedin, MapPin } from "lucide-react";
import programmerData from "../../public/Programmer.json";

const Lottie = dynamic(() => import("lottie-react"), { ssr: false });

export default function CreatorContent() {
    return (
        <main className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-blue-100 selection:text-blue-900">

            <nav className="fixed top-0 left-0 right-0 z-50 p-6 flex justify-between items-center pointer-events-none">
                <Link
                    href="/"
                    className="pointer-events-auto bg-white/80 backdrop-blur-md shadow-sm border border-slate-200 px-4 py-2 rounded-full flex items-center gap-2 text-sm font-bold text-slate-600 hover:text-slate-900 hover:shadow-md transition-all active:scale-95 group"
                >
                    <ChevronLeft size={16} className="group-hover:-translate-x-1 transition-transform" />
                    Back to Map
                </Link>
            </nav>

            <div className="max-w-7xl mx-auto pt-32 pb-20 px-6">

                <div className="bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden relative">

                    <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-bl from-blue-100/50 to-transparent rounded-bl-full -mr-20 -mt-20 blur-3xl opacity-60"></div>
                    <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-gradient-to-tr from-red-100/40 to-transparent rounded-tr-full -ml-20 -mb-20 blur-3xl opacity-60"></div>

                    <div className="relative z-10 md:flex items-stretch">
                        <div className="md:w-1/2 min-h-[400px] relative group overflow-hidden">
                            <div className="absolute inset-0 bg-slate-200 animate-pulse">
                            </div>
                            <Image
                                src="/Obrempong.jpg"
                                alt="Obrempong Kwabena Osei-Wusu"
                                fill
                                className="object-cover object-top transition duration-1000 group-hover:scale-105"
                                priority
                            />
                            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-60"></div>
                        </div>

                        <div className="md:w-1/2 p-10 md:p-14 flex flex-col justify-center relative">

                            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-600 text-[10px] font-bold tracking-widest uppercase w-fit mb-6">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                                Developer
                            </div>

                            <h1 className="text-4xl md:text-5xl font-black tracking-tight text-slate-900 mb-2 md:pr-36">
                                Obrempong Kwabena Osei-Wusu
                            </h1>
                            <p className="text-lg font-medium text-slate-500 mb-8">
                                Geomatic Engineering Student & Backend Engineer
                            </p>

                            <div className="space-y-6 text-slate-600 leading-relaxed">
                                <p>
                                    I describe myself as a hungry young man, totally out of his comfort zone, living his epic vision for Ghana, Africa, and the world at large.
                                </p>

                                <figure className="my-9 border-l-2 border-slate-900 pl-5 sm:pl-6">
                                    <blockquote className="text-xl font-medium leading-snug tracking-tight text-slate-900 sm:text-2xl">
                                        Outside death, every defeat is psychological
                                    </blockquote>
                                    <figcaption className="mt-3 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                                        Personal philosophy
                                    </figcaption>
                                </figure>
                                <p>
                                    Above all, I give thanks to <span className="font-bold text-slate-800">God</span>,
                                    the source of every good thing, for the strength, clarity and
                                    grace to see this work through.
                                </p>
                                <p>
                                    To <span className="font-bold text-slate-800">Dr. Kwame Obeng</span> your impact on my life serves as a constant reminder of the power of mentorship. Your profound wisdom, fatherly guidance, and unwavering belief in my potential have shaped not just my career, but the very content of my character. I am forever grateful for your presence in my life.
                                </p>
                            </div>

                            <div className="grid grid-cols-3 gap-4 mt-10 pt-10 border-t border-slate-100">
                                <div>
                                    <h3 className="text-2xl font-black text-slate-900">GIS</h3>
                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Mapping Analysis</p>
                                </div>
                                <div>
                                    <h3 className="text-2xl font-black text-slate-900">React</h3>
                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Frontend UI</p>
                                </div>
                                <div>
                                    <h3 className="text-2xl font-black text-slate-900">Python</h3>
                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Backend Logic</p>
                                </div>
                            </div>

                        </div>

                        <div className="absolute top-4 right-4 w-24 h-24 md:top-6 md:right-6 md:w-32 md:h-32 opacity-90 pointer-events-none z-50">
                            <Lottie animationData={programmerData} loop={true} className="w-full h-full" />
                        </div>
                    </div>
                </div>

                <div className="mt-8 grid md:grid-cols-2 gap-4">
                    <a
                        href="https://github.com/Obrempong-1/GIS-EMERGENCY-SYSTEM-"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bg-slate-900 text-white p-6 rounded-3xl flex items-center justify-between group hover:bg-slate-800 transition shadow-lg shadow-slate-200/50"
                    >
                        <div className="flex items-center gap-4">
                            <div className="p-3 bg-white/10 rounded-2xl group-hover:bg-white/20 transition">
                                <Github size={24} />
                            </div>
                            <div>
                                <h3 className="font-bold text-lg">GitHub</h3>
                                <p className="text-slate-400 text-sm">Check out my code</p>
                            </div>
                        </div>
                        <ChevronLeft size={20} className="rotate-180 text-slate-500 group-hover:translate-x-1 transition-transform" />
                    </a>

                    <a
                        href="https://www.linkedin.com/in/https://www.linkedin.com/in/obrempong-kwabena-osei-wusu-7b0217257/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bg-white text-slate-900 p-6 rounded-3xl border border-slate-200 flex items-center justify-between group hover:border-blue-200 hover:shadow-lg hover:shadow-blue-500/5 transition"
                    >
                        <div className="flex items-center gap-4">
                            <div className="p-3 bg-blue-50 text-blue-600 rounded-2xl group-hover:bg-blue-100 transition">
                                <Linkedin size={24} />
                            </div>
                            <div>
                                <h3 className="font-bold text-lg">LinkedIn</h3>
                                <p className="text-slate-400 text-sm">Connect professionally</p>
                            </div>
                        </div>
                        <ChevronLeft size={20} className="rotate-180 text-slate-300 group-hover:text-blue-500 group-hover:translate-x-1 transition-transform" />
                    </a>
                </div>

                <footer className="mt-20 text-center text-slate-400 text-sm font-medium">
                    <p className="flex items-center justify-center gap-2 opacity-60">
                        <MapPin size={14} />
                        Running from KNUST, Kumasi
                    </p>
                    <p className="mt-2 opacity-40">
                        © {new Date().getFullYear()} Obrempong Kwabena Osei-Wusu. All rights reserved.
                    </p>
                </footer>

            </div>
        </main>
    );
}
