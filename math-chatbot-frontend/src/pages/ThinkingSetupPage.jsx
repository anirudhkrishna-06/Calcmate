import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Brain, ArrowRight, BookOpen, Calendar, Bell } from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';

export default function ThinkingSetupPage() {
    const navigate = useNavigate();
    const [grade, setGrade] = useState('');
    const [topic, setTopic] = useState('');

    const grades = ['6', '7', '8', '9', '10', '11', '12'];
    const topics = [
        'Algebra', 'Geometry', 'Calculus', 'Trigonometry', 'Statistics', 'Probability', 'Arithmetic'
    ];

    const handleStart = () => {
        if (grade && topic) {
            // Save to localStorage as a placeholder for the Learning Layer
            localStorage.setItem('thinking_session_grade', grade);
            localStorage.setItem('thinking_session_topic', topic);
            navigate('/thinking-session');
        }
    };

    return (
        <div className="min-h-screen bg-gray-50">
            <Navbar />
            <PageTransition>
                <div className="max-w-4xl mx-auto px-4 py-12">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-white rounded-3xl shadow-xl p-8 border border-blue-100"
                    >
                        <div className="text-center mb-10">
                            <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-6 transform rotate-3">
                                <Brain size={32} className="text-blue-600" />
                            </div>
                            <h1 className="text-4xl font-extrabold text-gray-900 mb-4 tracking-tight">Live Thinking Session</h1>
                            <p className="text-lg text-gray-500">Transform how you learn math by focusing on the process, not just the final answer.</p>
                        </div>

                        <div className="space-y-8">
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-3">Select Grade Context</label>
                                <div className="grid grid-cols-4 md:grid-cols-7 gap-3">
                                    {grades.map(g => (
                                        <button
                                            key={g}
                                            onClick={() => setGrade(g)}
                                            className={`py-3 rounded-xl border-2 transition-all font-medium ${grade === g ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-gray-200 hover:border-blue-300 text-gray-600 hover:bg-gray-50'}`}
                                        >
                                            {g}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-3">Select Math Topic</label>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                    {topics.map(t => (
                                        <button
                                            key={t}
                                            onClick={() => setTopic(t)}
                                            className={`py-3 px-4 rounded-xl border-2 transition-all font-medium text-sm ${topic === t ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-gray-200 hover:border-blue-300 text-gray-600 hover:bg-gray-50'}`}
                                        >
                                            {t}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <button
                                onClick={handleStart}
                                disabled={!grade || !topic}
                                className="w-full mt-8 py-4 bg-blue-600 text-white rounded-xl font-bold text-lg hover:bg-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transform active:scale-[0.98]"
                            >
                                Start Session <ArrowRight size={20} />
                            </button>
                        </div>
                    </motion.div>

                    {/* Learning Layer UI Placeholders */}
                    <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="bg-white p-6 rounded-2xl border border-gray-100 flex items-start gap-4 shadow-sm opacity-80 cursor-default">
                            <BookOpen className="text-purple-500 flex-shrink-0" />
                            <div>
                                <h3 className="font-semibold text-gray-900">Syllabus Mapping</h3>
                                <p className="text-xs text-gray-500 mt-1">Maps to CBSE Curriculum standards automatically.</p>
                            </div>
                        </div>
                        <div className="bg-white p-6 rounded-2xl border border-gray-100 flex items-start gap-4 shadow-sm opacity-80 cursor-default">
                            <Calendar className="text-green-500 flex-shrink-0" />
                            <div>
                                <h3 className="font-semibold text-gray-900">Topic Scheduling</h3>
                                <p className="text-xs text-gray-500 mt-1">Spaced repetition based on your historical performance.</p>
                            </div>
                        </div>
                        <div className="bg-white p-6 rounded-2xl border border-gray-100 flex items-start gap-4 shadow-sm opacity-80 cursor-default">
                            <Bell className="text-orange-500 flex-shrink-0" />
                            <div>
                                <h3 className="font-semibold text-gray-900">Missed Topics</h3>
                                <p className="text-xs text-gray-500 mt-1">Reminders for topics that need review.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </PageTransition>
        </div>
    );
}
