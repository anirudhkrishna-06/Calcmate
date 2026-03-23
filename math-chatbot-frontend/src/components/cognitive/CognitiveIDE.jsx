import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
    BrainCircuit,
    Loader2,
    Mic,
    MicOff,
    PauseCircle,
    Play,
    Radio,
    Square,
} from 'lucide-react';

const stateCopy = {
    pre_session: {
        eyebrow: 'Cognitive Runtime',
        title: 'Start Thinking',
        body: 'Think aloud. The system will follow your reasoning.',
    },
    loading: {
        eyebrow: 'Engine Startup',
        title: 'Initializing cognitive engine...',
        body: 'Preparing session state, problem context, and real-time tracing.',
    },
    active: {
        eyebrow: 'Live Session',
        title: 'Thinking in progress',
        body: 'Speak naturally. The engine is tracing how your reasoning evolves over time.',
    },
    completed: {
        eyebrow: 'Session Closed',
        title: 'Thinking session complete',
        body: 'The runtime has closed the session and preserved the cognitive trace for reporting.',
    },
};

function formatTimer(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export default function CognitiveIDE({
    uiState,
    timer,
    micStatus,
    statusText,
    waveform,
    sessionPhase,
    lifecycleState,
    runtimeNote,
    onStart,
    onToggleMic,
    onEndSession,
}) {
    const copy = stateCopy[uiState];
    const isLoading = uiState === 'loading';
    const isActive = uiState === 'active';

    const micButtonLabel =
        micStatus === 'recording' ? 'Pause Listening' : micStatus === 'paused' ? 'Resume Listening' : 'Activate Microphone';

    const MicIcon = micStatus === 'recording' ? PauseCircle : micStatus === 'paused' ? Play : Mic;

    return (
        <section className="relative overflow-hidden rounded-[32px] border border-slate-900/10 bg-[radial-gradient(circle_at_top,rgba(244,63,94,0.08),transparent_34%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(15,23,42,0.93))] p-6 text-white shadow-[0_30px_100px_rgba(15,23,42,0.35)] xl:h-[calc(100vh-3rem)]">
            <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(148,163,184,0.08),transparent_35%,rgba(250,204,21,0.08)_100%)]" />
            <div className="relative flex h-full flex-col">
                <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-4">
                    <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-slate-300">{copy.eyebrow}</p>
                        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">{copy.title}</h1>
                    </div>
                    <div className="rounded-full border border-white/12 bg-white/6 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-200">
                        {sessionPhase.replace('_', ' ')}
                    </div>
                </div>

                <div className="flex flex-1 flex-col items-center justify-center text-center">
                    <AnimatePresence mode="wait">
                        {uiState === 'pre_session' && (
                            <motion.div
                                key="pre"
                                initial={{ opacity: 0, y: 18 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -18 }}
                                className="w-full max-w-xl"
                            >
                                <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-[28px] border border-white/12 bg-white/6 shadow-[0_20px_50px_rgba(8,15,34,0.32)]">
                                    <BrainCircuit size={40} className="text-amber-300" />
                                </div>
                                <p className="mx-auto mt-6 max-w-md text-base leading-7 text-slate-300">{copy.body}</p>
                                {runtimeNote ? <p className="mx-auto mt-4 max-w-md text-sm leading-7 text-amber-200">{runtimeNote}</p> : null}
                                <button
                                    onClick={onStart}
                                    className="mt-10 inline-flex items-center gap-3 rounded-full bg-amber-300 px-8 py-4 text-sm font-semibold uppercase tracking-[0.26em] text-slate-950 transition hover:bg-amber-200"
                                >
                                    <Radio size={18} />
                                    Start Thinking
                                </button>
                            </motion.div>
                        )}

                        {uiState === 'active' && (
                            <motion.div
                                key="active"
                                initial={{ opacity: 0, y: 18 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -18 }}
                                className="flex w-full flex-1 flex-col items-center justify-center"
                            >
                                <div className="rounded-full border border-white/12 bg-white/6 px-6 py-3 font-mono text-4xl tracking-[0.22em] text-white shadow-[0_20px_60px_rgba(15,23,42,0.3)] sm:text-5xl">
                                    {formatTimer(timer)}
                                </div>

                                <div className="mt-10 flex h-28 w-full max-w-md items-end justify-center gap-2 rounded-[28px] border border-white/8 bg-white/5 px-6 py-8 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
                                    {waveform.map((level, index) => (
                                        <motion.span
                                            key={index}
                                            animate={{ height: `${level}%`, opacity: level > 12 ? 1 : 0.35 }}
                                            transition={{ duration: 0.18, ease: 'easeOut' }}
                                            className="w-2 rounded-full bg-gradient-to-t from-amber-300 via-rose-300 to-sky-200"
                                            style={{ minHeight: '12px' }}
                                        />
                                    ))}
                                </div>

                                <div className="mt-8 rounded-full border border-white/10 bg-white/6 px-5 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-slate-300">
                                    {statusText}
                                </div>

                                <button
                                    onClick={onToggleMic}
                                    className={`mt-10 inline-flex h-20 w-20 items-center justify-center rounded-full border text-white transition ${
                                        micStatus === 'recording'
                                            ? 'border-rose-300/70 bg-rose-400/16 shadow-[0_0_0_12px_rgba(251,113,133,0.12)]'
                                            : micStatus === 'paused'
                                              ? 'border-sky-300/50 bg-sky-300/14 shadow-[0_0_0_12px_rgba(125,211,252,0.1)]'
                                              : 'border-white/16 bg-white/10'
                                    }`}
                                    aria-label={micButtonLabel}
                                >
                                    <MicIcon size={28} />
                                </button>

                                <p className="mt-5 max-w-md text-sm leading-7 text-slate-300">{copy.body}</p>
                                <p className="mt-4 text-[11px] font-semibold uppercase tracking-[0.26em] text-slate-400">{micButtonLabel}</p>
                                <button
                                    onClick={onEndSession}
                                    className="mt-8 inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/8 px-5 py-3 text-xs font-semibold uppercase tracking-[0.24em] text-slate-200 transition hover:bg-white/12"
                                >
                                    <Square size={14} />
                                    End Session
                                </button>
                            </motion.div>
                        )}

                        {uiState === 'completed' && (
                            <motion.div
                                key="completed"
                                initial={{ opacity: 0, y: 18 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -18 }}
                                className="w-full max-w-xl"
                            >
                                <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-[28px] border border-emerald-300/20 bg-emerald-300/10 shadow-[0_20px_50px_rgba(8,15,34,0.32)]">
                                    <BrainCircuit size={40} className="text-emerald-300" />
                                </div>
                                <p className="mx-auto mt-6 max-w-md text-base leading-7 text-slate-300">{copy.body}</p>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            <AnimatePresence>
                {isLoading && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/74 backdrop-blur-sm"
                    >
                        <div className="flex max-w-sm flex-col items-center text-center">
                            <div className="flex h-20 w-20 items-center justify-center rounded-[24px] border border-white/10 bg-white/6">
                                <Loader2 size={34} className="animate-spin text-amber-300" />
                            </div>
                            <h2 className="mt-6 text-2xl font-semibold text-white">Initializing cognitive engine...</h2>
                            <p className="mt-3 text-sm leading-7 text-slate-300">{copy.body}</p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <div className="relative mt-4 flex items-center justify-between border-t border-white/10 pt-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">
                <span className="inline-flex items-center gap-2">
                    {micStatus === 'recording' ? <Mic size={14} /> : <MicOff size={14} />}
                    {micStatus}
                </span>
                <span>{lifecycleState.replace('_', ' ')}</span>
            </div>
        </section>
    );
}
