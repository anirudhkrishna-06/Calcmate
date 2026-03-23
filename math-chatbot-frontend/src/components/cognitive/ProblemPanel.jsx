import React from 'react';
import { motion } from 'framer-motion';

export default function ProblemPanel({ problemText }) {
    return (
        <aside className="relative overflow-hidden rounded-[28px] border border-slate-200/80 bg-white/88 p-6 shadow-[0_20px_70px_rgba(15,23,42,0.08)] backdrop-blur xl:h-[calc(100vh-3rem)]">
            <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-amber-50/90 via-white/0 to-transparent" />
            <div className="relative flex h-full flex-col">
                <div className="mb-6 border-b border-slate-200/80 pb-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">Problem Context</p>
                    <h2 className="mt-2 text-xl font-semibold text-slate-900">Reference Problem</h2>
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.45 }}
                    className="flex-1 overflow-y-auto pr-1"
                >
                    <div className="rounded-[24px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.96))] p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
                        <p className="text-[12px] font-semibold uppercase tracking-[0.26em] text-slate-400">Prompt</p>
                        <p className="mt-5 whitespace-pre-wrap font-serif text-[1.08rem] leading-8 text-slate-700 sm:text-[1.15rem]">
                            {problemText}
                        </p>
                    </div>
                </motion.div>
            </div>
        </aside>
    );
}
