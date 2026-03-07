import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, MessageSquare, Brain, TrendingUp, Sparkles } from 'lucide-react';
import PageTransition from '../components/PageTransition';

// Floating math symbols for background
const SYMBOLS = ['∫', 'π', '∑', '√', 'Δ', '∞', 'θ', 'λ', '∂', 'φ', '±', '÷'];

function FloatingSymbol({ symbol, delay, x, y }) {
    return (
        <motion.span
            className="absolute text-blue-100 font-light select-none pointer-events-none"
            style={{ left: `${x}%`, top: `${y}%`, fontSize: `${Math.random() * 24 + 18}px` }}
            initial={{ opacity: 0, y: 20 }}
            animate={{
                opacity: [0, 0.6, 0],
                y: [20, -30, -60],
            }}
            transition={{
                duration: 8,
                delay,
                repeat: Infinity,
                ease: 'easeInOut',
            }}
        >
            {symbol}
        </motion.span>
    );
}

export default function LandingPage() {
    const navigate = useNavigate();
    const [symbols] = useState(() =>
        SYMBOLS.map((s, i) => ({
            symbol: s,
            delay: i * 0.7,
            x: Math.random() * 90 + 5,
            y: Math.random() * 80 + 10,
        }))
    );

    const features = [
        {
            icon: MessageSquare,
            title: 'Ask a Question',
            desc: 'Get step-by-step solutions to any math problem using our AI-powered solver.',
        },
        {
            icon: Brain,
            title: 'Take a Quiz',
            desc: 'Test your knowledge with adaptive quizzes tailored to your skill level.',
        },
        {
            icon: TrendingUp,
            title: 'Track Streaks',
            desc: 'Build consistency with daily problem-solving streaks and visual analytics.',
        },
    ];

    return (
        <PageTransition className="min-h-screen bg-white relative overflow-hidden">
            {/* Floating background symbols */}
            <div className="absolute inset-0 overflow-hidden">
                {symbols.map((s, i) => (
                    <FloatingSymbol key={i} {...s} />
                ))}
            </div>

            {/* Top bar */}
            <header className="relative z-10 flex items-center justify-between px-6 lg:px-12 py-5">
                <div className="flex items-center gap-2">
                    <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center">
                        <span className="text-white font-bold text-base">M</span>
                    </div>
                    <span className="text-xl font-bold text-gray-900 tracking-tight">
                        Math<span className="text-blue-600">Mend</span>
                    </span>
                </div>
                <button
                    onClick={() => navigate('/login')}
                    className="text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors px-4 py-2 rounded-lg hover:bg-blue-50"
                >
                    Sign In
                </button>
            </header>

            {/* Hero */}
            <main className="relative z-10 max-w-5xl mx-auto px-6 lg:px-12 pt-16 lg:pt-28 pb-20">
                <motion.div
                    className="text-center"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.7, ease: 'easeOut' }}
                >
                    <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-blue-50 text-blue-700 rounded-full text-sm font-medium mb-6">
                        <Sparkles size={14} />
                        AI-Powered Math Solver
                    </div>

                    <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-gray-900 leading-tight tracking-tight">
                        Solve Math Problems
                        <br />
                        <span className="text-blue-600">Effortlessly</span>
                    </h1>

                    <p className="mt-6 text-lg text-gray-500 max-w-2xl mx-auto leading-relaxed">
                        Upload an image or type your question. Our neuro-symbolic AI engine
                        provides step-by-step solutions, tracks your progress, and helps you
                        improve.
                    </p>

                    <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
                        <motion.button
                            onClick={() => navigate('/login')}
                            className="flex items-center gap-2 px-8 py-3.5 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-all duration-200 shadow-lg shadow-blue-600/25 hover:shadow-blue-600/40"
                            whileHover={{ scale: 1.03 }}
                            whileTap={{ scale: 0.98 }}
                        >
                            Get Started
                            <ArrowRight size={18} />
                        </motion.button>
                        <button
                            onClick={() => {
                                document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
                            }}
                            className="px-8 py-3.5 text-gray-600 font-medium rounded-xl hover:bg-gray-50 border border-gray-200 transition-all duration-200"
                        >
                            Learn More
                        </button>
                    </div>
                </motion.div>

                {/* Features */}
                <section id="features" className="mt-32">
                    <motion.div
                        className="text-center mb-16"
                        initial={{ opacity: 0 }}
                        whileInView={{ opacity: 1 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                    >
                        <h2 className="text-3xl font-bold text-gray-900">
                            Everything You Need
                        </h2>
                        <p className="mt-3 text-gray-500">
                            A complete toolkit for mastering mathematics.
                        </p>
                    </motion.div>

                    <div className="grid md:grid-cols-3 gap-6">
                        {features.map((feat, idx) => {
                            const Icon = feat.icon;
                            return (
                                <motion.div
                                    key={feat.title}
                                    className="group bg-white border border-gray-100 rounded-2xl p-8 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-50 transition-all duration-300 cursor-default"
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    viewport={{ once: true }}
                                    transition={{ duration: 0.5, delay: idx * 0.15 }}
                                >
                                    <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-5 group-hover:bg-blue-100 transition-colors">
                                        <Icon size={22} className="text-blue-600" />
                                    </div>
                                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                        {feat.title}
                                    </h3>
                                    <p className="text-gray-500 text-sm leading-relaxed">
                                        {feat.desc}
                                    </p>
                                </motion.div>
                            );
                        })}
                    </div>
                </section>
            </main>

            {/* Footer */}
            <footer className="relative z-10 border-t border-gray-100 py-8">
                <p className="text-center text-sm text-gray-400">
                    © 2026 MathMend. Built with precision.
                </p>
            </footer>
        </PageTransition>
    );
}
