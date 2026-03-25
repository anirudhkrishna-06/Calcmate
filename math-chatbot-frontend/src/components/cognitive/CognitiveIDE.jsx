import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
    CheckCircle2,
    Clock3,
    Loader2,
    Radio,
    Square,
    Upload,
    Wand2,
    XCircle,
} from 'lucide-react';

function formatTimer(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function MetricTile({ label, value, tone = 'slate' }) {
    const toneClasses = {
        slate: 'border-white/10 bg-white/6 text-slate-200',
        amber: 'border-amber-300/20 bg-amber-300/10 text-amber-100',
        emerald: 'border-emerald-300/20 bg-emerald-300/10 text-emerald-100',
    };

    return (
        <div className={`rounded-[22px] border px-4 py-4 shadow-[0_18px_45px_rgba(15,23,42,0.2)] ${toneClasses[tone] || toneClasses.slate}`}>
            <p className="text-[10px] font-semibold uppercase tracking-[0.26em] text-current/70">{label}</p>
            <div className="mt-2 font-mono text-[1.8rem] tracking-[0.16em]">{value}</div>
        </div>
    );
}

function OrbitalLoader({ isValidating }) {
    return (
        <div className="relative mx-auto h-28 w-28">
            <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: isValidating ? 1.2 : 3.8, ease: 'linear' }}
                className="absolute inset-0 rounded-full border border-dashed border-white/20"
            />
            <motion.div
                animate={{ scale: [1, 1.04, 1], opacity: [0.65, 1, 0.65] }}
                transition={{ repeat: Infinity, duration: 2 }}
                className="absolute inset-[14px] rounded-full bg-gradient-to-br from-amber-300/35 via-rose-300/20 to-sky-300/20 blur-xl"
            />
            <div className="absolute inset-[22px] flex items-center justify-center rounded-full border border-white/12 bg-slate-950/72">
                {isValidating ? <Loader2 className="animate-spin text-amber-200" size={24} /> : <Upload className="text-amber-200" size={24} />}
            </div>
        </div>
    );
}

function ThinkingPulse({ active = false }) {
    return (
        <div className="relative mx-auto h-24 w-24">
            <motion.div
                animate={{
                    scale: active ? [1, 1.08, 1] : [1, 1.03, 1],
                    opacity: [0.35, 0.7, 0.35],
                }}
                transition={{ repeat: Infinity, duration: active ? 1.8 : 2.8, ease: 'easeInOut' }}
                className="absolute inset-0 rounded-full bg-gradient-to-br from-amber-300/45 via-rose-300/25 to-sky-300/25 blur-xl"
            />
            <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: active ? 5.5 : 9, ease: 'linear' }}
                className="absolute inset-0 rounded-full border border-dashed border-white/20"
            />
            <motion.div
                animate={{ rotate: -360 }}
                transition={{ repeat: Infinity, duration: active ? 7 : 12, ease: 'linear' }}
                className="absolute inset-[10px] rounded-full border border-white/12"
            />
            <div className="absolute inset-[20px] rounded-full border border-white/12 bg-slate-950/72" />
        </div>
    );
}

export default function CognitiveIDE({
    uiStage,
    thinkingTimer,
    effectiveSolvingTimer,
    uploadGraceUsed,
    waveform,
    runtimeNote,
    answerResult,
    isValidating,
    isEndingSession,
    onStartThinking,
    onStartSolving,
    onEndSession,
    onUploadAnswer,
    onNextQuestion,
}) {
    const fileInputRef = React.useRef(null);

    const handleFileSelect = (event) => {
        const file = event.target.files?.[0];
        if (file && onUploadAnswer) {
            onUploadAnswer(file);
        }
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    return (
        <section className="relative overflow-hidden rounded-[26px] border border-slate-900/10 bg-[radial-gradient(circle_at_top,rgba(251,191,36,0.1),transparent_26%),linear-gradient(180deg,rgba(15,23,42,0.99),rgba(15,23,42,0.95))] p-4 text-white shadow-[0_26px_80px_rgba(15,23,42,0.3)] xl:min-h-[620px]">
            <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(148,163,184,0.08),transparent_34%,rgba(251,191,36,0.08)_100%)]" />
            <div className="relative flex h-full flex-col">
                <div className="mb-3 border-b border-white/10 pb-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-300">Math Session</p>
                    <h2 className="mt-2 text-[1.55rem] font-semibold tracking-tight text-white">Enter Thinking Session</h2>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                    <MetricTile label="Thinking Time" value={formatTimer(thinkingTimer)} tone="amber" />
                    <MetricTile label="Solving Time" value={formatTimer(effectiveSolvingTimer)} tone={uiStage === 'solving' || uiStage === 'question_done' ? 'emerald' : 'slate'} />
                </div>

                <div className="mt-4 flex flex-1 flex-col justify-center rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] px-5 py-5">
                    <AnimatePresence mode="wait">
                        {uiStage === 'pre_session' && (
                            <motion.div
                                key="pre"
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -12 }}
                                className="flex h-full flex-col items-center justify-center gap-5 text-center"
                            >
                                <div className="relative">
                                    <ThinkingPulse />
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <Radio className="text-amber-200" size={24} />
                                    </div>
                                </div>
                                {runtimeNote ? <p className="mt-5 max-w-md text-sm text-amber-200">{runtimeNote}</p> : null}
                                <button
                                    onClick={onStartThinking}
                                    className="inline-flex items-center gap-3 rounded-full bg-amber-300 px-8 py-3.5 text-sm font-semibold uppercase tracking-[0.22em] text-slate-950 transition hover:bg-amber-200"
                                >
                                    <Radio size={18} />
                                    Start Thinking
                                </button>
                            </motion.div>
                        )}

                        {uiStage === 'loading' && (
                            <motion.div
                                key="loading"
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -12 }}
                                className="flex h-full flex-col items-center justify-center text-center"
                            >
                                <OrbitalLoader isValidating />
                            </motion.div>
                        )}

                        {uiStage === 'thinking' && (
                            <motion.div
                                key="thinking"
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -12 }}
                                className="flex h-full w-full flex-col"
                            >
                                <div className="flex-1" />

                                <div className="flex items-center justify-center">
                                    <div className="w-full max-w-xl rounded-[24px] border border-white/8 bg-slate-950/24 px-5 py-5">
                                        <div className="flex h-28 items-end justify-center gap-2 rounded-[20px] border border-white/8 bg-white/5 px-5 py-6">
                                            {waveform.map((level, index) => (
                                                <motion.span
                                                    key={index}
                                                    animate={{ height: `${level}%`, opacity: level > 12 ? 1 : 0.28 }}
                                                    transition={{ duration: 0.18, ease: 'easeOut' }}
                                                    className="w-2 rounded-full bg-gradient-to-t from-amber-300 via-rose-300 to-sky-200"
                                                    style={{ minHeight: '12px' }}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex flex-1 items-end justify-center pb-1 pt-5">
                                    <div className="flex flex-wrap items-center justify-center gap-3">
                                    <button
                                        onClick={onStartSolving}
                                        className="inline-flex items-center gap-3 rounded-full bg-emerald-300 px-8 py-3.5 text-sm font-semibold uppercase tracking-[0.22em] text-slate-950 transition hover:bg-emerald-200"
                                    >
                                        <Clock3 size={18} />
                                        Start Solving
                                    </button>
                                    <button
                                        onClick={onEndSession}
                                        disabled={isEndingSession}
                                        className="inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/8 px-5 py-3 text-xs font-semibold uppercase tracking-[0.22em] text-slate-200 transition hover:bg-white/12 disabled:opacity-50"
                                    >
                                        <Square size={14} />
                                        End Session
                                    </button>
                                    </div>
                                </div>
                            </motion.div>
                        )}

                        {uiStage === 'solving' && (
                            <motion.div
                                key="solving"
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -12 }}
                                className="flex h-full flex-col items-center justify-center"
                            >
                                <OrbitalLoader isValidating={isValidating} />
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    onChange={handleFileSelect}
                                    accept="image/*"
                                    className="hidden"
                                />
                                <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                                    <button
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={isValidating || isEndingSession}
                                        className="inline-flex items-center gap-3 rounded-full bg-amber-300 px-8 py-3.5 text-sm font-semibold uppercase tracking-[0.22em] text-slate-950 transition hover:bg-amber-200 disabled:opacity-50"
                                    >
                                        {isValidating ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
                                        {isValidating ? 'Checking' : 'Upload Answer'}
                                    </button>
                                    <button
                                        onClick={onEndSession}
                                        disabled={isEndingSession}
                                        className="inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/8 px-5 py-3 text-xs font-semibold uppercase tracking-[0.22em] text-slate-200 transition hover:bg-white/12 disabled:opacity-50"
                                    >
                                        <Square size={14} />
                                        End Session
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {uiStage === 'question_done' && (
                            <motion.div
                                key="question_done"
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -12 }}
                                className="flex h-full flex-col items-center justify-center text-center"
                            >
                                <div className={`flex h-20 w-20 items-center justify-center rounded-[24px] border ${
                                    answerResult?.correct ? 'border-emerald-300/20 bg-emerald-300/10' : 'border-rose-300/20 bg-rose-300/10'
                                }`}>
                                    {answerResult?.correct ? <CheckCircle2 className="text-emerald-300" size={34} /> : <XCircle className="text-rose-300" size={34} />}
                                </div>
                                <div className="mt-5 w-full max-w-xl rounded-[24px] border border-white/10 bg-white/6 p-4 text-left">
                                    <p className={`text-base font-bold ${answerResult?.correct ? 'text-emerald-200' : 'text-rose-200'}`}>
                                        {answerResult?.correct ? 'Correct' : 'Wrong'}
                                    </p>
                                    <p className="mt-2 text-sm text-slate-200">Your answer: {answerResult?.extracted_answer || 'N/A'}</p>
                                    {!answerResult?.correct ? <p className="mt-1 text-sm text-slate-200">Expected: {answerResult?.expected_answer || 'N/A'}</p> : null}
                                    {answerResult?.explanation ? <p className="mt-3 text-xs leading-6 text-slate-300">{answerResult.explanation}</p> : null}
                                    <p className="mt-2 text-xs leading-6 text-slate-400">Upload grace used: {formatTimer(uploadGraceUsed)}</p>
                                </div>
                                <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                                    <button
                                        onClick={onNextQuestion}
                                        className="inline-flex items-center gap-3 rounded-full bg-amber-300 px-8 py-3.5 text-sm font-semibold uppercase tracking-[0.22em] text-slate-950 transition hover:bg-amber-200"
                                    >
                                        <Wand2 size={18} />
                                        Next Question
                                    </button>
                                    <button
                                        onClick={onEndSession}
                                        disabled={isEndingSession}
                                        className="inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/8 px-5 py-3 text-xs font-semibold uppercase tracking-[0.22em] text-slate-200 transition hover:bg-white/12 disabled:opacity-50"
                                    >
                                        <Square size={14} />
                                        End Session
                                    </button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </section>
    );
}
