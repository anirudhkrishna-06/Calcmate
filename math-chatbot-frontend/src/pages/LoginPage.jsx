import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, ArrowLeft, Loader2 } from 'lucide-react';
import PageTransition from '../components/PageTransition';

export default function LoginPage() {
    const navigate = useNavigate();
    const { login, signup } = useAuth();

    const [isSignUp, setIsSignUp] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [shake, setShake] = useState(false);

    const triggerShake = () => {
        setShake(true);
        setTimeout(() => setShake(false), 500);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsSubmitting(true);

        // Simulate a small network delay
        await new Promise((r) => setTimeout(r, 400));

        let result;
        if (isSignUp) {
            if (!name.trim()) {
                setError('Please enter your name');
                setIsSubmitting(false);
                triggerShake();
                return;
            }
            result = signup(name.trim(), email.trim(), password);
        } else {
            result = login(email.trim(), password);
        }

        setIsSubmitting(false);

        if (result.success) {
            navigate('/dashboard');
        } else {
            setError(result.error);
            triggerShake();
        }
    };

    return (
        <PageTransition className="min-h-screen bg-gray-50 flex flex-col">
            {/* Back link */}
            <div className="p-6">
                <Link
                    to="/"
                    className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
                >
                    <ArrowLeft size={16} />
                    Back to home
                </Link>
            </div>

            <div className="flex-1 flex items-center justify-center px-4 pb-16">
                <motion.div
                    className={`w-full max-w-md ${shake ? 'animate-shake' : ''}`}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                    style={shake ? {
                        animation: 'shake 0.5s ease-in-out',
                    } : {}}
                >
                    {/* Header */}
                    <div className="text-center mb-8">
                        <div className="flex items-center justify-center gap-2 mb-6">
                            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center">
                                <span className="text-white font-bold text-lg">M</span>
                            </div>
                        </div>
                        <h1 className="text-2xl font-bold text-gray-900">
                            {isSignUp ? 'Create your account' : 'Welcome back'}
                        </h1>
                        <p className="mt-2 text-sm text-gray-500">
                            {isSignUp
                                ? 'Start solving math problems with AI'
                                : 'Sign in to continue to MathMend'}
                        </p>
                    </div>

                    {/* Form Card */}
                    <div className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
                        <form onSubmit={handleSubmit} className="space-y-5">
                            {isSignUp && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                                        Full name
                                    </label>
                                    <input
                                        type="text"
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        placeholder="Alex Johnson"
                                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all text-sm"
                                    />
                                </div>
                            )}

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                                    Email address
                                </label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="you@example.com"
                                    required
                                    className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all text-sm"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                                    Password
                                </label>
                                <div className="relative">
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="••••••••"
                                        required
                                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all text-sm pr-10"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                                    >
                                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                            </div>

                            {error && (
                                <motion.p
                                    className="text-sm text-red-500 bg-red-50 px-4 py-2 rounded-lg"
                                    initial={{ opacity: 0, y: -5 }}
                                    animate={{ opacity: 1, y: 0 }}
                                >
                                    {error}
                                </motion.p>
                            )}

                            <button
                                type="submit"
                                disabled={isSubmitting}
                                className="w-full py-2.5 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                            >
                                {isSubmitting ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin" />
                                        {isSignUp ? 'Creating account...' : 'Signing in...'}
                                    </>
                                ) : (
                                    isSignUp ? 'Create account' : 'Sign in'
                                )}
                            </button>
                        </form>

                        <div className="mt-6 text-center">
                            <p className="text-sm text-gray-500">
                                {isSignUp ? 'Already have an account?' : "Don't have an account?"}{' '}
                                <button
                                    onClick={() => {
                                        setIsSignUp(!isSignUp);
                                        setError('');
                                    }}
                                    className="text-blue-600 font-medium hover:text-blue-800 transition-colors"
                                >
                                    {isSignUp ? 'Sign in' : 'Sign up'}
                                </button>
                            </p>
                        </div>
                    </div>

                    {/* Demo credentials hint */}
                    {!isSignUp && (
                        <motion.div
                            className="mt-4 bg-blue-50 border border-blue-100 rounded-xl px-4 py-3"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.6 }}
                        >
                            <p className="text-xs text-blue-700 font-medium mb-1">Demo credentials</p>
                            <p className="text-xs text-blue-600 font-mono">
                                demo@mathmend.com / demo123
                            </p>
                        </motion.div>
                    )}
                </motion.div>
            </div>

            {/* Inline shake keyframe */}
            <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          10%, 30%, 50%, 70%, 90% { transform: translateX(-4px); }
          20%, 40%, 60%, 80% { transform: translateX(4px); }
        }
        .animate-shake { animation: shake 0.5s ease-in-out; }
      `}</style>
        </PageTransition>
    );
}
