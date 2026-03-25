import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertTriangle, ArrowRight, Award, BarChart3, BookOpen, Brain, CheckCircle2, Clock, Lightbulb, Loader2, MessageSquare, Search, Send, Target, Zap } from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';
import { COGNITIVE_API_BASE as API_BASE_URL } from '../config/api';

function formatTime(seconds) {
    const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
    return `${Math.floor(safe / 60)}m ${Math.round(safe % 60)}s`;
}

function normaliseWrongStepAnalysis(analysis) {
    if (!analysis || typeof analysis !== 'object') {
        return { available: false, summary: '', thinking_mistakes: [], solving_mistakes: [], strengths: [], next_focus: [] };
    }
    const thinking = Array.isArray(analysis.thinking_mistakes) ? analysis.thinking_mistakes : [];
    const solving = Array.isArray(analysis.solving_mistakes) ? analysis.solving_mistakes : [];
    return {
        available: Boolean(analysis.available || thinking.length || solving.length),
        generated_by: analysis.generated_by || 'report',
        summary: analysis.summary || '',
        thinking_mistakes: thinking,
        solving_mistakes: solving,
        strengths: Array.isArray(analysis.strengths) ? analysis.strengths.filter(Boolean) : [],
        next_focus: Array.isArray(analysis.next_focus) ? analysis.next_focus.filter(Boolean) : [],
    };
}

function WrongStepCard({ item, accentClass }) {
    return (
        <div className={`rounded-2xl border p-4 ${accentClass}`}>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{item.question_number ? `Question ${item.question_number}` : 'Report Insight'}</p>
            <p className="mt-2 text-base font-bold text-slate-950">{item.title || 'Wrong Step Detected'}</p>
            {item.observed_issue && <p className="mt-2 text-sm leading-6 text-slate-700">{item.observed_issue}</p>}
            {item.evidence && <p className="mt-3 text-sm leading-6 text-slate-600"><span className="font-bold text-slate-800">Evidence:</span> {item.evidence}</p>}
            {item.why_it_failed && <p className="mt-3 text-sm leading-6 text-slate-600"><span className="font-bold text-slate-800">Why it failed:</span> {item.why_it_failed}</p>}
            {item.correction && <p className="mt-3 text-sm leading-6 text-emerald-900"><span className="font-bold">How to do it right:</span> {item.correction}</p>}
            {item.guided_question && <p className="mt-3 text-sm leading-6 text-indigo-900"><span className="font-bold">Tutor prompt:</span> {item.guided_question}</p>}
            {item.hint && <p className="mt-2 text-sm leading-6 text-amber-900"><span className="font-bold">Clue:</span> {item.hint}</p>}
        </div>
    );
}

export default function ThinkingReportPage() {
    const navigate = useNavigate();
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [tutoringSessionId, setTutoringSessionId] = useState('');
    const [tutorMessages, setTutorMessages] = useState([]);
    const [tutorInput, setTutorInput] = useState('');
    const [tutorStatus, setTutorStatus] = useState('idle');
    const [tutorProgress, setTutorProgress] = useState(null);
    const [tutoringAvailable, setTutoringAvailable] = useState(false);
    const [tutoringIntro, setTutoringIntro] = useState('');

    const applyTutoringBootstrap = (data) => {
        setTutoringSessionId(data?.tutoring_session_id || '');
        setTutoringAvailable(Boolean(data?.available));
        setTutoringIntro(data?.intro_message || '');
        setTutorProgress(data?.progress || null);
        setTutorMessages((current) => (
            current.length > 0
                ? current
                : (data?.assistant_message ? [{ role: 'assistant', content: data.assistant_message }] : [])
        ));
        setTutorStatus('ready');
        return data;
    };

    const createTutoringSession = async (sourceReport) => {
        const response = await fetch(`${API_BASE_URL}/start_tutoring_session`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ report: sourceReport }),
        });
        if (!response.ok) throw new Error('Failed to start tutoring session');
        const data = await response.json();
        return applyTutoringBootstrap(data);
    };

    const aggregateReportRaw = localStorage.getItem('mathmend_session_report');
    const sessionId = localStorage.getItem('mathmend_session_id');
    const timeElapsed = parseInt(localStorage.getItem('mathmend_session_time') || localStorage.getItem('thinking_session_time') || '120', 10);

    useEffect(() => {
        if (aggregateReportRaw) {
            try {
                setReport(JSON.parse(aggregateReportRaw));
                setLoading(false);
                return;
            } catch (err) {
                console.error('Aggregate report parse error:', err);
            }
        }
        if (!sessionId) {
            setLoading(false);
            setError('No session found. Please complete a thinking session first.');
            return;
        }
        async function fetchReport() {
            try {
                const response = await fetch(`${API_BASE_URL}/generate_report`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId }),
                });
                if (!response.ok) throw new Error('Failed to fetch report');
                setReport(await response.json());
            } catch (err) {
                console.error('Report fetch error:', err);
                setError('Unable to load report. The session may have expired.');
            } finally {
                setLoading(false);
            }
        }
        fetchReport();
    }, [aggregateReportRaw, sessionId]);

    useEffect(() => {
        if (!report || tutoringSessionId || tutorStatus === 'booting') return;
        let cancelled = false;
        async function startTutoring() {
            setTutorStatus('booting');
            try {
                if (cancelled) return;
                await createTutoringSession(report);
            } catch (err) {
                console.error('Tutoring boot error:', err);
                if (!cancelled) {
                    setTutorStatus('error');
                    setTutorMessages((current) => (
                        current.length > 0
                            ? current
                            : [{ role: 'assistant', content: 'You can still type what you think went wrong. I will try to start the tutoring flow when you send it.' }]
                    ));
                }
            }
        }
        startTutoring();
        return () => { cancelled = true; };
    }, [report, tutoringSessionId, tutorStatus]);

    async function handleTutorSubmit(event) {
        event.preventDefault();
        const trimmed = tutorInput.trim();
        if (!trimmed || tutorStatus === 'sending' || tutorProgress?.completed) return;
        setTutorMessages((current) => [...current, { role: 'user', content: trimmed }]);
        setTutorInput('');
        setTutorStatus('sending');
        try {
            let activeTutoringSessionId = tutoringSessionId;
            let activeTutoringAvailable = tutoringAvailable;
            if (!activeTutoringSessionId) {
                const data = await createTutoringSession(report);
                activeTutoringSessionId = data?.tutoring_session_id || '';
                activeTutoringAvailable = Boolean(data?.available);
            }
            if (!activeTutoringSessionId || !activeTutoringAvailable) {
                throw new Error('Tutoring session is not ready yet.');
            }
            const response = await fetch(`${API_BASE_URL}/tutoring_chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tutoring_session_id: activeTutoringSessionId, message: trimmed }),
            });
            if (!response.ok) throw new Error('Tutoring chat failed');
            const data = await response.json();
            setTutorMessages((current) => [...current, { role: 'assistant', content: data.assistant_message || 'Try explaining the step again.' }]);
            setTutorProgress(data.progress || null);
            setTutorStatus(data.completed ? 'completed' : 'ready');
        } catch (err) {
            console.error('Tutoring chat error:', err);
            setTutorMessages((current) => [...current, { role: 'assistant', content: 'I could not continue the tutoring chat just now. Please try sending your explanation again.' }]);
            setTutorStatus('ready');
        }
    }

    const metrics = report?.timeline_metrics || {};
    const vs = report?.validation_state || {};
    const rounds = report?.rounds || [];
    const totalQuestions = report?.total_questions || rounds.length || 1;
    const correctAnswers = report?.correct_answers ?? rounds.filter((round) => round.answerResult?.correct).length;
    const detailedReports = report?.detailed_report || [];
    const predictive = report?.predictive_analytics || null;
    const aggregateWrongStepAnalysis = useMemo(() => normaliseWrongStepAnalysis(report?.wrong_step_analysis), [report]);
    const predictiveAvailable = Boolean(predictive?.available);
    const confusionRiskTone = predictive?.confusion_risk_level === 'high' ? 'bg-rose-50 text-rose-700 border-rose-200' : predictive?.confusion_risk_level === 'moderate' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200';

    const scores = [
        { name: 'Path Alignment', score: Math.round((vs.path_alignment_score || 0) * 100), icon: Target, color: 'text-blue-500', bg: 'bg-blue-50', bar: 'bg-blue-500', desc: vs.path_alignment_score >= 0.7 ? 'Strong alignment with the optimal solution path.' : 'Room for improvement in following the optimal path.' },
        { name: 'Solution Progress', score: Math.round((vs.progress_ratio || 0) * 100), icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-50', bar: 'bg-emerald-500', desc: vs.progress_ratio >= 0.8 ? 'Made excellent progress through the solution steps.' : 'Covered some of the solution, more steps remain.' },
        { name: 'Efficiency', score: Math.round(Math.max(0, 100 - (vs.inefficiency_score || 0) * 100)), icon: Zap, color: 'text-amber-500', bg: 'bg-amber-50', bar: 'bg-amber-500', desc: (vs.inefficiency_score || 0) < 0.3 ? 'Efficient use of time and methods.' : 'Some unnecessary exploration detected.' },
        { name: 'Focus Score', score: Math.round(Math.max(0, 100 - (vs.deviation_score || 0) * 100)), icon: Search, color: 'text-fuchsia-500', bg: 'bg-fuchsia-50', bar: 'bg-fuchsia-500', desc: (vs.deviation_score || 0) < 0.3 ? 'Stayed focused on valid approaches.' : 'Explored outside the valid method set.' },
        { name: 'Stability', score: Math.round(Math.max(0, 100 - (vs.oscillation_index || 0) * 100)), icon: BarChart3, color: 'text-indigo-500', bg: 'bg-indigo-50', bar: 'bg-indigo-500', desc: (vs.oscillation_index || 0) < 0.3 ? 'Consistent thinking without excessive switching.' : 'Switched between methods quite often.' },
    ];

    if (loading) {
        return <div className="min-h-screen bg-gray-50 flex items-center justify-center"><div className="text-center"><Loader2 className="w-10 h-10 animate-spin text-blue-600 mx-auto" /><p className="mt-4 text-gray-500 font-medium">Generating your report...</p></div></div>;
    }

    if (error) {
        return (
            <div className="min-h-screen bg-gray-50 pb-12">
                <Navbar />
                <div className="max-w-4xl mx-auto px-4 mt-8 text-center">
                    <p className="text-gray-500 text-lg">{error}</p>
                    <button onClick={() => navigate('/dashboard')} className="mt-6 px-6 py-3 bg-gray-900 text-white rounded-xl font-bold hover:bg-gray-800">Return to Dashboard</button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 pb-12">
            <Navbar />
            <PageTransition>
                <div className="max-w-5xl mx-auto px-4 mt-8">
                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
                        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 p-10 text-white text-center">
                            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', delay: 0.2 }} className="w-20 h-20 bg-white/20 backdrop-blur-md rounded-full flex items-center justify-center mx-auto mb-4 border border-white/30 shadow-xl">
                                <Award size={40} className="text-white" />
                            </motion.div>
                            <h1 className="text-3xl font-extrabold mb-2 text-white">Thinking Session Complete!</h1>
                            <p className="text-blue-100 text-lg opacity-90">You spent {formatTime(timeElapsed)} across {totalQuestions} question{totalQuestions === 1 ? '' : 's'}.</p>
                            <p className="mt-2 text-sm text-blue-100/90">{correctAnswers} correct out of {totalQuestions}</p>
                        </div>

                        <div className="p-8">
                            {report?.thinking_graph && (
                                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-8 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-5">
                                    <div className="flex items-center gap-2 mb-3"><Brain size={18} className="text-indigo-600" /><span className="font-bold text-indigo-800 text-sm">Your Thinking Path</span></div>
                                    <p className="text-indigo-700 font-mono text-sm leading-7">{report.thinking_graph}</p>
                                </motion.div>
                            )}

                            <h2 className="text-xl font-bold text-gray-900 mb-6">Your Thinking Profile</h2>
                            <div className="space-y-6">
                                {scores.map((item, idx) => {
                                    const Icon = item.icon;
                                    return (
                                        <motion.div key={item.name} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + (idx * 0.1) }}>
                                            <div className="flex items-center justify-between mb-2">
                                                <div className="flex items-center gap-3">
                                                    <div className={`p-2 rounded-lg ${item.bg}`}><Icon size={18} className={item.color} /></div>
                                                    <div><span className="font-bold text-gray-800">{item.name}</span><p className="text-xs text-gray-500 mt-0.5">{item.desc}</p></div>
                                                </div>
                                                <span className="font-black text-gray-900">{item.score}%</span>
                                            </div>
                                            <div className="h-2.5 w-full bg-gray-100 rounded-full overflow-hidden"><motion.div initial={{ width: 0 }} animate={{ width: `${item.score}%` }} transition={{ duration: 1, delay: 0.5 + (idx * 0.1), type: 'spring' }} className={`h-full rounded-full ${item.bar}`} /></div>
                                        </motion.div>
                                    );
                                })}
                            </div>

                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }} className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-4">
                                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 text-center"><p className="text-2xl font-black text-gray-900">{report?.total_chunks || 0}</p><p className="text-xs text-gray-500 mt-1 font-medium">Chunks Analyzed</p></div>
                                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 text-center"><p className="text-2xl font-black text-gray-900">{report?.total_interventions || 0}</p><p className="text-xs text-gray-500 mt-1 font-medium">Interventions</p></div>
                                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 text-center"><p className="text-2xl font-black text-gray-900">{vs.on_graph_nodes || 0}</p><p className="text-xs text-gray-500 mt-1 font-medium">On-Graph Steps</p></div>
                                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 text-center"><p className="text-2xl font-black text-gray-900">{vs.off_graph_nodes || 0}</p><p className="text-xs text-gray-500 mt-1 font-medium">Off-Graph Steps</p></div>
                            </motion.div>

                            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.88 }} className="mt-8 rounded-2xl border border-sky-100 bg-sky-50/70 p-5">
                                <div className="flex items-center gap-2 mb-3"><BarChart3 size={18} className="text-sky-600" /><span className="font-bold text-sky-800 text-sm">Predictive Analytics</span></div>
                                <p className="text-sm leading-6 text-sky-950">{predictive?.summary || 'Predictive analytics was not available for this report.'}</p>
                                {predictiveAvailable && (
                                    <>
                                        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                                            <div className="rounded-xl bg-white/90 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-500">Predicted Time</p><p className="mt-2 text-sm font-bold text-gray-900">{formatTime(Math.round(predictive.predicted_total_time_seconds || 0))}</p></div>
                                            <div className="rounded-xl bg-white/90 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-500">Observed Time</p><p className="mt-2 text-sm font-bold text-gray-900">{formatTime(Math.round(predictive.observed_total_time_seconds || 0))}</p></div>
                                            <div className="rounded-xl bg-white/90 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-500">Confusion Risk</p><p className="mt-2 text-sm font-bold text-gray-900">{((predictive.confusion_probability || 0) * 100).toFixed(1)}%</p></div>
                                            <div className="rounded-xl bg-white/90 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-500">Pace Signal</p><p className="mt-2 text-sm font-bold capitalize text-gray-900">{String(predictive.pace_label || 'n/a').replaceAll('_', ' ')}</p></div>
                                        </div>
                                        <div className={`mt-4 inline-flex rounded-full border px-3 py-1 text-xs font-bold ${confusionRiskTone}`}>{String(predictive.confusion_risk_level || 'low').toUpperCase()} RISK</div>
                                        {Array.isArray(predictive.highlights) && predictive.highlights.length > 0 && <div className="mt-4 rounded-2xl border border-sky-100 bg-white/80 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-sky-700">Model Highlights</p><div className="mt-3 space-y-2">{predictive.highlights.map((item, index) => <p key={`${item}-${index}`} className="text-sm leading-6 text-gray-700">{item}</p>)}</div></div>}
                                    </>
                                )}
                            </motion.div>

                            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.92 }} className="mt-8 rounded-2xl border border-rose-100 bg-[linear-gradient(180deg,rgba(255,247,237,0.95),rgba(255,255,255,0.98))] p-5">
                                <div className="flex items-center gap-2 mb-3"><AlertTriangle size={18} className="text-rose-600" /><span className="font-bold text-rose-800 text-sm">Wrong-Step Analysis</span></div>
                                <p className="text-sm leading-6 text-slate-800">{aggregateWrongStepAnalysis.summary || 'No report-side wrong-step analysis was available.'}</p>

                                {aggregateWrongStepAnalysis.available ? (
                                    <>
                                        {aggregateWrongStepAnalysis.strengths.length > 0 && <div className="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-700">What Stayed Strong</p><div className="mt-3 space-y-2">{aggregateWrongStepAnalysis.strengths.map((item, index) => <p key={`${item}-${index}`} className="text-sm leading-6 text-emerald-950">{item}</p>)}</div></div>}
                                        <div className="mt-5 grid gap-4 lg:grid-cols-2">
                                            <div className="space-y-4">
                                                <div className="flex items-center gap-2"><Brain size={18} className="text-indigo-600" /><p className="font-bold text-slate-900">Wrong Aspects in Thinking</p></div>
                                                {aggregateWrongStepAnalysis.thinking_mistakes.length > 0 ? aggregateWrongStepAnalysis.thinking_mistakes.map((item) => <WrongStepCard key={item.finding_id || `${item.title}-${item.question_number}`} item={item} accentClass="border-indigo-100 bg-indigo-50/50" />) : <div className="rounded-2xl border border-dashed border-indigo-200 bg-white/80 p-4 text-sm leading-6 text-slate-600">No clear thinking-path mistake was isolated in the report.</div>}
                                            </div>
                                            <div className="space-y-4">
                                                <div className="flex items-center gap-2"><BookOpen size={18} className="text-amber-600" /><p className="font-bold text-slate-900">Wrong Aspects in Solving</p></div>
                                                {aggregateWrongStepAnalysis.solving_mistakes.length > 0 ? aggregateWrongStepAnalysis.solving_mistakes.map((item) => <WrongStepCard key={item.finding_id || `${item.title}-${item.question_number}`} item={item} accentClass="border-amber-100 bg-amber-50/60" />) : <div className="rounded-2xl border border-dashed border-amber-200 bg-white/80 p-4 text-sm leading-6 text-slate-600">No clear solving-step mistake was isolated in the report.</div>}
                                            </div>
                                        </div>
                                        {aggregateWrongStepAnalysis.next_focus.length > 0 && <div className="mt-5 rounded-2xl border border-slate-200 bg-white/90 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Immediate Next Focus</p><div className="mt-3 space-y-2">{aggregateWrongStepAnalysis.next_focus.map((item, index) => <p key={`${item}-${index}`} className="text-sm leading-6 text-slate-700">{item}</p>)}</div></div>}
                                    </>
                                ) : (
                                    <div className="mt-4 rounded-2xl border border-dashed border-rose-200 bg-white/85 p-4 text-sm leading-6 text-slate-600">The report did not surface any question-level wrong steps that need guided follow-up.</div>
                                )}
                            </motion.div>

                            {rounds.length > 0 && (
                                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.95 }} className="mt-8">
                                    <h2 className="text-xl font-bold text-gray-900 mb-4">Question Summary</h2>
                                    <div className="space-y-3">
                                        {rounds.map((round) => {
                                            const roundWrongStepAnalysis = normaliseWrongStepAnalysis(round.report?.wrong_step_analysis);
                                            return (
                                                <div key={`${round.sessionId}-${round.questionNumber}`} className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
                                                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                                        <div><p className="text-sm font-bold text-gray-900">Question {round.questionNumber}</p><p className="mt-1 text-sm text-gray-600">{round.problemText}</p></div>
                                                        <div className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold ${round.answerResult?.correct ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>{round.answerResult?.correct ? 'Correct' : 'Wrong / Not checked'}</div>
                                                    </div>
                                                    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                                                        <div className="rounded-xl bg-gray-50 p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gray-400">Thinking</p><p className="mt-2 text-sm font-bold text-gray-900">{formatTime(round.thinkingSeconds || 0)}</p></div>
                                                        <div className="rounded-xl bg-gray-50 p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gray-400">Solving</p><p className="mt-2 text-sm font-bold text-gray-900">{formatTime(round.solvingSeconds || 0)}</p></div>
                                                        <div className="rounded-xl bg-gray-50 p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gray-400">Upload Grace</p><p className="mt-2 text-sm font-bold text-gray-900">{formatTime(round.uploadGraceUsed || 0)}</p></div>
                                                        <div className="rounded-xl bg-gray-50 p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gray-400">Your Answer</p><p className="mt-2 text-sm font-bold text-gray-900">{round.answerResult?.extracted_answer || 'N/A'}</p></div>
                                                    </div>

                                                    {round.report?.time_analysis && <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                                                        <div className="rounded-xl bg-indigo-50 p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-indigo-500">To Strategy</p><p className="mt-2 text-sm font-bold text-gray-900">{formatTime(Math.round(round.report.time_analysis.time_to_strategy_seconds || 0))}</p></div>
                                                        <div className="rounded-xl bg-indigo-50 p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-indigo-500">To Execution</p><p className="mt-2 text-sm font-bold text-gray-900">{formatTime(Math.round(round.report.time_analysis.time_to_execution_seconds || 0))}</p></div>
                                                        <div className="rounded-xl bg-indigo-50 p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-indigo-500">Longest Silence</p><p className="mt-2 text-sm font-bold text-gray-900">{formatTime(Math.round(round.report.time_analysis.longest_silence_seconds || 0))}</p></div>
                                                        <div className="rounded-xl bg-indigo-50 p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-indigo-500">Expected</p><p className="mt-2 text-sm font-bold text-gray-900">{round.answerResult?.expected_answer || 'N/A'}</p></div>
                                                    </div>}

                                                    {round.report?.predictive_analytics?.available && <div className="mt-4 rounded-2xl border border-sky-100 bg-sky-50/70 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-sky-700">Question Prediction Layer</p><p className="mt-3 text-sm leading-7 text-sky-950">{round.report.predictive_analytics.summary}</p></div>}
                                                    {round.report?.detailed_analysis && <div className="mt-4 rounded-2xl border border-amber-100 bg-amber-50/70 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-700">Question Analysis</p><p className="mt-3 text-sm leading-7 text-amber-950">{round.report.detailed_analysis}</p></div>}
                                                    {roundWrongStepAnalysis.available && <div className="mt-4 rounded-2xl border border-rose-100 bg-rose-50/60 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-rose-700">Wrong-Step Breakdown</p><p className="mt-3 text-sm leading-7 text-slate-700">{roundWrongStepAnalysis.summary}</p><div className="mt-4 grid gap-3 lg:grid-cols-2"><div className="space-y-3">{roundWrongStepAnalysis.thinking_mistakes.map((item) => <WrongStepCard key={item.finding_id || `${item.title}-${round.questionNumber}-thinking`} item={item} accentClass="border-indigo-100 bg-white/90" />)}</div><div className="space-y-3">{roundWrongStepAnalysis.solving_mistakes.map((item) => <WrongStepCard key={item.finding_id || `${item.title}-${round.questionNumber}-solving`} item={item} accentClass="border-amber-100 bg-white/90" />)}</div></div></div>}
                                                    {round.report?.improvement_rule && <div className="mt-3 rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-700">Targeted Improvement</p><p className="mt-3 text-sm leading-7 text-emerald-950">{round.report.improvement_rule}</p></div>}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </motion.div>
                            )}

                            {detailedReports.length > 0 && <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.98 }} className="mt-8 rounded-2xl border border-blue-100 bg-blue-50/70 p-5"><div className="flex items-center gap-2 mb-3"><Clock size={18} className="text-blue-600" /><span className="font-bold text-blue-800 text-sm">Session Time Analysis</span></div><div className="space-y-3">{detailedReports.map((item) => <div key={item.question_number} className="rounded-xl bg-white/90 p-4"><p className="text-sm font-bold text-gray-900">Question {item.question_number}</p><p className="mt-2 text-sm leading-7 text-gray-700">{item.detailed_analysis || item.insight}</p></div>)}</div></motion.div>}
                            {report?.insight && <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.0 }} className="mt-8 rounded-2xl border border-amber-100 bg-amber-50/60 p-5"><div className="flex items-center gap-2 mb-3"><Lightbulb size={18} className="text-amber-600" /><span className="font-bold text-amber-800 text-sm">AI Insight</span></div><p className="text-amber-900 text-sm leading-6">{report.insight}</p></motion.div>}
                            {report?.improvement_rule && <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.1 }} className="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50/60 p-5"><div className="flex items-center gap-2 mb-3"><Target size={18} className="text-emerald-600" /><span className="font-bold text-emerald-800 text-sm">Next Time, Try This</span></div><p className="text-emerald-900 text-sm leading-6">{report.improvement_rule}</p></motion.div>}

                            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.18 }} className="mt-8 rounded-3xl border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)] p-5 shadow-sm">
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                    <div>
                                        <div className="flex items-center gap-2"><MessageSquare size={18} className="text-slate-700" /><span className="font-bold text-slate-900 text-sm">Post-Report Tutoring Chat</span></div>
                                        <p className="mt-2 text-sm leading-6 text-slate-600">This guided chat stays on each wrong step until your explanation shows the idea is clear, then it unlocks the next one.</p>
                                        {tutoringIntro && <p className="mt-2 text-sm leading-6 text-slate-700">{tutoringIntro}</p>}
                                    </div>
                                    {tutorProgress && <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 text-sm text-slate-700"><p className="font-bold text-slate-900">{tutorProgress.completed_questions}/{tutorProgress.total_questions} cleared</p>{tutorProgress.current_title && !tutorProgress.completed && <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">{tutorProgress.current_stage} | {tutorProgress.current_title}</p>}</div>}
                                </div>

                                <div className="mt-5 rounded-2xl border border-slate-200 bg-white">
                                    <div className="max-h-[420px] overflow-y-auto p-4 space-y-3">
                                        {tutorStatus === 'booting' && <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 size={16} className="animate-spin" />Preparing the tutoring flow from your report...</div>}
                                        {tutorMessages.map((message, index) => <div key={`${message.role}-${index}`} className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === 'assistant' ? 'bg-slate-100 text-slate-800' : 'ml-auto bg-indigo-600 text-white'}`}><p className="whitespace-pre-wrap">{message.content}</p></div>)}
                                        {tutorStatus === 'sending' && <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 size={16} className="animate-spin" />Evaluating your explanation...</div>}
                                        {tutorStatus === 'error' && <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-700">The tutoring panel could not start automatically. Refreshing the page after the backend restarts should restore it.</div>}
                                        {tutorStatus === 'ready' && !tutoringAvailable && tutorMessages.length === 0 && <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">No wrong-step tutoring targets were found in this report.</div>}
                                    </div>
                                    <form onSubmit={handleTutorSubmit} className="border-t border-slate-200 p-4">
                                        <div className="flex flex-col gap-3 sm:flex-row">
                                            <textarea value={tutorInput} onChange={(event) => setTutorInput(event.target.value)} placeholder="Explain why your step was wrong and how you would correct it." rows={3} disabled={tutorStatus === 'sending' || tutorProgress?.completed} className="min-h-[84px] flex-1 resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-indigo-400 focus:bg-white" />
                                            <button type="submit" disabled={tutorStatus === 'sending' || tutorProgress?.completed || !tutorInput.trim()} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"><Send size={16} />Send</button>
                                        </div>
                                    </form>
                                </div>
                            </motion.div>

                            <div className="mt-10 pt-8 border-t border-gray-100 flex justify-end">
                                <button onClick={() => navigate('/dashboard')} className="px-8 py-3.5 bg-gray-900 text-white rounded-xl font-bold hover:bg-gray-800 transition-colors flex items-center gap-2 shadow-md">Return to Dashboard <ArrowRight size={18} /></button>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </PageTransition>
        </div>
    );
}
