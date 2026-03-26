import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Flame, Calendar, TrendingUp, Target, Zap, Brain, MessageSquare, Trophy } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';
import { listUserChats, syncUserStreakFromChats } from '../services/userData';

// Generate calendar grid for last 20 weeks (140 days)
function generateCalendarGrid(activeDays) {
    const daySet = new Set(activeDays);
    const grid = [];
    const today = new Date();

    for (let i = 139; i >= 0; i--) {
        const d = new Date(today);
        d.setDate(d.getDate() - i);
        const dateStr = d.toISOString().slice(0, 10);
        grid.push({
            date: dateStr,
            active: daySet.has(dateStr),
            dayOfWeek: d.getDay(),
        });
    }

    return grid;
}

export default function StreakPage() {
    const { user } = useAuth();
    const [streakData, setStreakData] = useState({
        currentStreak: 0,
        longestStreak: 0,
        activeDays: [],
        totalActivities: 0,
        chatActivities: 0,
        thinkingActivities: 0,
        quizActivities: 0,
        contestActivities: 0,
        lastActivityAt: null,
    });

    useEffect(() => {
        let isMounted = true;

        const loadStreak = async () => {
            if (!user?.id) return;

            try {
                const chats = await listUserChats(user.id, 100);
                const resolvedStreak = await syncUserStreakFromChats(user.id, chats);

                if (!isMounted) return;

                setStreakData({
                    currentStreak: resolvedStreak.currentStreak || 0,
                    longestStreak: resolvedStreak.longestStreak || 0,
                    activeDays: resolvedStreak.activeDays || [],
                    totalActivities: resolvedStreak.totalActivities || resolvedStreak.totalSolved || 0,
                    chatActivities: resolvedStreak.chatActivities || 0,
                    thinkingActivities: resolvedStreak.thinkingActivities || 0,
                    quizActivities: resolvedStreak.quizActivities || 0,
                    contestActivities: resolvedStreak.contestActivities || 0,
                    lastActivityAt: resolvedStreak.lastActivityAt || null,
                });
            } catch (error) {
                console.error('Error loading streak data:', error);
            }
        };

        loadStreak();

        return () => {
            isMounted = false;
        };
    }, [user?.id]);

    const calendarGrid = useMemo(
        () => generateCalendarGrid(streakData.activeDays),
        [streakData.activeDays]
    );

    // Group by weeks for the grid
    const weeks = useMemo(() => {
        const w = [];
        for (let i = 0; i < calendarGrid.length; i += 7) {
            w.push(calendarGrid.slice(i, i + 7));
        }
        return w;
    }, [calendarGrid]);

    const statCards = [
        {
            label: 'Current Streak',
            value: streakData.currentStreak,
            unit: 'days',
            icon: Flame,
            color: 'text-blue-600',
            bg: 'bg-blue-50',
        },
        {
            label: 'Longest Streak',
            value: streakData.longestStreak,
            unit: 'days',
            icon: Target,
            color: 'text-cyan-700',
            bg: 'bg-cyan-50',
        },
        {
            label: 'Total Activity',
            value: streakData.totalActivities,
            unit: 'events',
            icon: Zap,
            color: 'text-violet-700',
            bg: 'bg-violet-50',
        },
        {
            label: 'Active Days',
            value: streakData.activeDays.length,
            unit: 'total',
            icon: Calendar,
            color: 'text-emerald-700',
            bg: 'bg-emerald-50',
        },
    ];

    const activityMix = [
        { label: 'Questions Asked', value: streakData.chatActivities, icon: MessageSquare, accent: 'from-blue-600 to-cyan-500' },
        { label: 'Thinking IDE', value: streakData.thinkingActivities, icon: Brain, accent: 'from-cyan-600 to-emerald-500' },
        { label: 'Quiz Sessions', value: streakData.quizActivities, icon: Zap, accent: 'from-indigo-600 to-blue-500' },
        { label: 'Contest Runs', value: streakData.contestActivities, icon: Trophy, accent: 'from-amber-500 to-orange-500' },
    ];

    const lastActivityLabel = streakData.lastActivityAt
        ? new Date(streakData.lastActivityAt).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
        : 'No activity yet';

    return (
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(37,99,235,0.12),_transparent_30%),linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)]">
            <Navbar />
            <PageTransition>
                <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
                    <motion.div
                        className="mb-8 rounded-[28px] border border-blue-100/80 bg-slate-950 px-6 py-7 text-white shadow-[0_28px_80px_-48px_rgba(15,23,42,0.9)]"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                    >
                        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                            <div>
                                <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-blue-100">
                                    <TrendingUp size={14} />
                                    Consistency Engine
                                </div>
                                <h1 className="text-2xl font-bold flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-2xl bg-white/10 flex items-center justify-center">
                                        <Flame size={20} className="text-amber-300" />
                                    </div>
                                    Learning Streaks
                                </h1>
                                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
                                    Every meaningful learning action counts here, from asking a question to completing a thinking IDE session, finishing a quiz, or participating in a contest.
                                </p>
                            </div>
                            <div className="grid grid-cols-2 gap-3 min-w-[280px]">
                                <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Current Pace</p>
                                    <p className="mt-2 text-2xl font-bold text-white">{streakData.currentStreak} days</p>
                                </div>
                                <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Last Activity</p>
                                    <p className="mt-2 text-sm font-semibold text-white">{lastActivityLabel}</p>
                                </div>
                            </div>
                        </div>
                    </motion.div>

                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                        {statCards.map((stat, idx) => {
                            const Icon = stat.icon;
                            return (
                                <motion.div
                                    key={stat.label}
                                    className="bg-white rounded-2xl border border-white/80 p-5 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.5)]"
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.08 }}
                                >
                                    <div className={`w-9 h-9 ${stat.bg} rounded-xl flex items-center justify-center mb-3`}>
                                        <Icon size={16} className={stat.color} />
                                    </div>
                                    <div className="flex items-baseline gap-1.5">
                                        <motion.span
                                            className="text-2xl font-bold text-gray-900"
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            transition={{ delay: 0.3 + idx * 0.1 }}
                                        >
                                            {stat.value}
                                        </motion.span>
                                        <span className="text-xs text-gray-400">{stat.unit}</span>
                                    </div>
                                    <p className="text-xs text-gray-500 mt-1">{stat.label}</p>
                                </motion.div>
                            );
                        })}
                    </div>

                    <motion.div
                        className="grid gap-4 md:grid-cols-3 mb-8"
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.2 }}
                    >
                        {activityMix.map((item, index) => {
                            const Icon = item.icon;
                            return (
                                <div key={item.label} className="relative overflow-hidden rounded-[24px] border border-white/80 bg-white p-5 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.5)]">
                                    <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${item.accent}`} />
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{item.label}</p>
                                            <p className="mt-3 text-3xl font-bold text-slate-950">{item.value}</p>
                                        </div>
                                        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-50 text-slate-700">
                                            <Icon size={18} />
                                        </div>
                                    </div>
                                    <p className="mt-3 text-sm text-slate-500">
                                        {index === 0 ? 'Tracked from your chat activity.' : index === 1 ? 'Counted when a full thinking IDE session is completed.' : index === 2 ? 'Counted when a quiz session is completed.' : 'Counted after a contest submission is evaluated.'}
                                    </p>
                                </div>
                            );
                        })}
                    </motion.div>

                    <motion.div
                        className="bg-white rounded-[28px] border border-white/80 p-6 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.5)]"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.4 }}
                    >
                        <h2 className="text-base font-semibold text-gray-900 mb-1">Activity Heatmap</h2>
                        <p className="text-xs text-gray-400 mb-6">Last 20 weeks of real learning activity across questions, thinking sessions, quizzes, and contests</p>

                        <div className="overflow-x-auto">
                            <div className="flex gap-1 min-w-max">
                                {weeks.map((week, wIdx) => (
                                    <div key={wIdx} className="flex flex-col gap-1">
                                        {week.map((day) => (
                                            <motion.div
                                                key={day.date}
                                                className={`w-3.5 h-3.5 rounded-sm transition-colors cursor-default ${day.active
                                                        ? 'bg-blue-500 hover:bg-blue-600'
                                                        : 'bg-gray-100 hover:bg-gray-200'
                                                    }`}
                                                title={`${day.date}${day.active ? ' — Active' : ''}`}
                                                initial={{ opacity: 0, scale: 0 }}
                                                animate={{ opacity: 1, scale: 1 }}
                                                transition={{
                                                    duration: 0.15,
                                                    delay: 0.5 + wIdx * 0.02,
                                                }}
                                            />
                                        ))}
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="flex items-center gap-3 mt-5 text-xs text-gray-400">
                            <span>Less</span>
                            <div className="flex gap-1">
                                <div className="w-3 h-3 rounded-sm bg-gray-100" />
                                <div className="w-3 h-3 rounded-sm bg-blue-200" />
                                <div className="w-3 h-3 rounded-sm bg-blue-400" />
                                <div className="w-3 h-3 rounded-sm bg-blue-600" />
                            </div>
                            <span>More</span>
                        </div>
                    </motion.div>

                    {streakData.totalActivities === 0 && (
                        <motion.div
                            className="mt-6 rounded-2xl border border-blue-100 bg-blue-50 px-5 py-4"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.8 }}
                        >
                            <p className="text-sm text-blue-700 font-medium mb-1">
                                Start your streak!
                            </p>
                            <p className="text-xs text-blue-600">
                                Ask a question, complete a thinking session, take a quiz, or join a contest to begin building your streak.
                            </p>
                        </motion.div>
                    )}
                </div>
            </PageTransition>
        </div>
    );
}
