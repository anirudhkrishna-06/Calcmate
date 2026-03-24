import React from 'react';
import { motion } from 'framer-motion';
import {
    AlertTriangle,
    Brain,
    Compass,
    Gauge,
    Lightbulb,
    Sparkles,
    Target,
    Zap,
} from 'lucide-react';

const stateVisuals = {
    understanding: { icon: Brain, tone: 'border-sky-200 bg-sky-50 text-sky-700' },
    parameter: { icon: Compass, tone: 'border-cyan-200 bg-cyan-50 text-cyan-700' },
    strategy: { icon: Lightbulb, tone: 'border-amber-200 bg-amber-50 text-amber-700' },
    delay: { icon: Gauge, tone: 'border-orange-200 bg-orange-50 text-orange-700' },
    deviation: { icon: AlertTriangle, tone: 'border-rose-200 bg-rose-50 text-rose-700' },
    execution: { icon: Target, tone: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
    intervention: { icon: Sparkles, tone: 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700' },
    signal: { icon: Zap, tone: 'border-slate-200 bg-slate-50 text-slate-700' },
    system: { icon: Brain, tone: 'border-indigo-200 bg-indigo-50 text-indigo-700' },
};

function getProgressScore(validationState) {
    const progress = validationState?.progress_ratio || 0;
    return Math.round(progress * 100);
}

function getFocusScore(validationState) {
    const deviation = validationState?.deviation_score || 0;
    return Math.max(0, Math.round(100 - deviation * 100));
}

function getStabilityScore(validationState) {
    const oscillation = validationState?.oscillation_index || 0;
    return Math.max(0, Math.round(100 - oscillation * 100));
}

function getMomentumCopy({ uiStage, sessionPhase, statusText, interventionMessage }) {
    if (interventionMessage) {
        return {
            title: 'Tutor guidance active',
            body: interventionMessage,
        };
    }
    if (uiStage === 'pre_session') {
        return {
            title: 'Ready',
            body: 'This panel will summarize progress once the session begins.',
        };
    }
    if (uiStage === 'solving') {
        return {
            title: 'Silent solving mode',
            body: 'Your reasoning capture is paused. Focus on solving cleanly and upload the final answer when ready.',
        };
    }
    if (uiStage === 'question_done') {
        return {
            title: 'Question archived',
            body: 'Use the timers and answer check to decide whether to move to the next problem or close the session.',
        };
    }
    return {
        title: sessionPhase === 'strategy_selection' ? 'Strategy is forming' : 'Thinking is in motion',
        body: statusText || 'The system is watching how your current reasoning is evolving.',
    };
}

export default function TimelinePanel({
    events,
    validationState,
    sessionPhase,
    lifecycleState,
    statusText,
    uiStage,
    interventionMessage,
}) {
    const recentStates = events.slice(-3);
    const currentState = recentStates[recentStates.length - 1];
    const momentum = getMomentumCopy({ uiStage, sessionPhase, statusText, interventionMessage });
    const scores = [
        { label: 'Path Progress', value: getProgressScore(validationState), accent: 'bg-sky-500' },
        { label: 'Focus', value: getFocusScore(validationState), accent: 'bg-emerald-500' },
        { label: 'Stability', value: getStabilityScore(validationState), accent: 'bg-amber-500' },
    ];

    return (
        <aside className="grid gap-3 xl:min-h-[620px] xl:grid-rows-[0.88fr_1.12fr]">
            <section className="relative overflow-hidden rounded-[24px] border border-slate-200/80 bg-white/90 p-4 shadow-[0_20px_70px_rgba(15,23,42,0.08)] backdrop-blur">
                <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-sky-50/90 via-white/0 to-transparent" />
                <div className="relative flex h-full flex-col">
                    <div className="mb-4 border-b border-slate-200/80 pb-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">State Strip</p>
                        <h2 className="mt-2 text-lg font-semibold text-slate-900">Current reasoning state</h2>
                    </div>

                    <div className="flex-1 space-y-3">
                        {recentStates.length === 0 ? (
                            <div className="flex h-full min-h-[170px] items-center justify-center rounded-[24px] border border-dashed border-slate-200 bg-slate-50/80 p-8 text-center">
                                <div>
                                    <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-400">Awaiting first signal</p>
                                    <p className="mt-3 text-sm leading-7 text-slate-500">Once the session begins, this strip will keep just the last three learning states visible.</p>
                                </div>
                            </div>
                        ) : (
                            recentStates.map((event, index) => {
                                const visual = stateVisuals[event.type] || stateVisuals.signal;
                                const Icon = visual.icon;
                                const isCurrent = index === recentStates.length - 1;
                                return (
                                    <motion.div
                                        key={event.id}
                                        initial={{ opacity: 0, x: 16 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ duration: 0.22 }}
                                        className={`rounded-[22px] border p-4 transition ${isCurrent ? 'border-slate-900 bg-slate-900 text-white shadow-[0_18px_50px_rgba(15,23,42,0.16)]' : 'border-slate-200 bg-white text-slate-900'}`}
                                    >
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="flex items-center gap-3">
                                                <span className={`flex h-10 w-10 items-center justify-center rounded-2xl border ${isCurrent ? 'border-white/20 bg-white/10 text-white' : visual.tone}`}>
                                                    <Icon size={16} />
                                                </span>
                                                <div>
                                                    <p className="text-sm font-semibold">{event.title}</p>
                                                    <p className={`mt-1 text-xs ${isCurrent ? 'text-slate-300' : 'text-slate-500'}`}>{event.timeLabel}</p>
                                                </div>
                                            </div>
                                            {isCurrent && (
                                                <span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-100">
                                                    Live
                                                </span>
                                            )}
                                        </div>
                                    </motion.div>
                                );
                            })
                        )}
                    </div>
                </div>
            </section>

            <section className="relative overflow-hidden rounded-[24px] border border-slate-200/80 bg-white/90 p-4 shadow-[0_20px_70px_rgba(15,23,42,0.08)] backdrop-blur">
                <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-amber-50/90 via-white/0 to-transparent" />
                <div className="relative flex h-full flex-col">
                    <div className="mb-4 border-b border-slate-200/80 pb-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">Tutor Board</p>
                        <h2 className="mt-2 text-lg font-semibold text-slate-900">Learning guidance</h2>
                    </div>

                    <div className="grid gap-4">
                        <div className="grid gap-4 sm:grid-cols-3">
                            {scores.map((score) => (
                                <div key={score.label} className="rounded-[22px] border border-slate-200 bg-slate-50/70 p-4">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">{score.label}</p>
                                    <p className="mt-3 text-2xl font-black text-slate-900">{score.value}%</p>
                                    <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${score.value}%` }}
                                            transition={{ duration: 0.6 }}
                                            className={`h-full rounded-full ${score.accent}`}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="grid gap-4 sm:grid-cols-2">
                            <div className="rounded-[24px] border border-slate-200 bg-[linear-gradient(180deg,rgba(248,250,252,0.9),rgba(255,255,255,1))] p-5">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">Current Mode</p>
                                <p className="mt-3 text-lg font-semibold text-slate-900">{sessionPhase.replaceAll('_', ' ')}</p>
                                <p className="mt-2 text-sm leading-6 text-slate-500">Lifecycle: {lifecycleState}</p>
                                {currentState ? (
                                    <p className="mt-4 rounded-2xl bg-slate-900 px-4 py-3 text-sm leading-6 text-slate-100">
                                        Latest state: {currentState.title}
                                    </p>
                                ) : null}
                            </div>

                            <div className="rounded-[24px] border border-amber-200 bg-amber-50/70 p-5">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-700">Tutor Note</p>
                                <p className="mt-3 text-lg font-semibold text-slate-900">{momentum.title}</p>
                                <p className="mt-2 text-sm leading-7 text-slate-600">{momentum.body}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </aside>
    );
}
