import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Award, Target, GitMerge, Search, AlertTriangle, ArrowRight, CheckCircle2 } from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';

export default function ThinkingReportPage() {
    const navigate = useNavigate();
    const timeElapsed = localStorage.getItem('thinking_session_time') || 120; // 2 mins fallback
    
    // Mocked frontend-based scoring logic
    const scores = [
        { name: 'Understanding Quality', score: 92, icon: Target, color: 'text-blue-500', bg: 'bg-blue-50', bar: 'bg-blue-500', desc: "Grasped the core variables quickly." },
        { name: 'Approach Correctness', score: 88, icon: GitMerge, color: 'text-green-500', bg: 'bg-green-50', bar: 'bg-green-500', desc: "Identified the correct relative speed logic." },
        { name: 'Logical Flow', score: 85, icon: CheckCircle2, color: 'text-indigo-500', bg: 'bg-indigo-50', bar: 'bg-indigo-500', desc: "Fluid progression from concept to unit conversion." },
        { name: 'Exploration Behavior', score: 65, icon: Search, color: 'text-purple-500', bg: 'bg-purple-50', bar: 'bg-purple-500', desc: "Hesitant to explore alternative methods." },
        { name: 'Mistake Patterns', score: 95, icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50', bar: 'bg-amber-500', desc: "Avoided common unit conversion pitfalls (High is good)." },
    ];

    const formatTime = (seconds) => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}m ${s}s`;
    };

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
                            <p className="text-blue-100 text-lg opacity-90">You spent {formatTime(timeElapsed)} deeply analyzing the problem.</p>
                        </div>

                        <div className="p-8">
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
