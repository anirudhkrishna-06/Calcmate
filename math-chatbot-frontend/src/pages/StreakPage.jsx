import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Flame, Calendar, TrendingUp, Target, Zap } from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';

const STREAK_KEY = 'mathmend_streak';
const SESSIONS_KEY = 'mathmend_chat_sessions';

function getStreakData() {
    try {
        const data = JSON.parse(localStorage.getItem(STREAK_KEY) || '{}');
        return {
            currentStreak: data.currentStreak || 0,
            longestStreak: data.longestStreak || 0,
            activeDays: data.activeDays || [],
            totalProblems: data.totalProblems || 0,
        };
    } catch {
        return { currentStreak: 0, longestStreak: 0, activeDays: [], totalProblems: 0 };
    }
}

function computeFromSessions() {
    try {
        const sessions = JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]');
        const daySet = new Set();
        let totalProblems = 0;

        sessions.forEach((s) => {
            if (s.messages) {
                s.messages.forEach((m) => {
                    if (m.type === 'user') {
                        totalProblems++;
                        const d = new Date(m.timestamp).toISOString().slice(0, 10);
                        daySet.add(d);
                    }
                });
            }
        });

        const sortedDays = Array.from(daySet).sort();

        // Calculate current streak
        let currentStreak = 0;
        let longestStreak = 0;
        let tempStreak = 0;
        const today = new Date().toISOString().slice(0, 10);

        if (sortedDays.length > 0) {
            // Check if today or yesterday is in the set for current streak
            const todayDate = new Date();
            const checkDate = new Date(todayDate);

            // Count backwards from today
            for (let i = 0; i < 365; i++) {
                const dateStr = checkDate.toISOString().slice(0, 10);
                if (daySet.has(dateStr)) {
                    currentStreak++;
                    checkDate.setDate(checkDate.getDate() - 1);
                } else if (i === 0) {
                    // Today not active yet, check from yesterday
                    checkDate.setDate(checkDate.getDate() - 1);
                    continue;
                } else {
                    break;
                }
            }

            // Longest streak
            for (let i = 0; i < sortedDays.length; i++) {
                if (i === 0) {
                    tempStreak = 1;
                } else {
                    const prev = new Date(sortedDays[i - 1]);
                    const curr = new Date(sortedDays[i]);
                    const diff = (curr - prev) / 86400000;
                    tempStreak = diff === 1 ? tempStreak + 1 : 1;
                }
                longestStreak = Math.max(longestStreak, tempStreak);
            }
        }

        // Save computed data
        const streakData = {
            currentStreak,
            longestStreak,
            activeDays: sortedDays,
            totalProblems,
        };
        localStorage.setItem(STREAK_KEY, JSON.stringify(streakData));

        return streakData;
    } catch {
        return { currentStreak: 0, longestStreak: 0, activeDays: [], totalProblems: 0 };
    }
}

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
    const [streakData, setStreakData] = useState({ currentStreak: 0, longestStreak: 0, activeDays: [], totalProblems: 0 });

    useEffect(() => {
        const data = computeFromSessions();
        setStreakData(data);
    }, []);

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
            color: 'text-blue-600',
            bg: 'bg-blue-50',
        },
        {
            label: 'Total Problems',
            value: streakData.totalProblems,
            unit: 'solved',
            icon: Zap,
            color: 'text-blue-600',
            bg: 'bg-blue-50',
        },
        {
            label: 'Active Days',
            value: streakData.activeDays.length,
            unit: 'total',
            icon: Calendar,
            color: 'text-blue-600',
            bg: 'bg-blue-50',
        },
    ];

    return (
        <div className="min-h-screen bg-gray-50">
            <Navbar />
            <PageTransition>
                <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
                    {/* Header */}
                    <motion.div
                        className="mb-8"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                    >
                        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
                            <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
                                <TrendingUp size={20} className="text-blue-600" />
                            </div>
                            Problem Streak Analysis
                        </h1>
                        <p className="mt-2 text-gray-500 text-sm">
                            Track your daily problem-solving consistency
                        </p>
                    </motion.div>

                    {/* Stat Cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                        {statCards.map((stat, idx) => {
                            const Icon = stat.icon;
                            return (
                                <motion.div
                                    key={stat.label}
                                    className="bg-white rounded-2xl border border-gray-100 p-5"
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

                    {/* Heatmap Calendar */}
                    <motion.div
                        className="bg-white rounded-2xl border border-gray-100 p-6"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.4 }}
                    >
                        <h2 className="text-base font-semibold text-gray-900 mb-1">Activity Heatmap</h2>
                        <p className="text-xs text-gray-400 mb-6">Last 20 weeks of problem-solving activity</p>

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

                        {/* Legend */}
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

                    {/* Tip */}
                    {streakData.totalProblems === 0 && (
                        <motion.div
                            className="mt-6 bg-blue-50 border border-blue-100 rounded-xl px-5 py-4"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.8 }}
                        >
                            <p className="text-sm text-blue-700 font-medium mb-1">
                                Start your streak!
                            </p>
                            <p className="text-xs text-blue-600">
                                Head to "Ask a Question" and solve your first problem to begin tracking your streak.
                            </p>
                        </motion.div>
                    )}
                </div>
            </PageTransition>
        </div>
    );
}
