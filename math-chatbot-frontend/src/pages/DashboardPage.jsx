import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import {
    MessageSquare,
    Brain,
    User,
    TrendingUp,
    Target,
    ArrowRight,
    Clock,
    Lightbulb,
    Activity,
    BarChart3,
    Trophy,
} from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';
import { getRecentChats, getUserAnalytics, listUserChats, syncUserAnalyticsFromChats } from '../services/userData';
import { getUserRatingProfile, listVisibleContests } from '../services/contestData';

export default function DashboardPage() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [recentActivity, setRecentActivity] = useState([]);
    const [analytics, setAnalytics] = useState({
        weakTopics: [],
        mostAskedTopics: [],
        activityLevel: 'New',
        totalQuestions: 0,
        activeDays: 0,
        totalSessions: 0,
    });
    const [ratingProfile, setRatingProfile] = useState({ currentRating: 0, maxRating: 0, contestsPlayed: 0 });
    const [contestSummary, setContestSummary] = useState({ live: 0, upcoming: 0 });

    useEffect(() => {
        let isMounted = true;

        const loadRecentActivity = async () => {
            if (!user?.id) return;

            try {
                const [recentChats, allChats, storedAnalytics, rating, contests] = await Promise.all([
                    getRecentChats(user.id, 5),
                    listUserChats(user.id, 100),
                    getUserAnalytics(user.id),
                    getUserRatingProfile(user.id),
                    listVisibleContests(user, 20),
                ]);
                if (!isMounted) return;

                const analyticsData =
                    storedAnalytics?.updatedAt || allChats.length === 0
                        ? storedAnalytics
                        : await syncUserAnalyticsFromChats(user.id, allChats);

                setRecentActivity(recentChats.filter((session) => (session.messages || []).length > 0));
                setAnalytics(analyticsData);
                setRatingProfile(rating);
                setContestSummary({
                    live: contests.filter((contest) => {
                        const now = Date.now();
                        return now >= new Date(contest.startTime).getTime() && now <= new Date(contest.endTime).getTime();
                    }).length,
                    upcoming: contests.filter((contest) => Date.now() < new Date(contest.startTime).getTime()).length,
                });
            } catch (error) {
                console.error('Error loading recent conversations:', error);
            }
        };

        loadRecentActivity();

        return () => {
            isMounted = false;
        };
    }, [user?.id]);

    const getGreeting = () => {
        const h = new Date().getHours();
        if (h < 12) return 'Good morning';
        if (h < 17) return 'Good afternoon';
        return 'Good evening';
    };

    const cards = [
        {
            title: 'Thinking IDE',
            desc: 'Enter the audio-first cognitive runtime for real-time thinking traces.',
            icon: Lightbulb,
            color: 'blue',
            path: '/thinking-setup',
            badge: 'Phase 2',
        },
        {
            title: 'Ask a Question',
            desc: 'Chat with our AI solver. Upload images or type your math problem.',
            icon: MessageSquare,
            color: 'blue',
            path: '/chat',
            badge: null,
        },
        {
            title: 'Quiz',
            desc: 'Test your math skills with adaptive quizzes across different topics.',
            icon: Brain,
            color: 'blue',
            path: '/quiz',
            badge: null,
        },
        {
            title: 'Contests',
            desc: 'Join time-bound olympiad contests with rating updates and leaderboard tracking.',
            icon: Trophy,
            color: 'blue',
            path: '/contests',
            badge: contestSummary.live > 0 ? 'Live Now' : contestSummary.upcoming > 0 ? 'Upcoming' : null,
        },
        {
            title: 'Profile',
            desc: 'View and manage your account, preferences, and learning stats.',
            icon: User,
            color: 'blue',
            path: '/profile',
            badge: null,
        },
        {
            title: 'Problem Streak',
            desc: 'Track your daily problem-solving streak and consistency analysis.',
            icon: TrendingUp,
            color: 'blue',
            path: '/streak',
            badge: null,
        },
    ];

    const colorMap = {
        blue: {
            iconBg: 'bg-blue-100',
            iconText: 'text-blue-600',
            border: 'hover:border-blue-200',
            shadow: 'hover:shadow-blue-50',
        },
    };

    const insightCards = [
        {
            title: 'Student Rating',
            value: `${ratingProfile.currentRating || 0}`,
            helper:
                ratingProfile.contestsPlayed > 0
                    ? `Peak ${ratingProfile.maxRating || 0} across ${ratingProfile.contestsPlayed} contests`
                    : 'Contest rating unlocks after the first evaluated contest',
            icon: Target,
        },
        {
            title: 'Weak Topics',
            value: analytics.weakTopics.length > 0 ? analytics.weakTopics[0].topic : 'No signal yet',
            helper:
                analytics.weakTopics.length > 0
                    ? `${analytics.weakTopics[0].count} questions tracked`
                    : 'Ask a few questions to unlock insights',
            icon: BarChart3,
        },
        {
            title: 'Strong Topic',
            value: analytics.mostAskedTopics.length > 0 ? analytics.mostAskedTopics[0].topic : 'No signal yet',
            helper:
                analytics.mostAskedTopics.length > 0
                    ? `${analytics.mostAskedTopics[0].count} total questions`
                    : 'Topic distribution appears here',
            icon: Activity,
        },
    ];

    return (
        <div className="min-h-screen bg-gray-50">
            <Navbar />
            <PageTransition>
                <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div className="mb-10">
                        <motion.h1
                            className="text-3xl font-bold text-gray-900"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4 }}
                        >
                            {getGreeting()}, {(user?.displayName || user?.name || 'User').split(' ')[0]}
                        </motion.h1>
                        <motion.p
                            className="mt-2 text-gray-500"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 0.4, delay: 0.1 }}
                        >
                            Choose the environment you want to open.
                        </motion.p>
                    </div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-12">
                        {cards.map((card, idx) => {
                            const Icon = card.icon;
                            const colors = colorMap[card.color];
                            return (
                                <motion.button
                                    key={card.title}
                                    onClick={() => navigate(card.path)}
                                    className={`relative text-left bg-white rounded-2xl border border-gray-100 p-6 transition-all duration-300 ${colors.border} ${colors.shadow} hover:shadow-lg group`}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.1 }}
                                    whileHover={{ y: -4 }}
                                >
                                    {card.badge && (
                                        <span className="absolute top-4 right-4 text-[10px] font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                                            {card.badge}
                                        </span>
                                    )}
                                    <div className={`w-11 h-11 ${colors.iconBg} rounded-xl flex items-center justify-center mb-4 group-hover:scale-105 transition-transform`}>
                                        <Icon size={20} className={colors.iconText} />
                                    </div>
                                    <h3 className="text-base font-semibold text-gray-900 mb-1.5">{card.title}</h3>
                                    <p className="text-sm text-gray-500 leading-relaxed mb-4">{card.desc}</p>
                                    <div className="flex items-center text-sm text-blue-600 font-medium group-hover:gap-2 gap-1 transition-all">
                                        Open
                                        <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                                    </div>
                                </motion.button>
                            );
                        })}
                    </div>

                    <div className="grid lg:grid-cols-3 gap-5 mb-12">
                        {insightCards.map((card, idx) => {
                            const Icon = card.icon;
                            return (
                                <motion.div
                                    key={card.title}
                                    className="bg-white rounded-2xl border border-gray-100 p-6"
                                    initial={{ opacity: 0, y: 16 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.35, delay: 0.25 + idx * 0.08 }}
                                >
                                    <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center mb-4">
                                        <Icon size={18} className="text-blue-600" />
                                    </div>
                                    <p className="text-xs uppercase tracking-[0.14em] text-gray-400 mb-2">{card.title}</p>
                                    <p className="text-lg font-semibold text-gray-900">{card.value}</p>
                                    <p className="text-sm text-gray-500 mt-2">{card.helper}</p>
                                </motion.div>
                            );
                        })}
                    </div>

                    <div className="grid lg:grid-cols-2 gap-5 mb-12">
                        <motion.div
                            className="bg-white rounded-2xl border border-gray-100 p-6"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4, delay: 0.45 }}
                        >
                            <div className="flex items-center justify-between mb-5">
                                <div>
                                    <h2 className="text-lg font-semibold text-gray-900">Weak Spot Detection</h2>
                                    <p className="text-sm text-gray-500 mt-1">Topics showing the strongest repeat-demand pattern.</p>
                                </div>
                                <Target size={18} className="text-blue-500" />
                            </div>

                            <div className="space-y-3">
                                {analytics.weakTopics.length === 0 ? (
                                    <p className="text-sm text-gray-500">Insights will appear after a few tagged questions are saved.</p>
                                ) : (
                                    analytics.weakTopics.map((topic) => (
                                        <div key={topic.topic} className="rounded-xl border border-gray-100 bg-gray-50 px-4 py-3">
                                            <div className="flex items-center justify-between gap-3">
                                                <p className="text-sm font-medium text-gray-900">{topic.topic}</p>
                                                <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2 py-1 rounded-full">
                                                    {topic.count} questions
                                                </span>
                                            </div>
                                            <p className="text-xs text-gray-500 mt-2">Weakness score {topic.score} · {topic.share}% of your tracked questions</p>
                                        </div>
                                    ))
                                )}
                            </div>
                        </motion.div>

                        <motion.div
                            className="bg-white rounded-2xl border border-gray-100 p-6"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4, delay: 0.52 }}
                        >
                            <div className="flex items-center justify-between mb-5">
                                <div>
                                    <h2 className="text-lg font-semibold text-gray-900">Most Asked Topics</h2>
                                    <p className="text-sm text-gray-500 mt-1">Your highest-frequency learning lanes so far.</p>
                                </div>
                                <BarChart3 size={18} className="text-blue-500" />
                            </div>

                            <div className="space-y-3">
                                {analytics.mostAskedTopics.length === 0 ? (
                                    <p className="text-sm text-gray-500">Ask questions across different chapters to build your topic map.</p>
                                ) : (
                                    analytics.mostAskedTopics.map((topic, index) => (
                                        <div key={topic.topic} className="flex items-center justify-between rounded-xl border border-gray-100 px-4 py-3">
                                            <div>
                                                <p className="text-sm font-medium text-gray-900">{index + 1}. {topic.topic}</p>
                                                <p className="text-xs text-gray-500 mt-1">{topic.share}% share of total questions</p>
                                            </div>
                                            <div className="text-right">
                                                <p className="text-sm font-semibold text-blue-600">{topic.count}</p>
                                                <p className="text-[11px] text-gray-400">questions</p>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </motion.div>
                    </div>

                    {recentActivity.length > 0 && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4, delay: 0.5 }}
                        >
                            <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Conversations</h2>
                            <div className="bg-white rounded-2xl border border-gray-100 divide-y divide-gray-50">
                                {recentActivity.map((session) => (
                                    <button
                                        key={session.id}
                                        onClick={() => navigate(`/chat?session=${session.id}`)}
                                        className="w-full flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors text-left"
                                    >
                                        <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center flex-shrink-0">
                                            <MessageSquare size={16} className="text-blue-600" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-gray-900 truncate">{session.title || 'Untitled conversation'}</p>
                                            <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
                                                <Clock size={10} />
                                                {new Date(session.updatedAt).toLocaleDateString()}
                                            </p>
                                        </div>
                                        <ArrowRight size={14} className="text-gray-300" />
                                    </button>
                                ))}
                            </div>
                        </motion.div>
                    )}
                </div>
            </PageTransition>
        </div>
    );
}
