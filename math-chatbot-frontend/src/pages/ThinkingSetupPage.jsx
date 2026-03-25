import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
    ArrowRight,
    BrainCircuit,
    Flame,
    Sparkles,
    Target,
    Zap,
} from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';
import { useAuth } from '../context/AuthContext';
import { getUserAnalytics, listUserChats, syncUserAnalyticsFromChats } from '../services/userData';

const FALLBACK_TOPICS = [
    { topic: 'Algebra', count: 0, score: 0, share: 0 },
    { topic: 'Geometry', count: 0, score: 0, share: 0 },
    { topic: 'Arithmetic', count: 0, score: 0, share: 0 },
];

export default function ThinkingSetupPage() {
    const navigate = useNavigate();
    const { user } = useAuth();
    const [analytics, setAnalytics] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [selectedTopic, setSelectedTopic] = useState('');
    const [isProMode, setIsProMode] = useState(false);

    useEffect(() => {
        let isMounted = true;

        const loadAnalytics = async () => {
            if (!user?.id) {
                setIsLoading(false);
                return;
            }

            try {
                const storedAnalytics = await getUserAnalytics(user.id);
                let analyticsData = storedAnalytics;

                if (!storedAnalytics?.updatedAt) {
                    const chats = await listUserChats(user.id, 100);
                    analyticsData = chats.length > 0
                        ? await syncUserAnalyticsFromChats(user.id, chats)
                        : storedAnalytics;
                }

                if (!isMounted) return;

                setAnalytics(analyticsData);
                const firstTopic = analyticsData?.weakTopics?.[0]?.topic || FALLBACK_TOPICS[0].topic;
                setSelectedTopic(firstTopic);
            } catch (error) {
                console.error('Unable to load thinking setup analytics:', error);
                if (isMounted) {
                    setSelectedTopic(FALLBACK_TOPICS[0].topic);
                }
            } finally {
                if (isMounted) {
                    setIsLoading(false);
                }
            }
        };

        loadAnalytics();

        return () => {
            isMounted = false;
        };
    }, [user?.id]);

    const recommendedTopics = useMemo(() => {
        const weakTopics = analytics?.weakTopics?.slice(0, 3) || [];
        return weakTopics.length > 0 ? weakTopics : FALLBACK_TOPICS;
    }, [analytics]);

    const selectedTopicData = recommendedTopics.find((topic) => topic.topic === selectedTopic) || recommendedTopics[0];

    const handleContinue = () => {
        const launchConfig = {
            topic: selectedTopicData?.topic || FALLBACK_TOPICS[0].topic,
            mode: isProMode ? 'pro' : 'normal',
            source: 'thinking-setup',
            userId: user?.id || null,
            startedAt: new Date().toISOString(),
        };

        sessionStorage.setItem('mathmend_thinking_launch', JSON.stringify(launchConfig));
        navigate('/thinking-session', { state: launchConfig });
    };

    return (
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(251,191,36,0.18),transparent_18%),radial-gradient(circle_at_80%_20%,rgba(56,189,248,0.16),transparent_20%),linear-gradient(180deg,#f8fafc_0%,#eef4ff_45%,#f7efe5_100%)]">
            <Navbar />
            <PageTransition>
                <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
                    <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
                        <section className="relative overflow-hidden rounded-[34px] border border-white/70 bg-white/70 p-6 shadow-[0_30px_90px_rgba(15,23,42,0.08)] backdrop-blur xl:p-8">
                            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.14),transparent_28%),radial-gradient(circle_at_90%_10%,rgba(14,165,233,0.12),transparent_24%)]" />
                            <div className="relative">
                                <div className="flex flex-wrap items-center gap-3">
                                    <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-700">
                                        <Sparkles size={13} />
                                        Thinking Launch Pad
                                    </span>
                                    <span className="rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-medium text-slate-500">
                                        Top weak spots from your Firebase analytics
                                    </span>
                                </div>

                                <h1 className="mt-5 max-w-3xl text-4xl font-black tracking-tight text-slate-950 sm:text-5xl">
                                    Start with the chapter that needs the most attention, then drop straight into a cinematic launch.
                                </h1>
                                <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
                                    We surface your three strongest weak-topic signals, let you lock one in, and then send you into the thinking runtime with a full-screen countdown before the mic starts listening.
                                </p>

                                <div className="mt-8 grid gap-4 lg:grid-cols-3">
                                    {recommendedTopics.map((topic, index) => {
                                        const isActive = selectedTopic === topic.topic;
                                        return (
                                            <motion.button
                                                key={topic.topic}
                                                type="button"
                                                onClick={() => setSelectedTopic(topic.topic)}
                                                whileHover={{ y: -4 }}
                                                whileTap={{ scale: 0.985 }}
                                                initial={{ opacity: 0, y: 16 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                transition={{ duration: 0.35, delay: index * 0.08 }}
                                                className={`relative overflow-hidden rounded-[28px] border p-5 text-left transition-all ${
                                                    isActive
                                                        ? 'border-slate-950 bg-slate-950 text-white shadow-[0_20px_40px_rgba(15,23,42,0.22)]'
                                                        : 'border-slate-200 bg-white/85 text-slate-900 hover:border-slate-300'
                                                }`}
                                            >
                                                <div className={`absolute inset-0 ${isActive ? 'bg-[radial-gradient(circle_at_top,rgba(251,191,36,0.22),transparent_32%)]' : 'bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.08),transparent_26%)]'}`} />
                                                <div className="relative">
                                                    <div className="flex items-center justify-between gap-3">
                                                        <span className={`inline-flex h-10 w-10 items-center justify-center rounded-2xl ${isActive ? 'bg-white/10 text-amber-200' : 'bg-slate-100 text-sky-600'}`}>
                                                            <Target size={18} />
                                                        </span>
                                                        <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${isActive ? 'bg-white/10 text-white/80' : 'bg-slate-100 text-slate-500'}`}>
                                                            Weak spot {index + 1}
                                                        </span>
                                                    </div>
                                                    <h2 className="mt-5 text-xl font-bold">{topic.topic}</h2>
                                                    <p className={`mt-2 text-sm leading-6 ${isActive ? 'text-slate-200' : 'text-slate-500'}`}>
                                                        {topic.count > 0
                                                            ? `${topic.count} tracked questions and ${topic.share || 0}% of your recent topic signal`
                                                            : 'Starter recommendation while your personal analytics warms up'}
                                                    </p>
                                                    <div className="mt-6 flex items-center justify-between">
                                                        <div>
                                                            <p className={`text-[11px] uppercase tracking-[0.18em] ${isActive ? 'text-slate-300' : 'text-slate-400'}`}>Intensity</p>
                                                            <p className="mt-1 text-base font-semibold">{topic.score || 'Fresh'}</p>
                                                        </div>
                                                        <div className={`h-12 w-12 rounded-full border ${isActive ? 'border-white/15 bg-white/10' : 'border-slate-200 bg-slate-50'} flex items-center justify-center`}>
                                                            {isActive ? <ArrowRight size={18} /> : <BrainCircuit size={18} />}
                                                        </div>
                                                    </div>
                                                </div>
                                            </motion.button>
                                        );
                                    })}
                                </div>
                            </div>
                        </section>

                        <aside className="space-y-6">
                            <section className="overflow-hidden rounded-[34px] border border-slate-900/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.98),rgba(30,41,59,0.96))] p-6 text-white shadow-[0_28px_80px_rgba(15,23,42,0.2)]">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-400">Launch Configuration</p>
                                <div className="mt-5 rounded-[28px] border border-white/10 bg-white/5 p-5">
                                    <div className="flex items-start justify-between gap-4">
                                        <div>
                                            <p className="text-sm text-slate-400">Selected topic</p>
                                            <h2 className="mt-2 text-2xl font-bold text-white">{selectedTopicData?.topic || 'Algebra'}</h2>
                                        </div>
                                        <div className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${isProMode ? 'bg-amber-300 text-slate-950' : 'bg-white/10 text-slate-200'}`}>
                                            {isProMode ? 'Pro mode' : 'Normal mode'}
                                        </div>
                                    </div>

                                    <div className="mt-6 rounded-[24px] border border-white/10 bg-black/20 p-4">
                                        <div className="flex items-center justify-between gap-4">
                                            <div>
                                                <p className="text-sm font-semibold text-white">Pro mode</p>
                                                <p className="mt-1 text-sm leading-6 text-slate-300">
                                                    Turn this on for a hotter launch treatment and an immediate start-thinking CTA. Both modes still get the full-screen `3 2 1` countdown.
                                                </p>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => setIsProMode((current) => !current)}
                                                className={`relative h-12 w-24 rounded-full border transition-all ${isProMode ? 'border-amber-300/60 bg-amber-300/20' : 'border-white/10 bg-white/10'}`}
                                                aria-pressed={isProMode}
                                            >
                                                <span className={`absolute inset-y-1 transition-all ${isProMode ? 'left-[50px]' : 'left-1'} flex h-10 w-10 items-center justify-center rounded-full ${isProMode ? 'bg-amber-300 text-slate-950' : 'bg-white text-slate-900'}`}>
                                                    {isProMode ? <Flame size={16} /> : <Zap size={16} />}
                                                </span>
                                            </button>
                                        </div>
                                    </div>

                                    <div className="mt-6 grid gap-3 sm:grid-cols-2">
                                        <div className="rounded-[24px] border border-white/10 bg-white/5 p-4">
                                            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Countdown</p>
                                            <p className="mt-2 text-lg font-semibold text-white">Full-screen 3 2 1</p>
                                            <p className="mt-2 text-sm leading-6 text-slate-300">The transition appears in both modes before the session opens.</p>
                                        </div>
                                        <div className="rounded-[24px] border border-white/10 bg-white/5 p-4">
                                            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Auto start</p>
                                            <p className="mt-2 text-lg font-semibold text-white">1 second delayed mic boot</p>
                                            <p className="mt-2 text-sm leading-6 text-slate-300">As soon as the session page lands, thinking begins automatically after the countdown clears.</p>
                                        </div>
                                    </div>

                                    <button
                                        type="button"
                                        onClick={handleContinue}
                                        disabled={!selectedTopic || isLoading}
                                        className={`mt-6 inline-flex w-full items-center justify-center gap-3 rounded-full px-6 py-4 text-sm font-semibold uppercase tracking-[0.24em] transition ${
                                            isProMode
                                                ? 'bg-amber-300 text-slate-950 hover:bg-amber-200'
                                                : 'bg-sky-400 text-slate-950 hover:bg-sky-300'
                                        } disabled:cursor-not-allowed disabled:opacity-50`}
                                    >
                                        {isProMode ? <Flame size={18} /> : <ArrowRight size={18} />}
                                        {isProMode ? 'Start Thinking' : 'Enter Session'}
                                    </button>
                                </div>
                            </section>

                            <section className="rounded-[30px] border border-white/70 bg-white/75 p-6 shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">What Changes</p>
                                <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
                                    <p>Topic selection is driven by your existing Firebase analytics summary, so the setup page stays personalized without adding another profile layer.</p>
                                    <p>Normal mode gives a clean launch. Pro mode sharpens the visual treatment and makes the thinking CTA the dominant action.</p>
                                    <p>If your analytics is still empty, we seed the flow with solid starter topics so the setup never blocks.</p>
                                </div>
                            </section>
                        </aside>
                    </div>
                </div>
            </PageTransition>
        </div>
    );
}
