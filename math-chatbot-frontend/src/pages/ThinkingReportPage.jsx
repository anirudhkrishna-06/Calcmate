import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Award, Target, GitMerge, Search, AlertTriangle, ArrowRight, CheckCircle2, Lightbulb, Zap, BarChart3, Clock, Loader2, Brain } from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';

const API_BASE_URL = 'http://127.0.0.1:8000';

export default function ThinkingReportPage() {
    const navigate = useNavigate();
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

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
                const data = await response.json();
                setReport(data);
            } catch (err) {
                console.error('Report fetch error:', err);
                setError('Unable to load report. The session may have expired.');
            } finally {
                setLoading(false);
            }
        }

        fetchReport();
    }, [aggregateReportRaw, sessionId]);

    const formatTime = (seconds) => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}m ${s}s`;
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <Loader2 className="w-10 h-10 animate-spin text-blue-600 mx-auto" />
                    <p className="mt-4 text-gray-500 font-medium">Generating your report...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-gray-50 pb-12">
                <Navbar />
                <div className="max-w-4xl mx-auto px-4 mt-8 text-center">
                    <p className="text-gray-500 text-lg">{error}</p>
                    <button onClick={() => navigate('/dashboard')} className="mt-6 px-6 py-3 bg-gray-900 text-white rounded-xl font-bold hover:bg-gray-800">
                        Return to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    const metrics = report?.timeline_metrics || {};
    const vs = report?.validation_state || {};
    const rounds = report?.rounds || [];
    const totalQuestions = report?.total_questions || rounds.length || 1;
    const correctAnswers = report?.correct_answers ?? rounds.filter((round) => round.answerResult?.correct).length;
    const detailedReports = report?.detailed_report || [];

    const scores = [
        {
            name: 'Path Alignment',
            score: Math.round((vs.path_alignment_score || 0) * 100),
            icon: Target,
            color: 'text-blue-500',
            bg: 'bg-blue-50',
            bar: 'bg-blue-500',
            desc: vs.path_alignment_score >= 0.7 ? 'Strong alignment with the optimal solution path.' : 'Room for improvement in following the optimal path.',
        },
        {
            name: 'Solution Progress',
            score: Math.round((vs.progress_ratio || 0) * 100),
            icon: CheckCircle2,
            color: 'text-emerald-500',
            bg: 'bg-emerald-50',
            bar: 'bg-emerald-500',
            desc: vs.progress_ratio >= 0.8 ? 'Made excellent progress through the solution steps.' : 'Covered some of the solution, more steps remain.',
        },
        {
            name: 'Efficiency',
            score: Math.round(Math.max(0, 100 - (vs.inefficiency_score || 0) * 100)),
            icon: Zap,
            color: 'text-amber-500',
            bg: 'bg-amber-50',
            bar: 'bg-amber-500',
            desc: (vs.inefficiency_score || 0) < 0.3 ? 'Efficient use of time and methods.' : 'Some unnecessary exploration detected.',
        },
        {
            name: 'Focus Score',
            score: Math.round(Math.max(0, 100 - (vs.deviation_score || 0) * 100)),
            icon: Search,
            color: 'text-purple-500',
            bg: 'bg-purple-50',
            bar: 'bg-purple-500',
            desc: (vs.deviation_score || 0) < 0.3 ? 'Stayed focused on valid approaches.' : 'Explored outside the valid method set.',
        },
        {
            name: 'Stability',
            score: Math.round(Math.max(0, 100 - (vs.oscillation_index || 0) * 100)),
            icon: BarChart3,
            color: 'text-indigo-500',
            bg: 'bg-indigo-50',
            bar: 'bg-indigo-500',
            desc: (vs.oscillation_index || 0) < 0.3 ? 'Consistent thinking without excessive switching.' : 'Switched between methods quite often.',
        },
    ];

    return (
        <div className="min-h-screen bg-gray-50 pb-12">
            <Navbar />
            <PageTransition>
                <div className="max-w-4xl mx-auto px-4 mt-8">
                    <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden"
                    >
                        {/* Header */}
                        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 p-10 text-white text-center">
                            <motion.div 
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                transition={{ type: "spring", delay: 0.2 }}
                                className="w-20 h-20 bg-white/20 backdrop-blur-md rounded-full flex items-center justify-center mx-auto mb-4 border border-white/30 shadow-xl"
                            >
                                <Award size={40} className="text-white" />
                            </motion.div>
                            <h1 className="text-3xl font-extrabold mb-2 text-white">Thinking Session Complete!</h1>
                            <p className="text-blue-100 text-lg opacity-90">You spent {formatTime(timeElapsed)} across {totalQuestions} question{totalQuestions === 1 ? '' : 's'}.</p>
                            <p className="mt-2 text-sm text-blue-100/90">{correctAnswers} correct out of {totalQuestions}</p>
                        </div>

                        <div className="p-8">
                            {/* Thinking Graph */}
                            {report?.thinking_graph && (
                                <motion.div 
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.2 }}
                                    className="mb-8 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-5"
                                >
                                    <div className="flex items-center gap-2 mb-3">
                                        <Brain size={18} className="text-indigo-600" />
                                        <span className="font-bold text-indigo-800 text-sm">Your Thinking Path</span>
                                    </div>
                                    <p className="text-indigo-700 font-mono text-sm leading-7">{report.thinking_graph}</p>
                                </motion.div>
                            )}

                            {/* Scores */}
                            <h2 className="text-xl font-bold text-gray-900 mb-6">Your Thinking Profile</h2>
                            
                            <div className="space-y-6">
                                {scores.map((item, idx) => {
                                    const Icon = item.icon;
                                    return (
                                        <motion.div 
                                            key={item.name}
                                            initial={{ opacity: 0, x: -20 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            transition={{ delay: 0.3 + (idx * 0.1) }}
                                        >
                                            <div className="flex items-center justify-between mb-2">
                                                <div className="flex items-center gap-3">
                                                    <div className={`p-2 rounded-lg ${item.bg}`}>
                                                        <Icon size={18} className={item.color} />
                                                    </div>
                                                    <div>
                                                        <span className="font-bold text-gray-800">{item.name}</span>
                                                        <p className="text-xs text-gray-500 mt-0.5">{item.desc}</p>
                                                    </div>
                                                </div>
                                                <span className="font-black text-gray-900">{item.score}%</span>
                                            </div>
                                            <div className="h-2.5 w-full bg-gray-100 rounded-full overflow-hidden">
                                                <motion.div 
                                                    initial={{ width: 0 }}
                                                    animate={{ width: `${item.score}%` }}
                                                    transition={{ duration: 1, delay: 0.5 + (idx * 0.1), type: "spring" }}
                                                    className={`h-full rounded-full ${item.bar}`}
                                                />
                                            </div>
                                        </motion.div>
                                    );
                                })}
                            </div>

                            {/* Session Stats */}
                            <motion.div 
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.8 }}
                                className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-4"
                            >
                                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 text-center">
                                    <p className="text-2xl font-black text-gray-900">{report?.total_chunks || 0}</p>
                                    <p className="text-xs text-gray-500 mt-1 font-medium">Chunks Analyzed</p>
                                </div>
                                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 text-center">
                                    <p className="text-2xl font-black text-gray-900">{report?.total_interventions || 0}</p>
                                    <p className="text-xs text-gray-500 mt-1 font-medium">Interventions</p>
                                </div>
                                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 text-center">
                                    <p className="text-2xl font-black text-gray-900">{vs.on_graph_nodes || 0}</p>
                                    <p className="text-xs text-gray-500 mt-1 font-medium">On-Graph Steps</p>
                                </div>
                                <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 text-center">
                                    <p className="text-2xl font-black text-gray-900">{vs.off_graph_nodes || 0}</p>
                                    <p className="text-xs text-gray-500 mt-1 font-medium">Off-Graph Steps</p>
                                </div>
                            </motion.div>

                            {rounds.length > 0 && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.95 }}
                                    className="mt-8"
                                >
                                    <h2 className="text-xl font-bold text-gray-900 mb-4">Question Summary</h2>
                                    <div className="space-y-3">
                                        {rounds.map((round) => (
                                            <div key={`${round.sessionId}-${round.questionNumber}`} className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
                                                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                                    <div>
                                                        <p className="text-sm font-bold text-gray-900">Question {round.questionNumber}</p>
                                                        <p className="mt-1 text-sm text-gray-600">{round.problemText}</p>
                                                    </div>
                                                    <div className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold ${
                                                        round.answerResult?.correct ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
                                                    }`}>
                                                        {round.answerResult?.correct ? 'Correct' : 'Wrong / Not checked'}
                                                    </div>
                                                </div>
                                                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                                                    <div className="rounded-xl bg-gray-50 p-3">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gray-400">Thinking</p>
                                                        <p className="mt-2 text-sm font-bold text-gray-900">{formatTime(round.thinkingSeconds || 0)}</p>
                                                    </div>
                                                    <div className="rounded-xl bg-gray-50 p-3">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gray-400">Solving</p>
                                                        <p className="mt-2 text-sm font-bold text-gray-900">{formatTime(round.solvingSeconds || 0)}</p>
                                                    </div>
                                                    <div className="rounded-xl bg-gray-50 p-3">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gray-400">Upload Grace</p>
                                                        <p className="mt-2 text-sm font-bold text-gray-900">{formatTime(round.uploadGraceUsed || 0)}</p>
                                                    </div>
                                                    <div className="rounded-xl bg-gray-50 p-3">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gray-400">Your Answer</p>
                                                        <p className="mt-2 text-sm font-bold text-gray-900">{round.answerResult?.extracted_answer || 'N/A'}</p>
                                                    </div>
                                                </div>

                                                {round.report?.time_analysis && (
                                                    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                                                        <div className="rounded-xl bg-indigo-50 p-3">
                                                            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-indigo-500">To Strategy</p>
                                                            <p className="mt-2 text-sm font-bold text-gray-900">{formatTime(Math.round(round.report.time_analysis.time_to_strategy_seconds || 0))}</p>
                                                        </div>
                                                        <div className="rounded-xl bg-indigo-50 p-3">
                                                            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-indigo-500">To Execution</p>
                                                            <p className="mt-2 text-sm font-bold text-gray-900">{formatTime(Math.round(round.report.time_analysis.time_to_execution_seconds || 0))}</p>
                                                        </div>
                                                        <div className="rounded-xl bg-indigo-50 p-3">
                                                            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-indigo-500">Longest Silence</p>
                                                            <p className="mt-2 text-sm font-bold text-gray-900">{formatTime(Math.round(round.report.time_analysis.longest_silence_seconds || 0))}</p>
                                                        </div>
                                                        <div className="rounded-xl bg-indigo-50 p-3">
                                                            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-indigo-500">Expected</p>
                                                            <p className="mt-2 text-sm font-bold text-gray-900">{round.answerResult?.expected_answer || 'N/A'}</p>
                                                        </div>
                                                    </div>
                                                )}

                                                {round.report?.detailed_analysis && (
                                                    <div className="mt-4 rounded-2xl border border-amber-100 bg-amber-50/70 p-4">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-700">Question Analysis</p>
                                                        <p className="mt-3 text-sm leading-7 text-amber-950">{round.report.detailed_analysis}</p>
                                                    </div>
                                                )}

                                                {round.report?.improvement_rule && (
                                                    <div className="mt-3 rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4">
                                                        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-700">Targeted Improvement</p>
                                                        <p className="mt-3 text-sm leading-7 text-emerald-950">{round.report.improvement_rule}</p>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </motion.div>
                            )}

                            {detailedReports.length > 0 && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.98 }}
                                    className="mt-8 rounded-2xl border border-blue-100 bg-blue-50/70 p-5"
                                >
                                    <div className="flex items-center gap-2 mb-3">
                                        <Clock size={18} className="text-blue-600" />
                                        <span className="font-bold text-blue-800 text-sm">Session Time Analysis</span>
                                    </div>
                                    <div className="space-y-3">
                                        {detailedReports.map((item) => (
                                            <div key={item.question_number} className="rounded-xl bg-white/90 p-4">
                                                <p className="text-sm font-bold text-gray-900">Question {item.question_number}</p>
                                                <p className="mt-2 text-sm leading-7 text-gray-700">{item.detailed_analysis || item.insight}</p>
                                            </div>
                                        ))}
                                    </div>
                                </motion.div>
                            )}

                            {/* Gemini Insight */}
                            {report?.insight && (
                                <motion.div 
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 1.0 }}
                                    className="mt-8 rounded-2xl border border-amber-100 bg-amber-50/60 p-5"
                                >
                                    <div className="flex items-center gap-2 mb-3">
                                        <Lightbulb size={18} className="text-amber-600" />
                                        <span className="font-bold text-amber-800 text-sm">AI Insight</span>
                                    </div>
                                    <p className="text-amber-900 text-sm leading-6">{report.insight}</p>
                                </motion.div>
                            )}

                            {/* Improvement Rule */}
                            {report?.improvement_rule && (
                                <motion.div 
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 1.1 }}
                                    className="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50/60 p-5"
                                >
                                    <div className="flex items-center gap-2 mb-3">
                                        <Target size={18} className="text-emerald-600" />
                                        <span className="font-bold text-emerald-800 text-sm">Next Time, Try This</span>
                                    </div>
                                    <p className="text-emerald-900 text-sm leading-6">{report.improvement_rule}</p>
                                </motion.div>
                            )}

                            <div className="mt-10 pt-8 border-t border-gray-100 flex justify-end">
                                <button
                                    onClick={() => navigate('/dashboard')}
                                    className="px-8 py-3.5 bg-gray-900 text-white rounded-xl font-bold hover:bg-gray-800 transition-colors flex items-center gap-2 shadow-md"
                                >
                                    Return to Dashboard <ArrowRight size={18} />
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </PageTransition>
        </div>
    );
}
