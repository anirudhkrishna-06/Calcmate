import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
    AlertTriangle,
    Brain,
    Compass,
    Gauge,
    Lightbulb,
    Play,
    Sparkles,
    Zap,
} from 'lucide-react';

const iconMap = {
    understanding: Brain,
    parameter: Compass,
    strategy: Lightbulb,
    delay: Gauge,
    deviation: AlertTriangle,
    execution: Play,
    intervention: Sparkles,
    signal: Zap,
    system: Brain,
};

const styleMap = {
    understanding: 'border-sky-200 bg-sky-50 text-sky-700',
    parameter: 'border-cyan-200 bg-cyan-50 text-cyan-700',
    strategy: 'border-amber-200 bg-amber-50 text-amber-700',
    delay: 'border-orange-200 bg-orange-50 text-orange-700',
    deviation: 'border-rose-200 bg-rose-50 text-rose-700',
    execution: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    intervention: 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700',
    signal: 'border-slate-200 bg-slate-50 text-slate-700',
    system: 'border-indigo-200 bg-indigo-50 text-indigo-700',
};

export default function TimelinePanel({ events }) {
    return (
        <aside className="relative overflow-hidden rounded-[28px] border border-slate-200/80 bg-white/88 p-6 shadow-[0_20px_70px_rgba(15,23,42,0.08)] backdrop-blur xl:h-[calc(100vh-3rem)]">
            <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-sky-50/90 via-white/0 to-transparent" />
            <div className="relative flex h-full flex-col">
                <div className="mb-6 border-b border-slate-200/80 pb-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">Cognitive Timeline</p>
                    <h2 className="mt-2 text-xl font-semibold text-slate-900">Live observations</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-500">The engine translates thinking activity into a readable sequence of cognitive milestones.</p>
                </div>

                <div className="flex-1 overflow-y-auto pr-1">
                    {events.length === 0 ? (
                        <div className="flex h-full min-h-[280px] items-center justify-center rounded-[24px] border border-dashed border-slate-200 bg-slate-50/80 p-8 text-center">
                            <div>
                                <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-400">Awaiting signal</p>
                                <p className="mt-3 text-sm leading-7 text-slate-500">Cognitive milestones will appear here as the system detects understanding, strategy shifts, and execution flow.</p>
                            </div>
                        </div>
                    ) : (
                        <div className="relative pl-6">
                            <div className="absolute left-[11px] top-0 h-full w-px bg-gradient-to-b from-sky-200 via-slate-200 to-transparent" />
                            <AnimatePresence initial={false}>
                                {events.map((event) => {
                                    const Icon = iconMap[event.type] || Brain;
                                    const tone = styleMap[event.type] || 'border-slate-200 bg-slate-50 text-slate-700';
                                    return (
                                        <motion.div
                                            key={event.id}
                                            initial={{ opacity: 0, x: 18 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            exit={{ opacity: 0, x: -18 }}
                                            transition={{ duration: 0.28 }}
                                            className="relative mb-4"
                                        >
                                            <span className={`absolute -left-6 top-5 flex h-6 w-6 items-center justify-center rounded-full border ${tone}`}>
                                                <Icon size={13} />
                                            </span>
                                            <div className="rounded-[22px] border border-slate-200/80 bg-white p-4 shadow-[0_18px_40px_rgba(15,23,42,0.05)]">
                                                <div className="flex items-center justify-between gap-4">
                                                    <h3 className="text-sm font-semibold text-slate-900">{event.title}</h3>
                                                    <span className="font-mono text-xs text-slate-400">{event.timeLabel}</span>
                                                </div>
                                                {event.detail && (
                                                    <p className="mt-2 text-[13px] leading-6 text-slate-500 italic">{event.detail}</p>
                                                )}
                                            </div>
                                        </motion.div>
                                    );
                                })}
                            </AnimatePresence>
                        </div>
                    )}
                </div>
            </div>
        </aside>
    );
}
