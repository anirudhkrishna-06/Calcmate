import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
    Activity,
    ArrowRight,
    BarChart3,
    Brain,
    Flame,
    Mail,
    Plus,
    Sparkles,
    Target,
    Users,
    Clock3,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';
import { addStudentToTeacher, createQuizNotification, listTeacherStudents } from '../services/classroomData';

const formatDate = (value) => {
    if (!value) return 'No activity yet';
    return new Date(value).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
};

export default function TeacherDashboardPage() {
    const { user } = useAuth();
    const [students, setStudents] = useState([]);
    const [selectedStudentId, setSelectedStudentId] = useState(null);
    const [studentIdInput, setStudentIdInput] = useState('');
    const [notificationTitle, setNotificationTitle] = useState('Adaptive Quiz Assigned');
    const [notificationBody, setNotificationBody] = useState('Attend today’s adaptive quiz to strengthen your weak spots and update your mastery profile.');
    const [isLoading, setIsLoading] = useState(true);
    const [isLinkingStudent, setIsLinkingStudent] = useState(false);
    const [isSendingNotification, setIsSendingNotification] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');

    const loadStudents = async () => {
        if (!user?.id) return;

        setIsLoading(true);
        try {
            const data = await listTeacherStudents(user.id);
            setStudents(data);
            if (!selectedStudentId && data.length > 0) {
                setSelectedStudentId(data[0].id);
            }
        } catch (error) {
            console.error('Error loading teacher dashboard:', error);
            setStatusMessage(error.message || 'Unable to load classroom data right now.');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadStudents();
    }, [user?.id]);

    const selectedStudent = useMemo(
        () => students.find((student) => student.id === selectedStudentId) || students[0] || null,
        [selectedStudentId, students]
    );

    const classroomOverview = useMemo(() => {
        const totalStudents = students.length;
        const totalQuestions = students.reduce((sum, student) => sum + (student.chatSummary?.totalQuestions || 0), 0);
        const totalThinkingSessions = students.reduce((sum, student) => sum + (student.thinkingSummary?.totalSessions || 0), 0);
        const totalQuizzes = students.reduce((sum, student) => sum + (student.quizSummary?.attended || 0), 0);
        const averageQuizScore =
            totalStudents > 0
                ? students.reduce((sum, student) => sum + (student.quizSummary?.averageScore || 0), 0) / totalStudents
                : 0;
        const averageRating =
            totalStudents > 0
                ? students.reduce((sum, student) => sum + (student.ratingProfile?.currentRating || 0), 0) / totalStudents
                : 0;
        const averageStreak =
            totalStudents > 0
                ? students.reduce((sum, student) => sum + (student.streakSummary?.currentStreak || 0), 0) / totalStudents
                : 0;
        const engagedToday = students.filter((student) =>
            student.streakSummary?.activeDays?.includes(new Date().toISOString().slice(0, 10))
        ).length;

        return {
            totalStudents,
            totalQuestions,
            totalThinkingSessions,
            totalQuizzes,
            averageQuizScore: Number(averageQuizScore.toFixed(1)),
            averageRating: Number(averageRating.toFixed(0)),
            averageStreak: Number(averageStreak.toFixed(1)),
            engagedToday,
        };
    }, [students]);

    const handleAddStudent = async () => {
        if (!studentIdInput.trim() || !user?.id) return;

        setIsLinkingStudent(true);
        setStatusMessage('');
        try {
            await addStudentToTeacher(user.id, studentIdInput.trim());
            setStudentIdInput('');
            setStatusMessage('Student linked successfully.');
            await loadStudents();
        } catch (error) {
            console.error('Error linking student:', error);
            setStatusMessage(error.message || 'Unable to link that student.');
        } finally {
            setIsLinkingStudent(false);
        }
    };

    const handleNotifyClass = async () => {
        if (!user?.id || students.length === 0) return;

        setIsSendingNotification(true);
        setStatusMessage('');
        try {
            await createQuizNotification({
                teacherId: user.id,
                teacherName: user.displayName || user.name || 'Teacher',
                studentIds: students.map((student) => student.id),
                title: notificationTitle.trim(),
                body: notificationBody.trim(),
            });
            setStatusMessage('Quiz notification sent to your classroom.');
        } catch (error) {
            console.error('Error sending quiz notification:', error);
            setStatusMessage(error.message || 'Unable to notify students right now.');
        } finally {
            setIsSendingNotification(false);
        }
    };

    const overviewCards = [
        { label: 'Linked Students', value: classroomOverview.totalStudents, helper: 'Active teacher-student connections', icon: Users },
        { label: 'Tracked Questions', value: classroomOverview.totalQuestions, helper: 'Questions recorded across the classroom', icon: Brain },
        { label: 'Thinking IDE', value: classroomOverview.totalThinkingSessions, helper: 'Completed post-tutoring thinking sessions', icon: Activity },
        { label: 'Quiz Attendance', value: classroomOverview.totalQuizzes, helper: 'Completed adaptive quiz attempts', icon: Mail },
        { label: 'Average Quiz Score', value: `${classroomOverview.averageQuizScore}%`, helper: 'Rolling class performance benchmark', icon: BarChart3 },
        { label: 'Class Rating', value: classroomOverview.averageRating, helper: 'Average contest rating across linked students', icon: Sparkles },
        { label: 'Avg Streak', value: `${classroomOverview.averageStreak}d`, helper: 'Average active streak across linked students', icon: Flame },
    ];

    return (
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.12),_transparent_35%),linear-gradient(180deg,#f8fbff_0%,#f3f6fb_100%)]">
            <Navbar />
            <PageTransition>
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div className="grid xl:grid-cols-[1.15fr_0.85fr] gap-6 mb-6">
                        <motion.div className="relative overflow-hidden rounded-[28px] border border-slate-200 bg-slate-950 text-white p-8" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(96,165,250,0.35),_transparent_40%)]" />
                            <div className="relative">
                                <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-100 mb-5">
                                    <Sparkles size={14} />
                                    Teacher Intelligence Console
                                </div>
                                <h1 className="text-3xl font-bold leading-tight">Monitor learning signals, assign quizzes, and act on weak spots in one place.</h1>
                                <p className="mt-4 max-w-2xl text-sm text-slate-300 leading-7">
                                    This dashboard is connected to the student analytics layer. Every linked student brings in weak topics, topic volume, activity level, recent chat pressure, and adaptive quiz performance.
                                </p>
                            </div>
                        </motion.div>

                        <motion.div className="rounded-[28px] border border-blue-100 bg-white p-6 shadow-[0_24px_60px_-36px_rgba(37,99,235,0.45)]" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.08 }}>
                            <div className="flex items-center justify-between mb-5">
                                <div>
                                    <h2 className="text-lg font-semibold text-gray-900">Assign Quiz Notification</h2>
                                    <p className="text-sm text-gray-500 mt-1">Broadcast an adaptive quiz reminder to every linked student.</p>
                                </div>
                                <Mail size={18} className="text-blue-600" />
                            </div>

                            <div className="space-y-4">
                                <input value={notificationTitle} onChange={(event) => setNotificationTitle(event.target.value)} className="w-full rounded-2xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500" />
                                <textarea value={notificationBody} onChange={(event) => setNotificationBody(event.target.value)} rows={4} className="w-full rounded-2xl border border-gray-200 px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500" />
                                <button onClick={handleNotifyClass} disabled={isSendingNotification || students.length === 0} className="w-full inline-flex items-center justify-center gap-2 rounded-2xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 transition-colors disabled:opacity-50">
                                    <Mail size={16} />
                                    {isSendingNotification ? 'Sending notification…' : 'Notify Entire Classroom'}
                                </button>
                            </div>
                        </motion.div>
                    </div>

                    <div className="grid sm:grid-cols-2 xl:grid-cols-6 gap-4 mb-6">
                        {overviewCards.map((card, index) => {
                            const Icon = card.icon;
                            return (
                                <motion.div key={card.label} className="rounded-2xl border border-gray-100 bg-white p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.12 + index * 0.06 }}>
                                    <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4"><Icon size={18} /></div>
                                    <p className="text-xs uppercase tracking-[0.14em] text-gray-400">{card.label}</p>
                                    <p className="text-2xl font-bold text-gray-900 mt-2">{card.value}</p>
                                    <p className="text-sm text-gray-500 mt-2">{card.helper}</p>
                                </motion.div>
                            );
                        })}
                    </div>

                    <div className="grid xl:grid-cols-[0.78fr_1.22fr] gap-6">
                        <motion.div className="rounded-[28px] border border-gray-100 bg-white p-6" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.18 }}>
                            <div className="flex items-start justify-between gap-4 mb-5">
                                <div>
                                    <h2 className="text-lg font-semibold text-gray-900">Student Network</h2>
                                    <p className="text-sm text-gray-500 mt-1">Add students by their account ID and open their intelligence profile.</p>
                                </div>
                                <Users size={18} className="text-blue-600" />
                            </div>

                            <div className="flex gap-2 mb-5">
                                <input value={studentIdInput} onChange={(event) => setStudentIdInput(event.target.value)} placeholder="Enter student UID" className="flex-1 rounded-2xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500" />
                                <button onClick={handleAddStudent} disabled={isLinkingStudent || !studentIdInput.trim()} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800 transition-colors disabled:opacity-50">
                                    <Plus size={16} />
                                    {isLinkingStudent ? 'Linking…' : 'Add'}
                                </button>
                            </div>

                            {statusMessage && <div className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700 mb-5">{statusMessage}</div>}

                            <div className="space-y-3 max-h-[680px] overflow-y-auto pr-1">
                                {isLoading ? <p className="text-sm text-gray-500">Loading classroom…</p> : students.length === 0 ? (
                                    <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-5 py-8 text-center">
                                        <Users size={20} className="mx-auto text-gray-300 mb-3" />
                                        <p className="text-sm font-medium text-gray-700">No students linked yet</p>
                                        <p className="text-xs text-gray-500 mt-2">Add a student by ID to start monitoring analytics and quiz performance.</p>
                                    </div>
                                ) : (
                                    students.map((student) => (
                                        <button key={student.id} onClick={() => setSelectedStudentId(student.id)} className={`w-full rounded-2xl border px-4 py-4 text-left transition-all ${selectedStudent?.id === student.id ? 'border-blue-200 bg-blue-50 shadow-sm' : 'border-gray-100 bg-white hover:border-gray-200 hover:bg-gray-50'}`}>
                                            <div className="flex items-start justify-between gap-3">
                                                <div>
                                                    <p className="text-sm font-semibold text-gray-900">{student.name}</p>
                                                    <p className="text-xs text-gray-500 mt-1">{student.email}</p>
                                                </div>
                                                <span className="text-[11px] font-semibold text-blue-600 bg-blue-100/80 px-2 py-1 rounded-full">{student.analytics?.activityLevel || 'New'}</span>
                                            </div>
                                            <div className="grid grid-cols-3 gap-3 mt-4 text-xs">
                                                <div className="rounded-xl bg-white/80 border border-gray-100 px-3 py-2"><p className="text-gray-400">Weak Topic</p><p className="text-gray-900 font-medium mt-1">{student.analytics?.weakTopics?.[0]?.topic || 'No signal'}</p></div>
                                                <div className="rounded-xl bg-white/80 border border-gray-100 px-3 py-2"><p className="text-gray-400">Questions</p><p className="text-gray-900 font-medium mt-1">{student.chatSummary?.totalQuestions || 0}</p></div>
                                                <div className="rounded-xl bg-white/80 border border-gray-100 px-3 py-2"><p className="text-gray-400">Rating</p><p className="text-gray-900 font-medium mt-1">{student.ratingProfile?.currentRating || 0}</p></div>
                                            </div>
                                        </button>
                                    ))
                                )}
                            </div>
                        </motion.div>

                        <motion.div className="rounded-[28px] border border-gray-100 bg-white p-6" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.24 }}>
                            <div className="mb-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
                                <div className="rounded-[24px] border border-slate-200 bg-slate-950 p-5 text-white">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Classroom Pulse</p>
                                            <p className="mt-3 text-2xl font-bold">{classroomOverview.engagedToday} students active today</p>
                                        </div>
                                        <Activity size={18} className="text-cyan-300" />
                                    </div>
                                    <p className="mt-3 text-sm leading-7 text-slate-300">
                                        Consistency now reflects questions, quizzes, and contest participation, so the classroom signal is based on real usage across the app.
                                    </p>
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-4">
                                        <p className="text-xs uppercase tracking-[0.14em] text-blue-500">Avg Streak</p>
                                        <p className="mt-2 text-2xl font-bold text-blue-900">{classroomOverview.averageStreak}d</p>
                                    </div>
                                    <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-4">
                                        <p className="text-xs uppercase tracking-[0.14em] text-amber-600">Today</p>
                                        <p className="mt-2 text-2xl font-bold text-amber-900">{classroomOverview.engagedToday}</p>
                                    </div>
                                </div>
                            </div>
                            {!selectedStudent ? (
                                <div className="h-full min-h-[420px] flex items-center justify-center text-center">
                                    <div>
                                        <Target size={22} className="mx-auto text-gray-300 mb-3" />
                                        <p className="text-sm font-medium text-gray-700">Select a student to open the intelligence view.</p>
                                    </div>
                                </div>
                            ) : (
                                <>
                                    <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-6">
                                        <div>
                                            <p className="text-xs uppercase tracking-[0.16em] text-blue-500 font-semibold">Student Intelligence</p>
                                            <h2 className="text-2xl font-bold text-gray-900 mt-2">{selectedStudent.name}</h2>
                                            <p className="text-sm text-gray-500 mt-2">{selectedStudent.email}</p>
                                            <p className="text-xs text-gray-400 mt-2">Linked on {formatDate(selectedStudent.linkedAt)}</p>
                                        </div>
                                            <div className="grid grid-cols-2 gap-3 min-w-[280px]">
                                                <div className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3"><p className="text-xs text-blue-500 uppercase tracking-[0.14em]">Activity</p><p className="text-lg font-semibold text-blue-900 mt-2">{selectedStudent.analytics?.activityLevel || 'New'}</p></div>
                                                <div className="rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3"><p className="text-xs text-gray-400 uppercase tracking-[0.14em]">Contest Rating</p><p className="text-lg font-semibold text-gray-900 mt-2">{selectedStudent.ratingProfile?.currentRating || 0}</p></div>
                                            </div>
                                    </div>

                                    <div className="grid md:grid-cols-3 gap-4 mb-6">
                                        <div className="rounded-2xl border border-gray-100 p-4"><div className="flex items-center gap-2 text-sm font-semibold text-gray-900 mb-2"><Target size={15} className="text-blue-600" />Weak Spots</div><div className="space-y-2">{(selectedStudent.analytics?.weakTopics || []).slice(0, 3).map((topic) => <div key={topic.topic} className="rounded-xl bg-gray-50 px-3 py-2"><p className="text-sm font-medium text-gray-900">{topic.topic}</p><p className="text-xs text-gray-500 mt-1">{topic.count} questions · score {topic.score}</p></div>)}{(selectedStudent.analytics?.weakTopics || []).length === 0 && <p className="text-sm text-gray-500">Not enough data yet.</p>}</div></div>
                                        <div className="rounded-2xl border border-gray-100 p-4"><div className="flex items-center gap-2 text-sm font-semibold text-gray-900 mb-2"><Brain size={15} className="text-blue-600" />Thinking + Chat</div><div className="space-y-3 text-sm text-gray-600"><div className="flex items-center justify-between"><span>Chat sessions</span><span className="font-semibold text-gray-900">{selectedStudent.chatSummary?.totalSessions || 0}</span></div><div className="flex items-center justify-between"><span>Thinking IDE sessions</span><span className="font-semibold text-gray-900">{selectedStudent.thinkingSummary?.totalSessions || 0}</span></div><div className="flex items-center justify-between"><span>Total questions</span><span className="font-semibold text-gray-900">{selectedStudent.chatSummary?.totalQuestions || 0}</span></div><div><p className="text-xs uppercase tracking-[0.14em] text-gray-400 mb-2">Latest IDE completion</p><p className="font-medium text-gray-900">{selectedStudent.thinkingSummary?.latestTopic || 'No thinking session yet'}</p><p className="text-xs text-gray-500 mt-1">{formatDate(selectedStudent.thinkingSummary?.latestCompletedAt)}</p></div></div></div>
                                        <div className="rounded-2xl border border-gray-100 p-4"><div className="flex items-center gap-2 text-sm font-semibold text-gray-900 mb-2"><Activity size={15} className="text-blue-600" />Contest + Quiz</div><div className="space-y-3 text-sm text-gray-600"><div className="flex items-center justify-between"><span>Contests played</span><span className="font-semibold text-gray-900">{selectedStudent.ratingProfile?.contestsPlayed || 0}</span></div><div className="flex items-center justify-between"><span>Quiz average</span><span className="font-semibold text-gray-900">{selectedStudent.quizSummary?.averageScore || 0}%</span></div><div className="flex items-center justify-between"><span>Current streak</span><span className="font-semibold text-gray-900">{selectedStudent.streakSummary?.currentStreak || 0}d</span></div><div className="flex items-center justify-between"><span>Last rating change</span><span className="font-semibold text-gray-900">{selectedStudent.ratingProfile?.lastRatingChange || 0}</span></div></div></div>
                                    </div>

                                    <div className="grid lg:grid-cols-[0.92fr_1.08fr] gap-5">
                                        <div className="rounded-2xl border border-gray-100 p-5"><div className="flex items-center justify-between mb-4"><div><h3 className="text-lg font-semibold text-gray-900">Most Asked Topics</h3><p className="text-sm text-gray-500 mt-1">Where the student spends the most attention.</p></div><BarChart3 size={17} className="text-blue-600" /></div><div className="space-y-3">{(selectedStudent.analytics?.mostAskedTopics || []).slice(0, 4).map((topic, index) => <div key={topic.topic} className="flex items-center justify-between rounded-xl border border-gray-100 px-4 py-3"><div><p className="text-sm font-medium text-gray-900">{index + 1}. {topic.topic}</p><p className="text-xs text-gray-500 mt-1">{topic.share}% share of tracked questions</p></div><span className="text-sm font-semibold text-blue-600">{topic.count}</span></div>)}{(selectedStudent.analytics?.mostAskedTopics || []).length === 0 && <p className="text-sm text-gray-500">No topic distribution available yet.</p>}</div></div>
                                        <div className="rounded-2xl border border-gray-100 p-5"><div className="flex items-center justify-between mb-4"><div><h3 className="text-lg font-semibold text-gray-900">Teacher Action Signal</h3><p className="text-sm text-gray-500 mt-1">Fast interpretation of where to intervene next.</p></div><ArrowRight size={17} className="text-blue-600" /></div><div className="rounded-2xl bg-slate-950 text-white p-5"><p className="text-xs uppercase tracking-[0.18em] text-slate-400">Recommended Focus</p><p className="text-2xl font-bold mt-3">{selectedStudent.analytics?.weakTopics?.[0]?.topic || 'Await more student activity'}</p><p className="text-sm text-slate-300 mt-3 leading-7">{selectedStudent.analytics?.weakTopics?.[0] ? `${selectedStudent.name} is repeatedly returning to ${selectedStudent.analytics.weakTopics[0].topic}. The signal combines frequency, recency, persistence, and consistency across the app, which makes this the strongest intervention target right now.` : 'Once the student starts asking questions, attending quizzes, or entering contests, the dashboard will generate a precise intervention direction here.'}</p></div><div className="grid grid-cols-3 gap-3 mt-4"><div className="rounded-xl border border-gray-100 bg-gray-50 px-4 py-3"><p className="text-xs text-gray-400 uppercase tracking-[0.14em]">Average Quiz</p><p className="text-lg font-semibold text-gray-900 mt-2">{selectedStudent.analytics?.averageQuizScore || 0}%</p></div><div className="rounded-xl border border-gray-100 bg-gray-50 px-4 py-3"><p className="text-xs text-gray-400 uppercase tracking-[0.14em]">Questions Asked</p><p className="text-lg font-semibold text-gray-900 mt-2">{selectedStudent.analytics?.totalQuestions || 0}</p></div><div className="rounded-xl border border-gray-100 bg-gray-50 px-4 py-3"><p className="text-xs text-gray-400 uppercase tracking-[0.14em]">Active Days</p><p className="text-lg font-semibold text-gray-900 mt-2">{selectedStudent.streakSummary?.activeDays?.length || 0}</p></div></div><div className="mt-4 rounded-2xl border border-orange-100 bg-orange-50 px-4 py-3 text-sm text-orange-800 flex items-center justify-between"><span className="inline-flex items-center gap-2"><Clock3 size={15} />Consistency signal</span><span className="font-semibold">{selectedStudent.streakSummary?.currentStreak || 0} day streak</span></div></div>
                                    </div>
                                </>
                            )}
                        </motion.div>
                    </div>
                </div>
            </PageTransition>
        </div>
    );
}
