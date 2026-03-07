import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import {
    User,
    Mail,
    Edit3,
    Check,
    X,
    MessageSquare,
    Brain,
    Flame,
    Calendar,
    Settings,
} from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';

export default function ProfilePage() {
    const { user, updateProfile } = useAuth();
    const [isEditing, setIsEditing] = useState(false);
    const [editName, setEditName] = useState(user?.name || '');

    // Compute stats from localStorage
    const [stats, setStats] = useState({
        totalQuestions: 0,
        totalSessions: 0,
        currentStreak: 0,
        memberSince: '',
    });

    useEffect(() => {
        try {
            const sessions = JSON.parse(localStorage.getItem('mathmend_chat_sessions') || '[]');
            const totalMessages = sessions.reduce(
                (sum, s) => sum + (s.messages?.filter((m) => m.type === 'user').length || 0),
                0
            );

            // Streak calc
            const streakData = JSON.parse(localStorage.getItem('mathmend_streak') || '{}');
            const currentStreak = streakData.currentStreak || 0;

            const storedUser = JSON.parse(localStorage.getItem('mathmend_user') || '{}');

            setStats({
                totalQuestions: totalMessages,
                totalSessions: sessions.length,
                currentStreak,
                memberSince: storedUser.joinedAt
                    ? new Date(storedUser.joinedAt).toLocaleDateString([], { month: 'long', year: 'numeric' })
                    : 'February 2026',
            });
        } catch {
            // ignore
        }
    }, []);

    const handleSaveName = () => {
        if (editName.trim()) {
            updateProfile({ name: editName.trim() });
            setIsEditing(false);
        }
    };

    const initials = (user?.name || 'U')
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);

    const statCards = [
        {
            label: 'Questions Asked',
            value: stats.totalQuestions,
            icon: MessageSquare,
        },
        {
            label: 'Chat Sessions',
            value: stats.totalSessions,
            icon: Brain,
        },
        {
            label: 'Current Streak',
            value: `${stats.currentStreak} days`,
            icon: Flame,
        },
        {
            label: 'Member Since',
            value: stats.memberSince,
            icon: Calendar,
        },
    ];

    return (
        <div className="min-h-screen bg-gray-50">
            <Navbar />
            <PageTransition>
                <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
                    {/* Profile Header Card */}
                    <motion.div
                        className="bg-white rounded-2xl border border-gray-100 p-8 mb-6"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4 }}
                    >
                        <div className="flex flex-col sm:flex-row items-center gap-6">
                            {/* Avatar */}
                            <div className="w-24 h-24 bg-blue-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-600/20">
                                <span className="text-white text-3xl font-bold">{initials}</span>
                            </div>

                            {/* Info */}
                            <div className="flex-1 text-center sm:text-left">
                                {isEditing ? (
                                    <div className="flex items-center gap-2 justify-center sm:justify-start">
                                        <input
                                            type="text"
                                            value={editName}
                                            onChange={(e) => setEditName(e.target.value)}
                                            className="text-xl font-bold text-gray-900 border-b-2 border-blue-500 bg-transparent outline-none pb-1 w-48"
                                            autoFocus
                                            onKeyDown={(e) => e.key === 'Enter' && handleSaveName()}
                                        />
                                        <button
                                            onClick={handleSaveName}
                                            className="p-1.5 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors"
                                        >
                                            <Check size={16} />
                                        </button>
                                        <button
                                            onClick={() => {
                                                setIsEditing(false);
                                                setEditName(user?.name || '');
                                            }}
                                            className="p-1.5 bg-gray-50 text-gray-500 rounded-lg hover:bg-gray-100 transition-colors"
                                        >
                                            <X size={16} />
                                        </button>
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-2 justify-center sm:justify-start">
                                        <h1 className="text-xl font-bold text-gray-900">{user?.name}</h1>
                                        <button
                                            onClick={() => setIsEditing(true)}
                                            className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all"
                                        >
                                            <Edit3 size={14} />
                                        </button>
                                    </div>
                                )}
                                <div className="flex items-center gap-2 mt-2 text-gray-500 text-sm justify-center sm:justify-start">
                                    <Mail size={14} />
                                    {user?.email}
                                </div>
                            </div>
                        </div>
                    </motion.div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                        {statCards.map((stat, idx) => {
                            const Icon = stat.icon;
                            return (
                                <motion.div
                                    key={stat.label}
                                    className="bg-white rounded-2xl border border-gray-100 p-5"
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: 0.1 + idx * 0.08 }}
                                >
                                    <div className="w-9 h-9 bg-blue-50 rounded-xl flex items-center justify-center mb-3">
                                        <Icon size={16} className="text-blue-600" />
                                    </div>
                                    <p className="text-lg font-bold text-gray-900">{stat.value}</p>
                                    <p className="text-xs text-gray-500 mt-0.5">{stat.label}</p>
                                </motion.div>
                            );
                        })}
                    </div>

                    {/* Settings Card */}
                    <motion.div
                        className="bg-white rounded-2xl border border-gray-100 p-6"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.5 }}
                    >
                        <div className="flex items-center gap-3 mb-5">
                            <div className="w-9 h-9 bg-gray-50 rounded-xl flex items-center justify-center">
                                <Settings size={16} className="text-gray-600" />
                            </div>
                            <h2 className="text-base font-semibold text-gray-900">Preferences</h2>
                        </div>

                        <div className="space-y-4">
                            <div className="flex items-center justify-between py-3 border-b border-gray-50">
                                <div>
                                    <p className="text-sm font-medium text-gray-700">Email notifications</p>
                                    <p className="text-xs text-gray-400 mt-0.5">
                                        Get notified about streak reminders
                                    </p>
                                </div>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input type="checkbox" className="sr-only peer" defaultChecked />
                                    <div className="w-10 h-5 bg-gray-200 peer-focus:ring-2 peer-focus:ring-blue-200 rounded-full peer peer-checked:after:translate-x-5 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                                </label>
                            </div>

                            <div className="flex items-center justify-between py-3">
                                <div>
                                    <p className="text-sm font-medium text-gray-700">Dark mode</p>
                                    <p className="text-xs text-gray-400 mt-0.5">Coming soon</p>
                                </div>
                                <label className="relative inline-flex items-center cursor-not-allowed opacity-50">
                                    <input type="checkbox" className="sr-only peer" disabled />
                                    <div className="w-10 h-5 bg-gray-200 rounded-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                                </label>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </PageTransition>
        </div>
    );
}
