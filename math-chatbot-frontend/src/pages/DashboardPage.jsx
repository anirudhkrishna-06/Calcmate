import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import {
    MessageSquare,
    Brain,
    User,
    TrendingUp,
    ArrowRight,
    Clock,
} from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';

export default function DashboardPage() {
    const { user } = useAuth();
    const navigate = useNavigate();

    const getGreeting = () => {
        const h = new Date().getHours();
        if (h < 12) return 'Good morning';
        if (h < 17) return 'Good afternoon';
        return 'Good evening';
    };

    const cards = [
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
            badge: 'Coming Soon',
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
            bg: 'bg-blue-50',
            iconBg: 'bg-blue-100',
            iconText: 'text-blue-600',
            border: 'hover:border-blue-200',
            shadow: 'hover:shadow-blue-50',
        },
    };

    // Get recent activity from localStorage
    const getRecentActivity = () => {
        try {
            const chatSessions = JSON.parse(localStorage.getItem('mathmend_chat_sessions') || '[]');
            const recent = chatSessions
                .filter((s) => s.messages && s.messages.length > 0)
                .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
                .slice(0, 3);
            return recent;
        } catch {
            return [];
        }
    };

    const recentActivity = getRecentActivity();

    return (
        <div className="min-h-screen bg-gray-50">
            <Navbar />
            <PageTransition>
                <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    {/* Welcome Header */}
                    <div className="mb-10">
                        <motion.h1
                            className="text-3xl font-bold text-gray-900"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4 }}
                        >
                            {getGreeting()}, {user?.name?.split(' ')[0] || 'User'}
                        </motion.h1>
                        <motion.p
                            className="mt-2 text-gray-500"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 0.4, delay: 0.1 }}
                        >
                            What would you like to work on today?
                        </motion.p>
                    </div>

                    {/* Feature Cards Grid */}
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
                                    <div
                                        className={`w-11 h-11 ${colors.iconBg} rounded-xl flex items-center justify-center mb-4 group-hover:scale-105 transition-transform`}
                                    >
                                        <Icon size={20} className={colors.iconText} />
                                    </div>
                                    <h3 className="text-base font-semibold text-gray-900 mb-1.5">
                                        {card.title}
                                    </h3>
                                    <p className="text-sm text-gray-500 leading-relaxed mb-4">
                                        {card.desc}
                                    </p>
                                    <div className="flex items-center text-sm text-blue-600 font-medium group-hover:gap-2 gap-1 transition-all">
                                        Open
                                        <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                                    </div>
                                </motion.button>
                            );
                        })}
                    </div>

                    {/* Recent Activity */}
                    {recentActivity.length > 0 && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.4, delay: 0.5 }}
                        >
                            <h2 className="text-lg font-semibold text-gray-900 mb-4">
                                Recent Conversations
                            </h2>
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
                                            <p className="text-sm font-medium text-gray-900 truncate">
                                                {session.title || 'Untitled conversation'}
                                            </p>
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
