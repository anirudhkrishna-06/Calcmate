import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { BellRing, Clock3, Eye, Flag, Lock, Plus, ShieldCheck, Swords, Trophy, Users } from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';
import { useAuth } from '../context/AuthContext';
import { listTeacherStudents } from '../services/classroomData';
import {
    createContest,
    fetchContestProblemBank,
    getContest,
    getContestSubmission,
    getServerContestTime,
    getUserRatingProfile,
    listContestLeaderboard,
    listVisibleContests,
    submitContestAttempt,
} from '../services/contestData';

const formatDateTime = (value) => {
    if (!value) return 'Not scheduled';
    return new Date(value).toLocaleString([], {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    });
};

const getStatus = (contest) => {
    const now = Date.now();
    const start = new Date(contest.startTime).getTime();
    const end = new Date(contest.endTime).getTime();
    if (now < start) return 'UPCOMING';
    if (now <= end) return 'LIVE';
    return 'COMPLETED';
};

const statusClass = {
    UPCOMING: 'bg-amber-50 text-amber-700 border-amber-200',
    LIVE: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    COMPLETED: 'bg-slate-100 text-slate-700 border-slate-200',
};

export default function ContestsPage() {
    const { user } = useAuth();
    const [searchParams, setSearchParams] = useSearchParams();
    const [contests, setContests] = useState([]);
    const [selectedContestId, setSelectedContestId] = useState(searchParams.get('contest') || '');
    const [selectedContest, setSelectedContest] = useState(null);
    const [leaderboard, setLeaderboard] = useState([]);
    const [ratingProfile, setRatingProfile] = useState(null);
    const [teacherStudents, setTeacherStudents] = useState([]);
    const [problemBank, setProblemBank] = useState([]);
    const [problemSearch, setProblemSearch] = useState('');
    const [selectedProblems, setSelectedProblems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [creatingContest, setCreatingContest] = useState(false);
    const [submittingContest, setSubmittingContest] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');
    const [problemBankStatus, setProblemBankStatus] = useState('');
    const [mySubmission, setMySubmission] = useState(null);
    const [attemptStartedAt, setAttemptStartedAt] = useState('');
    const [answers, setAnswers] = useState({});
    const [countdown, setCountdown] = useState('');
    const [contestForm, setContestForm] = useState(() => {
        const start = new Date(Date.now() + 3600000);
        const end = new Date(Date.now() + 7200000);
        return {
            title: 'PRMO Challenge',
            visibility: 'private',
            startTime: start.toISOString().slice(0, 16),
            endTime: end.toISOString().slice(0, 16),
        };
    });

    const loadContests = async () => {
        if (!user?.id) return;
        setLoading(true);
        try {
            const [contestItems, rating] = await Promise.all([listVisibleContests(user), getUserRatingProfile(user.id)]);
            setContests(contestItems);
            setRatingProfile(rating);
            const nextId = searchParams.get('contest') || selectedContestId || contestItems[0]?.id || '';
            if (nextId) {
                const [contest, board, submission] = await Promise.all([
                    getContest(nextId),
                    listContestLeaderboard(nextId),
                    getContestSubmission(nextId, user.id),
                ]);
                setSelectedContest(contest);
                setLeaderboard(board);
                setMySubmission(submission);
                setSelectedContestId(nextId);
            }
            if (user.role === 'teacher') {
                const students = await listTeacherStudents(user.id);
                setTeacherStudents(students);

                try {
                    const bank = await fetchContestProblemBank({ limit: 60 });
                    setProblemBank(bank);
                    setProblemBankStatus('');
                } catch (bankError) {
                    console.error('Error loading olympiad problem bank:', bankError);
                    setProblemBank([]);
                    setProblemBankStatus(
                        bankError.message?.includes('Contest problem bank is not available')
                            ? 'Olympiad problem bank is offline because the backend is missing openpyxl.'
                            : bankError.message || 'Unable to load olympiad problem bank.'
                    );
                }
            }
        } catch (error) {
            console.error('Error loading contest data:', error);
            setStatusMessage(error.message || 'Unable to load contest data.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadContests();
    }, [user?.id]);

    useEffect(() => {
        if (!selectedContest) return undefined;
        const tick = () => {
            const now = Date.now();
            const start = new Date(selectedContest.startTime).getTime();
            const end = new Date(selectedContest.endTime).getTime();
            if (now > end) {
                setCountdown('Closed');
                return;
            }
            const target = now < start ? start : end;
            const diff = Math.max(0, target - now);
            const prefix = now < start ? 'Starts in' : 'Ends in';
            const hours = Math.floor(diff / 3600000);
            const minutes = Math.floor((diff % 3600000) / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);
            setCountdown(`${prefix} ${hours}h ${minutes}m ${seconds}s`);
        };
        tick();
        const intervalId = window.setInterval(tick, 1000);
        return () => window.clearInterval(intervalId);
    }, [selectedContest]);

    const filteredProblems = useMemo(() => {
        if (!problemSearch.trim()) return problemBank;
        const needle = problemSearch.toLowerCase();
        return problemBank.filter(
            (problem) =>
                problem.statement.toLowerCase().includes(needle) ||
                problem.topic.toLowerCase().includes(needle) ||
                problem.competition.toLowerCase().includes(needle)
        );
    }, [problemBank, problemSearch]);

    const metrics = useMemo(() => ({
        live: contests.filter((contest) => getStatus(contest) === 'LIVE').length,
        upcoming: contests.filter((contest) => getStatus(contest) === 'UPCOMING').length,
        completed: contests.filter((contest) => getStatus(contest) === 'COMPLETED').length,
    }), [contests]);

    const openContest = async (contestId) => {
        setSelectedContestId(contestId);
        setSearchParams({ contest: contestId });
        const [contest, board, submission] = await Promise.all([
            getContest(contestId),
            listContestLeaderboard(contestId),
            getContestSubmission(contestId, user.id),
        ]);
        setSelectedContest(contest);
        setLeaderboard(board);
        setMySubmission(submission);
        setAttemptStartedAt('');
        setAnswers({});
    };

    const toggleProblem = (problem) => {
        setSelectedProblems((current) => {
            if (current.some((item) => item.questionId === problem.questionId)) {
                return current.filter((item) => item.questionId !== problem.questionId);
            }
            return [...current, problem].slice(0, 12);
        });
    };

    const handleCreateContest = async () => {
        if (!user?.id) return;
        setCreatingContest(true);
        setStatusMessage('');
        try {
            const contest = await createContest({
                teacherId: user.id,
                teacherName: user.displayName || user.name || 'Teacher',
                visibility: contestForm.visibility,
                title: contestForm.title,
                startTime: new Date(contestForm.startTime).toISOString(),
                endTime: new Date(contestForm.endTime).toISOString(),
                questions: selectedProblems,
                invitedStudentIds: contestForm.visibility === 'private' ? teacherStudents.map((student) => student.id) : [],
            });
            setSelectedProblems([]);
            setStatusMessage('Contest created and notifications sent.');
            await loadContests();
            await openContest(contest.id);
        } catch (error) {
            console.error('Error creating contest:', error);
            setStatusMessage(error.message || 'Unable to create contest.');
        } finally {
            setCreatingContest(false);
        }
    };

    const startContest = async () => {
        try {
            const serverTime = await getServerContestTime();
            setAttemptStartedAt(serverTime.serverTime);
        } catch (error) {
            setStatusMessage(error.message || 'Unable to start contest.');
        }
    };

    const submitContest = async () => {
        if (!selectedContest || !attemptStartedAt) return;
        setSubmittingContest(true);
        setStatusMessage('');
        try {
            const serverTime = await getServerContestTime();
            await submitContestAttempt({
                contest: selectedContest,
                user,
                startTime: attemptStartedAt,
                endTime: serverTime.serverTime,
                answers: selectedContest.questions.map((question) => ({
                    qId: question.questionId,
                    answer: answers[question.questionId] === '' || answers[question.questionId] == null ? null : Number(answers[question.questionId]),
                    timestamp: serverTime.serverTime,
                })),
            });
            await openContest(selectedContest.id);
            setRatingProfile(await getUserRatingProfile(user.id));
            setStatusMessage('Contest submitted. Leaderboard refreshed.');
        } catch (error) {
            console.error('Error submitting contest:', error);
            setStatusMessage(error.message || 'Unable to submit contest.');
        } finally {
            setSubmittingContest(false);
        }
    };

    return (
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.16),_transparent_28%),linear-gradient(180deg,#f8fafc_0%,#eef4ff_100%)]">
            <Navbar />
            <PageTransition>
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div className="grid xl:grid-cols-[1.05fr_0.95fr] gap-6 mb-6">
                        <motion.div className="rounded-[28px] border border-slate-200 bg-slate-950 text-white p-8 relative overflow-hidden" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
                            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(45,212,191,0.22),_transparent_38%)]" />
                            <div className="relative">
                                <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-slate-200 mb-4"><Swords size={14} />Contest Engine</div>
                                <h1 className="text-3xl font-bold leading-tight">Competitive math contests with server-evaluated ratings, fairness checks, and auditable leaderboards.</h1>
                                <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300">Olympiad problems are snapshotted into each contest. Submissions are time-scored, anomaly-checked, and written back into the student rating profile.</p>
                            </div>
                        </motion.div>
                        <motion.div className="rounded-[28px] border border-white/60 bg-white/90 backdrop-blur p-6 shadow-[0_24px_70px_-40px_rgba(15,23,42,0.45)]" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}>
                            <div className="flex items-start justify-between gap-4">
                                <div>
                                    <p className="text-xs uppercase tracking-[0.16em] text-cyan-600 font-semibold">Rating Profile</p>
                                    <h2 className="text-3xl font-bold text-slate-950 mt-2">{ratingProfile?.currentRating || 0}</h2>
                                    <p className="text-sm text-slate-500 mt-2">Peak {ratingProfile?.maxRating || 0} · {ratingProfile?.contestsPlayed || 0} contests</p>
                                </div>
                                <div className="w-12 h-12 rounded-2xl bg-cyan-50 text-cyan-600 flex items-center justify-center"><Trophy size={22} /></div>
                            </div>
                            <div className="grid grid-cols-3 gap-3 mt-6">
                                <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3"><p className="text-xs uppercase tracking-[0.14em] text-slate-400">Live</p><p className="text-xl font-bold text-slate-900 mt-2">{metrics.live}</p></div>
                                <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3"><p className="text-xs uppercase tracking-[0.14em] text-slate-400">Upcoming</p><p className="text-xl font-bold text-slate-900 mt-2">{metrics.upcoming}</p></div>
                                <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3"><p className="text-xs uppercase tracking-[0.14em] text-slate-400">Completed</p><p className="text-xl font-bold text-slate-900 mt-2">{metrics.completed}</p></div>
                            </div>
                            <div className="rounded-2xl border border-cyan-100 bg-cyan-50 px-4 py-4 mt-6 text-sm text-cyan-800">Fast-submit thresholds, answer-pattern anomalies, and audit hashes are computed during contest evaluation.</div>
                        </motion.div>
                    </div>
                    {statusMessage && <div className="mb-6 rounded-2xl border border-cyan-100 bg-cyan-50 px-4 py-3 text-sm text-cyan-800">{statusMessage}</div>}
                    <div className="grid xl:grid-cols-[0.8fr_1.2fr] gap-6">
                        <motion.div className="rounded-[28px] border border-white/60 bg-white/90 backdrop-blur p-6" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
                            <div className="flex items-center justify-between mb-5">
                                <div>
                                    <h2 className="text-lg font-semibold text-slate-950">Contest Board</h2>
                                    <p className="text-sm text-slate-500 mt-1">Upcoming, live, and completed contests visible to this account.</p>
                                </div>
                                <BellRing size={18} className="text-cyan-600" />
                            </div>
                            <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
                                {loading ? (
                                    <p className="text-sm text-slate-500">Loading contests...</p>
                                ) : contests.length === 0 ? (
                                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-5 py-8 text-center">
                                        <Flag size={20} className="mx-auto text-slate-300 mb-3" />
                                        <p className="text-sm font-medium text-slate-700">No contests yet</p>
                                        <p className="text-xs text-slate-500 mt-2">Teachers can create the first olympiad contest from the bank below.</p>
                                    </div>
                                ) : (
                                    contests.map((contest) => {
                                        const status = getStatus(contest);
                                        return (
                                            <button key={contest.id} onClick={() => openContest(contest.id)} className={`w-full rounded-2xl border px-4 py-4 text-left transition-all ${selectedContestId === contest.id ? 'border-cyan-200 bg-cyan-50' : 'border-slate-100 bg-white hover:border-slate-200 hover:bg-slate-50'}`}>
                                                <div className="flex items-start justify-between gap-3">
                                                    <div>
                                                        <p className="text-sm font-semibold text-slate-950">{contest.title}</p>
                                                        <p className="text-xs text-slate-500 mt-1">{contest.questions.length} problems · by {contest.createdByName}</p>
                                                    </div>
                                                    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusClass[status]}`}>{status}</span>
                                                </div>
                                                <div className="flex items-center gap-3 text-xs text-slate-500 mt-4">
                                                    <span className="inline-flex items-center gap-1"><Clock3 size={12} />{formatDateTime(contest.startTime)}</span>
                                                    <span className="inline-flex items-center gap-1">{contest.visibility === 'private' ? <Lock size={12} /> : <Eye size={12} />}{contest.visibility}</span>
                                                </div>
                                            </button>
                                        );
                                    })
                                )}
                            </div>
                            {user?.role === 'teacher' && (
                                <div className="mt-6 rounded-[28px] border border-slate-100 bg-slate-50 p-5">
                                    <div className="flex items-center justify-between mb-4">
                                        <div>
                                            <h3 className="text-lg font-semibold text-slate-950">Create Contest</h3>
                                            <p className="text-sm text-slate-500 mt-1">Snapshot olympiad problems into a locked contest window.</p>
                                        </div>
                                        <Plus size={18} className="text-cyan-600" />
                                    </div>
                                    <div className="space-y-3">
                                        <input value={contestForm.title} onChange={(event) => setContestForm((current) => ({ ...current, title: event.target.value }))} placeholder="Contest title" className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm focus:outline-none focus:border-cyan-500" />
                                        <div className="grid sm:grid-cols-2 gap-3">
                                            <input type="datetime-local" value={contestForm.startTime} onChange={(event) => setContestForm((current) => ({ ...current, startTime: event.target.value }))} className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm focus:outline-none focus:border-cyan-500" />
                                            <input type="datetime-local" value={contestForm.endTime} onChange={(event) => setContestForm((current) => ({ ...current, endTime: event.target.value }))} className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm focus:outline-none focus:border-cyan-500" />
                                        </div>
                                        <div className="grid grid-cols-2 gap-3">
                                            <button onClick={() => setContestForm((current) => ({ ...current, visibility: 'private' }))} className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${contestForm.visibility === 'private' ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-200 text-slate-600'}`}>Private Class</button>
                                            <button onClick={() => setContestForm((current) => ({ ...current, visibility: 'public' }))} className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${contestForm.visibility === 'public' ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-200 text-slate-600'}`}>Public</button>
                                        </div>
                                        {problemBankStatus && <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-800">{problemBankStatus}</div>}
                                        <input value={problemSearch} onChange={(event) => setProblemSearch(event.target.value)} placeholder="Search olympiad bank" className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm focus:outline-none focus:border-cyan-500" />
                                        <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                                            {filteredProblems.slice(0, 30).map((problem) => {
                                                const selected = selectedProblems.some((item) => item.questionId === problem.questionId);
                                                return (
                                                    <button key={problem.questionId} onClick={() => toggleProblem(problem)} className={`w-full rounded-2xl border px-4 py-3 text-left ${selected ? 'border-cyan-500 bg-cyan-50' : 'border-slate-100 bg-white hover:border-slate-200'}`}>
                                                        <div className="flex items-start justify-between gap-3">
                                                            <div>
                                                                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{problem.competition} · {problem.topic}</p>
                                                                <p className="text-sm font-medium text-slate-900 mt-2 line-clamp-3">{problem.statement}</p>
                                                            </div>
                                                            <span className="text-xs font-semibold text-cyan-700 bg-white px-2 py-1 rounded-full">{problem.difficultyRating}</span>
                                                        </div>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                        <div className="rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-600">{selectedProblems.length} / 12 selected · {teacherStudents.length} students on private list</div>
                                        <button onClick={handleCreateContest} disabled={creatingContest || selectedProblems.length === 0} className="w-full rounded-2xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50">{creatingContest ? 'Creating contest...' : 'Create Contest Snapshot'}</button>
                                    </div>
                                </div>
                            )}
                        </motion.div>
                        <motion.div className="rounded-[28px] border border-white/60 bg-white/90 backdrop-blur p-6" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
                            <div className="flex items-center justify-between mb-5">
                                <div>
                                    <h2 className="text-lg font-semibold text-slate-950">{selectedContest?.title || 'Contest Detail'}</h2>
                                    <p className="text-sm text-slate-500 mt-1">{selectedContest ? `${formatDateTime(selectedContest.startTime)} to ${formatDateTime(selectedContest.endTime)}` : 'Select a contest to inspect problems, leaderboard, and fairness output.'}</p>
                                </div>
                                {selectedContest && <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusClass[getStatus(selectedContest)]}`}>{getStatus(selectedContest)}</span>}
                            </div>
                            {!selectedContest ? <div className="min-h-[420px] flex items-center justify-center text-sm text-slate-500">Open a contest from the board to continue.</div> :
                                <div className="grid lg:grid-cols-[1fr_0.95fr] gap-5">
                                    <div className="rounded-2xl border border-slate-100 p-5">
                                        <div className="flex items-center justify-between mb-4">
                                            <div>
                                                <h3 className="text-lg font-semibold text-slate-950">Problems</h3>
                                                <p className="text-sm text-slate-500 mt-1">{countdown}</p>
                                            </div>
                                            <Users size={17} className="text-cyan-600" />
                                        </div>
                                        <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
                                            {selectedContest.questions.map((question, index) => (
                                                <div key={question.questionId} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-4">
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div>
                                                            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Problem {index + 1} · {question.topic}</p>
                                                            <p className="text-sm font-medium text-slate-900 mt-2 whitespace-pre-wrap">{question.statement}</p>
                                                        </div>
                                                        <span className="text-xs font-semibold text-cyan-700 bg-white px-2 py-1 rounded-full">{question.difficultyRating}</span>
                                                    </div>
                                                    {user?.role === 'student' && attemptStartedAt && !mySubmission && getStatus(selectedContest) === 'LIVE' && <input type="number" min="0" max="99" value={answers[question.questionId] ?? ''} onChange={(event) => setAnswers((current) => ({ ...current, [question.questionId]: event.target.value }))} placeholder="00-99" className="mt-4 w-28 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:border-cyan-500" />}
                                                </div>
                                            ))}
                                        </div>
                                        {user?.role === 'student' && (
                                            <div className="mt-5">
                                                {mySubmission ? <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-4 text-sm text-emerald-800">Submission recorded. Score {mySubmission.totalCorrect || 0}, time {mySubmission.totalTime || 0}s.</div> :
                                                    getStatus(selectedContest) === 'UPCOMING' ? <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-4 text-sm text-amber-800">Contest has not started yet.</div> :
                                                        getStatus(selectedContest) === 'COMPLETED' ? <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-4 text-sm text-slate-600">Contest window is closed. Leaderboard is frozen.</div> :
                                                            !attemptStartedAt ? <button onClick={startContest} className="w-full rounded-2xl bg-cyan-600 px-4 py-3 text-sm font-semibold text-white hover:bg-cyan-700">Start Contest Timer</button> :
                                                                <button onClick={submitContest} disabled={submittingContest} className="w-full rounded-2xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50">{submittingContest ? 'Submitting contest...' : 'Submit Final Answers'}</button>}
                                            </div>
                                        )}
                                    </div>
                                    <div className="space-y-5">
                                        <div className="rounded-2xl border border-slate-100 p-5">
                                            <h3 className="text-lg font-semibold text-slate-950">Leaderboard</h3>
                                            <p className="text-sm text-slate-500 mt-1 mb-4">Sorted by score, total time, then difficulty solved.</p>
                                            <div className="space-y-3">
                                                {leaderboard.length === 0 ? <p className="text-sm text-slate-500">Leaderboard appears after the first evaluated submission.</p> : leaderboard.map((entry) => (
                                                    <div key={entry.userId} className="flex items-center justify-between rounded-2xl border border-slate-100 px-4 py-3">
                                                        <div>
                                                            <p className="text-sm font-semibold text-slate-900">{entry.rank ? `#${entry.rank}` : 'DQ'} · {entry.displayName || entry.userId}</p>
                                                            <p className="text-xs text-slate-500 mt-1">{entry.score} correct · {entry.totalTime}s · difficulty {entry.difficultySolved}</p>
                                                        </div>
                                                        <div className="text-right">
                                                            <p className="text-sm font-semibold text-cyan-700">{entry.newRating}</p>
                                                            <p className="text-xs text-slate-400">{entry.ratingChange >= 0 ? '+' : ''}{entry.ratingChange}</p>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                        <div className="rounded-2xl border border-slate-100 p-5">
                                            <div className="flex items-center gap-2 mb-4"><ShieldCheck size={17} className="text-cyan-600" /><h3 className="text-lg font-semibold text-slate-950">Fairness Output</h3></div>
                                            {mySubmission ? (
                                                <div className="space-y-3">
                                                    <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3"><p className="text-xs uppercase tracking-[0.14em] text-slate-400">Validity</p><p className="text-sm font-semibold text-slate-900 mt-2">{mySubmission.isValid ? 'Accepted' : 'Flagged / disqualified'}</p></div>
                                                    <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3"><p className="text-xs uppercase tracking-[0.14em] text-slate-400">Flags</p><div className="mt-2 space-y-2">{(mySubmission.fairnessFlags || []).length === 0 ? <p className="text-sm text-slate-600">No anomalies detected.</p> : mySubmission.fairnessFlags.map((flag) => <p key={flag} className="text-sm text-slate-700">{flag}</p>)}</div></div>
                                                </div>
                                            ) : <p className="text-sm text-slate-500">Your audit signals appear here after evaluation.</p>}
                                        </div>
                                    </div>
                                </div>}
                        </motion.div>
                    </div>
                </div>
            </PageTransition>
        </div>
    );
}
