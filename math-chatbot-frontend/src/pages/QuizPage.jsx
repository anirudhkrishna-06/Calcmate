import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Brain, CheckCircle2, XCircle, ArrowRight, BarChart2,
    Loader2, Lightbulb, RefreshCw, Trophy, Target, Zap
} from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';

const API_BASE = 'http://localhost:8000';

// ─── Topic label formatter ───────────────────────────────────────────────────
const formatTopic = (t) =>
    t.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

// ─── Mastery bar ─────────────────────────────────────────────────────────────
function MasteryBar({ mastery, label }) {
    const pct = Math.round(mastery * 100);
    const color =
        pct < 40 ? 'bg-red-400' : pct < 70 ? 'bg-yellow-400' : 'bg-emerald-400';
    return (
        <div className="space-y-1">
            <div className="flex justify-between text-xs text-gray-500">
                <span className="truncate max-w-[160px]">{formatTopic(label)}</span>
                <span className="font-semibold text-gray-700">{pct}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                    className={`h-full rounded-full ${color}`}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.7, ease: 'easeOut' }}
                />
            </div>
        </div>
    );
}

// ─── Result badge ─────────────────────────────────────────────────────────────
function ResultBadge({ correct }) {
    return correct ? (
        <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="flex items-center gap-1.5 text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-1.5 text-sm font-medium"
        >
            <CheckCircle2 size={16} /> Correct!
        </motion.div>
    ) : (
        <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="flex items-center gap-1.5 text-red-500 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5 text-sm font-medium"
        >
            <XCircle size={16} /> Incorrect
        </motion.div>
    );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function QuizPage() {
    // ── State ────────────────────────────────────────────────────────────────
    const [view, setView] = useState('start'); // start | quiz | result | dashboard
    const [batchSize, setBatchSize] = useState(5);
    const [sessionId, setSessionId] = useState(null);

    const [questions, setQuestions] = useState([]); // [{topic, question, solution, ground_truth}]
    const [qIndex, setQIndex] = useState(0);

    const [answer, setAnswer] = useState('');
    const [submitted, setSubmitted] = useState(false);
    const [lastResult, setLastResult] = useState(null); // {correct, solution}
    const [batchScore, setBatchScore] = useState(0);

    const [stats, setStats] = useState(null); // mastery per topic
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const inputRef = useRef(null);

    // ── Focus input when new question loads ─────────────────────────────────
    useEffect(() => {
        if (view === 'quiz' && !submitted && inputRef.current) {
            inputRef.current.focus();
        }
    }, [qIndex, submitted, view]);

    // ── Start session ─────────────────────────────────────────────────────────
    const startSession = async () => {
        setLoading(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE}/quiz/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ batch_size: batchSize }),
            });
            if (!res.ok) throw new Error('Failed to start quiz session');
            const data = await res.json();
            setSessionId(data.session_id);
            setQuestions(data.questions);
            setQIndex(0);
            setBatchScore(0);
            setAnswer('');
            setSubmitted(false);
            setLastResult(null);
            setView('quiz');
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    // ── Submit answer ─────────────────────────────────────────────────────────
    const submitAnswer = async () => {
        if (!answer.trim() || submitted) return;
        setLoading(true);
        try {
            const currentQ = questions[qIndex];
            const res = await fetch(`${API_BASE}/quiz/answer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    question_index: qIndex,
                    answer: answer.trim(),
                    topic: currentQ.topic,
                    ground_truth: currentQ.ground_truth,
                }),
            });
            if (!res.ok) throw new Error('Grading failed');
            const data = await res.json();
            setLastResult(data);
            setSubmitted(true);
            if (data.correct) setBatchScore((s) => s + 1);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    // ── Next question or finish ───────────────────────────────────────────────
    const nextQuestion = () => {
        if (qIndex + 1 < questions.length) {
            setQIndex((i) => i + 1);
            setAnswer('');
            setSubmitted(false);
            setLastResult(null);
        } else {
            fetchStats();
            setView('result');
        }
    };

    // ── Fetch mastery stats ───────────────────────────────────────────────────
    const fetchStats = async () => {
        try {
            const res = await fetch(`${API_BASE}/quiz/stats`);
            if (res.ok) setStats(await res.json());
        } catch (_) {}
    };

    // ── Key handler ───────────────────────────────────────────────────────────
    const handleKey = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!submitted) submitAnswer();
            else nextQuestion();
        }
    };

    const currentQ = questions[qIndex];
    const progress = questions.length ? ((qIndex + (submitted ? 1 : 0)) / questions.length) * 100 : 0;

    // ═════════════════════════════════════════════════════════════════════════
    // VIEWS
    // ═════════════════════════════════════════════════════════════════════════

    // ── Start screen ─────────────────────────────────────────────────────────
    if (view === 'start') return (
        <div className="min-h-screen bg-gray-50">
            <Navbar />
            <PageTransition>
                <div className="max-w-xl mx-auto px-4 py-16">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8"
                    >
                        {/* Icon */}
                        <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mb-6">
                            <Brain size={32} className="text-blue-600" />
                        </div>

                        <h1 className="text-2xl font-bold text-gray-900 mb-2">
                            Adaptive Quiz
                        </h1>
                        <p className="text-gray-500 text-sm mb-8 leading-relaxed">
                            Our AI tracks your strengths and weak spots in real time using
                            Bayesian learning — spending more time where you need it most.
                        </p>

                        {/* Feature pills */}
                        <div className="flex flex-wrap gap-2 mb-8">
                            {[
                                { icon: Target, label: 'Targets weak spots' },
                                { icon: Zap,    label: 'Instant feedback' },
                                { icon: BarChart2, label: 'Tracks mastery' },
                            ].map(({ icon: Icon, label }) => (
                                <div key={label} className="flex items-center gap-1.5 bg-blue-50 text-blue-700 text-xs font-medium px-3 py-1.5 rounded-full">
                                    <Icon size={12} />
                                    {label}
                                </div>
                            ))}
                        </div>

                        {/* Batch size picker */}
                        <div className="mb-6">
                            <label className="block text-sm font-medium text-gray-700 mb-3">
                                Questions per session
                            </label>
                            <div className="flex gap-2">
                                {[3, 5, 8, 10].map((n) => (
                                    <button
                                        key={n}
                                        onClick={() => setBatchSize(n)}
                                        className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border transition-all ${
                                            batchSize === n
                                                ? 'bg-blue-600 text-white border-blue-600'
                                                : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300 hover:text-blue-600'
                                        }`}
                                    >
                                        {n}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {error && (
                            <p className="text-red-500 text-sm mb-4 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
                        )}

                        <button
                            onClick={startSession}
                            disabled={loading}
                            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors disabled:opacity-60"
                        >
                            {loading ? <Loader2 size={18} className="animate-spin" /> : <Brain size={18} />}
                            {loading ? 'Starting…' : 'Start Quiz'}
                        </button>
                    </motion.div>
                </div>
            </PageTransition>
        </div>
    );

    // ── Quiz screen ───────────────────────────────────────────────────────────
    if (view === 'quiz' && currentQ) return (
        <div className="min-h-screen bg-gray-50">
            <Navbar />
            <PageTransition>
                <div className="max-w-2xl mx-auto px-4 py-10">

                    {/* Progress bar */}
                    <div className="mb-6">
                        <div className="flex justify-between text-xs text-gray-400 mb-1.5">
                            <span>Question {qIndex + 1} of {questions.length}</span>
                            <span className="font-medium text-blue-600">{formatTopic(currentQ.topic)}</span>
                        </div>
                        <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                            <motion.div
                                className="h-full bg-blue-600 rounded-full"
                                animate={{ width: `${progress}%` }}
                                transition={{ duration: 0.4 }}
                            />
                        </div>
                    </div>

                    {/* Question card */}
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={qIndex}
                            initial={{ opacity: 0, x: 30 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -30 }}
                            transition={{ duration: 0.25 }}
                            className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-4"
                        >
                            {/* Topic badge */}
                            <div className="inline-flex items-center gap-1.5 bg-blue-50 text-blue-700 text-xs font-semibold px-2.5 py-1 rounded-lg mb-4">
                                <Brain size={12} />
                                {formatTopic(currentQ.topic)}
                            </div>

                            <p className="text-gray-800 text-base font-medium leading-relaxed mb-6">
                                {currentQ.question}
                            </p>

                            {/* Answer input */}
                            <textarea
                                ref={inputRef}
                                value={answer}
                                onChange={(e) => setAnswer(e.target.value)}
                                onKeyDown={handleKey}
                                disabled={submitted || loading}
                                placeholder="Type your answer here… (press Enter to submit)"
                                rows={2}
                                className="w-full resize-none border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500 transition"
                            />

                            {/* Submit / Next button */}
                            <div className="flex items-center justify-between mt-4">
                                <div>
                                    {submitted && lastResult && (
                                        <ResultBadge correct={lastResult.correct} />
                                    )}
                                </div>

                                {!submitted ? (
                                    <button
                                        onClick={submitAnswer}
                                        disabled={!answer.trim() || loading}
                                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors disabled:opacity-50"
                                    >
                                        {loading ? <Loader2 size={15} className="animate-spin" /> : null}
                                        Submit
                                    </button>
                                ) : (
                                    <button
                                        onClick={nextQuestion}
                                        className="flex items-center gap-2 bg-gray-900 hover:bg-gray-700 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors"
                                    >
                                        {qIndex + 1 < questions.length ? 'Next' : 'Finish'}
                                        <ArrowRight size={15} />
                                    </button>
                                )}
                            </div>
                        </motion.div>
                    </AnimatePresence>

                    {/* Solution reveal */}
                    <AnimatePresence>
                        {submitted && lastResult && (
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className={`rounded-2xl border p-5 ${
                                    lastResult.correct
                                        ? 'bg-emerald-50 border-emerald-200'
                                        : 'bg-amber-50 border-amber-200'
                                }`}
                            >
                                <div className="flex items-start gap-2">
                                    <Lightbulb
                                        size={16}
                                        className={lastResult.correct ? 'text-emerald-600 mt-0.5' : 'text-amber-600 mt-0.5'}
                                    />
                                    <div>
                                        <p className={`text-xs font-semibold mb-1 ${lastResult.correct ? 'text-emerald-700' : 'text-amber-700'}`}>
                                            {lastResult.correct ? 'Great work!' : 'Solution'}
                                        </p>
                                        <p className="text-sm text-gray-700 leading-relaxed">
                                            {lastResult.solution}
                                        </p>
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {error && (
                        <p className="text-red-500 text-sm mt-3 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
                    )}
                </div>
            </PageTransition>
        </div>
    );

    // ── Result / Dashboard screen ─────────────────────────────────────────────
    if (view === 'result') return (
        <div className="min-h-screen bg-gray-50">
            <Navbar />
            <PageTransition>
                <div className="max-w-xl mx-auto px-4 py-12">

                    {/* Score card */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 mb-6 text-center"
                    >
                        <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
                            <Trophy size={32} className="text-blue-600" />
                        </div>
                        <h2 className="text-2xl font-bold text-gray-900 mb-1">
                            Batch Complete!
                        </h2>
                        <p className="text-gray-500 text-sm mb-6">
                            You scored {batchScore} out of {questions.length}
                        </p>

                        {/* Big score ring */}
                        <div className="relative w-28 h-28 mx-auto mb-6">
                            <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                                <circle cx="50" cy="50" r="40" fill="none" stroke="#f1f5f9" strokeWidth="10" />
                                <motion.circle
                                    cx="50" cy="50" r="40" fill="none"
                                    stroke="#2563eb" strokeWidth="10"
                                    strokeLinecap="round"
                                    strokeDasharray={`${2 * Math.PI * 40}`}
                                    initial={{ strokeDashoffset: 2 * Math.PI * 40 }}
                                    animate={{ strokeDashoffset: 2 * Math.PI * 40 * (1 - batchScore / questions.length) }}
                                    transition={{ duration: 1, ease: 'easeOut' }}
                                />
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <span className="text-2xl font-bold text-gray-900">
                                    {Math.round((batchScore / questions.length) * 100)}%
                                </span>
                            </div>
                        </div>

                        {/* Action buttons */}
                        <div className="flex gap-3">
                            <button
                                onClick={() => { setView('start'); setError(''); }}
                                className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
                            >
                                <RefreshCw size={15} />
                                New Batch
                            </button>
                            <button
                                onClick={() => { fetchStats(); setView('dashboard'); }}
                                className="flex-1 flex items-center justify-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 rounded-xl transition-colors text-sm"
                            >
                                <BarChart2 size={15} />
                                View Progress
                            </button>
                        </div>
                    </motion.div>

                    {/* Quick mastery preview */}
                    {stats && (
                        <motion.div
                            initial={{ opacity: 0, y: 15 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                            className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6"
                        >
                            <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
                                <BarChart2 size={15} className="text-blue-600" />
                                Your Mastery
                            </h3>
                            <div className="space-y-3">
                                {Object.entries(stats.topics).map(([topic, { mean }]) => (
                                    <MasteryBar key={topic} label={topic} mastery={mean} />
                                ))}
                            </div>
                        </motion.div>
                    )}
                </div>
            </PageTransition>
        </div>
    );

    // ── Dashboard-only view ───────────────────────────────────────────────────
    if (view === 'dashboard') return (
        <div className="min-h-screen bg-gray-50">
            <Navbar />
            <PageTransition>
                <div className="max-w-xl mx-auto px-4 py-12">
                    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
                        <h2 className="text-lg font-bold text-gray-900 mb-1">Knowledge Dashboard</h2>
                        <p className="text-xs text-gray-500 mb-6">
                            Your Bayesian mastery model — updated after every answer
                        </p>
                        {stats ? (
                            <div className="space-y-3">
                                {Object.entries(stats.topics)
                                    .sort((a, b) => a[1].mean - b[1].mean)
                                    .map(([topic, { mean }]) => (
                                        <MasteryBar key={topic} label={topic} mastery={mean} />
                                    ))}
                            </div>
                        ) : (
                            <p className="text-sm text-gray-400">No data yet — complete a quiz first.</p>
                        )}
                    </div>
                    <button
                        onClick={() => setView('start')}
                        className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
                    >
                        <Brain size={16} />
                        Start Another Batch
                    </button>
                </div>
            </PageTransition>
        </div>
    );

    return null;
}