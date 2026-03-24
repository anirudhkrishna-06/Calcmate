import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
    BrainCircuit,
    Camera,
    CheckCircle2,
    Loader2,
    Mic,
    MicOff,
    PauseCircle,
    Play,
    Radio,
    Square,
    XCircle,
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
        body: 'Upload your answer to validate, or view your session report.',
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
    interventionMessage,
    onStart,
    onToggleMic,
    onEndSession,
    onUploadAnswer,
    answerResult,
    isValidating,
}) {
    const copy = stateCopy[uiState];
    const isLoading = uiState === 'loading';
    const isActive = uiState === 'active';
    const fileInputRef = React.useRef(null);

    const micButtonLabel =
        micStatus === 'recording' ? 'Pause Listening' : micStatus === 'paused' ? 'Resume Listening' : 'Activate Microphone';

    const MicIcon = micStatus === 'recording' ? PauseCircle : micStatus === 'paused' ? Play : Mic;

    const handleFileSelect = (e) => {
        const file = e.target.files?.[0];
        if (file && onUploadAnswer) {
            onUploadAnswer(file);
        }
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

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

                                {/* Answer Upload Section */}
                                <div className="mt-8">
                                    <input
                                        type="file"
                                        ref={fileInputRef}
                                        onChange={handleFileSelect}
                                        accept="image/*"
                                        className="hidden"
                                    />
                                    {!answerResult && (
                                        <button
                                            onClick={() => fileInputRef.current?.click()}
                                            disabled={isValidating}
                                            className="inline-flex items-center gap-3 rounded-full border border-amber-300/40 bg-amber-300/10 px-6 py-3 text-sm font-semibold uppercase tracking-[0.22em] text-amber-200 transition hover:bg-amber-300/20 disabled:opacity-50"
                                        >
                                            {isValidating ? (
                                                <>
                                                    <Loader2 size={18} className="animate-spin" />
                                                    Validating...
                                                </>
                                            ) : (
                                                <>
                                                    <Camera size={18} />
                                                    Upload Answer
                                                </>
                                            )}
                                        </button>
                                    )}

                                    {/* Answer Result */}
                                    {answerResult && (
                                        <motion.div
                                            initial={{ opacity: 0, scale: 0.9 }}
                                            animate={{ opacity: 1, scale: 1 }}
                                            className={`mt-4 mx-auto max-w-sm rounded-2xl border p-5 ${
                                                answerResult.correct
                                                    ? 'border-emerald-300/30 bg-emerald-300/10'
                                                    : 'border-rose-300/30 bg-rose-300/10'
                                            }`}
                                        >
                                            <div className="flex items-center gap-3 justify-center">
                                                {answerResult.correct ? (
                                                    <CheckCircle2 size={28} className="text-emerald-300" />
                                                ) : (
                                                    <XCircle size={28} className="text-rose-300" />
                                                )}
                                                <span className={`text-lg font-bold ${answerResult.correct ? 'text-emerald-200' : 'text-rose-200'}`}>
                                                    {answerResult.correct ? 'Correct!' : 'Incorrect'}
                                                </span>
                                            </div>
                                            {answerResult.extracted_answer && (
                                                <p className="mt-3 text-sm text-slate-300">
                                                    Your answer: <span className="font-mono text-white">{answerResult.extracted_answer}</span>
                                                </p>
                                            )}
                                            {answerResult.expected_answer && !answerResult.correct && (
                                                <p className="mt-1 text-sm text-slate-300">
                                                    Expected: <span className="font-mono text-white">{answerResult.expected_answer}</span>
                                                </p>
                                            )}
                                        </motion.div>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Loading Overlay */}
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

            {/* Intervention Popup — floating Socratic prompt */}
            <AnimatePresence>
                {interventionMessage && (
                    <motion.div
                        key="intervention-popup"
                        initial={{ opacity: 0, y: 30, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 20, scale: 0.95 }}
                        transition={{ type: 'spring', damping: 20, stiffness: 300 }}
                        className="absolute inset-x-6 bottom-20 z-30 mx-auto max-w-md"
                    >
                        <div className="rounded-2xl border border-fuchsia-300/30 bg-fuchsia-950/80 px-6 py-5 shadow-[0_20px_60px_rgba(168,85,247,0.2)] backdrop-blur-lg">
                            <div className="flex items-start gap-3">
                                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-fuchsia-400/20">
                                    <BrainCircuit size={16} className="text-fuchsia-300" />
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-fuchsia-300/80">Cognitive Coach</p>
                                    <p className="mt-2 text-sm leading-6 text-white/90">{interventionMessage}</p>
                                </div>
                            </div>
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
