import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Mic, Send, Clock, Play, CheckCircle2, ChevronRight, AlertCircle } from 'lucide-react';
import Navbar from '../components/Navbar';
import PageTransition from '../components/PageTransition';

const stages = [
    { id: 'understand', name: 'Understand Problem' },
    { id: 'plan', name: 'Plan Approach' },
    { id: 'solve', name: 'Step-by-Step Solving' },
    { id: 'explore', name: 'Explore Alternatives' },
    { id: 'reflect', name: 'Reflect' }
];

export default function ThinkingSessionPage() {
    const navigate = useNavigate();
    const [currentStageIdx, setCurrentStageIdx] = useState(0);
    const [chatHistory, setChatHistory] = useState([
        { role: 'ai', content: "Let's read the problem carefully. What is the main thing we are trying to find here?" }
    ]);
    const [inputValue, setInputValue] = useState('');
    const [timeElapsed, setTimeElapsed] = useState(0);
    const messagesEndRef = useRef(null);

    const problem = "A train 120 meters long is running with a speed of 60 km/hr. In what time will it pass a man who is running at 6 km/hr in the direction opposite to that in which the train is going?";
    const topic = localStorage.getItem('thinking_session_topic') || 'Math Problem';

    useEffect(() => {
        const timer = setInterval(() => {
            setTimeElapsed(prev => prev + 1);
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [chatHistory]);

    const formatTime = (seconds) => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s.toString().padStart(2, '0')}`;
    };

    const handleSend = () => {
        if (!inputValue.trim()) return;

        const newHistory = [...chatHistory, { role: 'user', content: inputValue }];
        setChatHistory(newHistory);
        setInputValue('');

        // Mock AI Behavior
        setTimeout(() => {
            let aiResponse = "";
            let advanceStage = false;

            if (currentStageIdx === 0) {
                if (inputValue.toLowerCase().includes('time') || inputValue.toLowerCase().includes('pass')) {
                    aiResponse = "Great! We need to find the time. Now, let's move to planning. How should we approach relative speed when objects move in opposite directions?";
                    advanceStage = true;
                } else {
                    aiResponse = "Close, but let's re-read the last sentence. Are we looking for speed, distance, or time?";
                }
            } else if (currentStageIdx === 1) {
                if (inputValue.toLowerCase().includes('add') || inputValue.toLowerCase().includes('sum')) {
                    aiResponse = "Exactly! We add the speeds. Let's calculate the relative speed and then solve for time.";
                    advanceStage = true;
                } else {
                    aiResponse = "Think about two cars driving towards each other. Do they pass each other faster or slower? Should we add or subtract their speeds?";
                }
            } else if (currentStageIdx === 2) {
                if (inputValue.toLowerCase().includes('66')) {
                    aiResponse = "Wait, don't forget units! Before calculating time, the speed is in km/hr but distance is in meters. What should we do next?";
                } else if (inputValue.toLowerCase().includes('convert') || inputValue.toLowerCase().includes('5/18')) {
                    aiResponse = "Brilliant! You caught the unit difference. Go ahead and calculate the final time in seconds.";
                } else if (inputValue.includes('6.54')) {
                    aiResponse = "Perfect calculation! Now, are there any other ways to think about this problem, or is this the most efficient path?";
                    advanceStage = true;
                } else {
                    aiResponse = "Let's work through the math. Relative speed = 60 + 6 km/hr. How do we convert that to m/s?";
                }
            } else if (currentStageIdx === 3) {
                aiResponse = "Good thoughts. Finally, let's reflect. What was the trickiest part of this problem for you?";
                advanceStage = true;
            } else if (currentStageIdx === 4) {
                // Record session stats
                localStorage.setItem('thinking_session_time', timeElapsed);
                navigate('/thinking-report');
                return;
            }

            setChatHistory([...newHistory, { role: 'ai', content: aiResponse }]);
            if (advanceStage) {
                setCurrentStageIdx(prev => Math.min(prev + 1, 4));
            }
        }, 1200);
    };

    const guidedInputs = ["I think...", "Can we try the formula...", "I'm confused about...", "Let's draw it out."];

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col">
            <Navbar />
            
            <div className="flex-1 flex gap-4 max-w-7xl mx-auto w-full p-4 h-[calc(100vh-80px)]">
                {/* Insights Panel (Left) */}
                <div className="w-64 bg-white rounded-2xl shadow-sm border border-gray-200 p-5 flex flex-col hidden md:flex">
                    <h3 className="font-bold text-gray-800 mb-6 flex items-center gap-2">
                        <Brain className="text-blue-600" /> Session Progress
                    </h3>
                    
                    <div className="flex-1 space-y-6 relative">
                        {/* Progress Line */}
                        <div className="absolute left-[11px] top-2 bottom-6 w-0.5 bg-gray-100 z-0"></div>

                        {stages.map((stage, idx) => (
                            <div key={stage.id} className="relative z-10 flex items-start gap-4">
                                <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${idx < currentStageIdx ? 'bg-green-100 text-green-600' : idx === currentStageIdx ? 'bg-blue-600 text-white ring-4 ring-blue-50' : 'bg-gray-100 text-gray-400'}`}>
                                    {idx < currentStageIdx ? <CheckCircle2 size={14} /> : (idx + 1)}
                                </div>
                                <div className={idx === currentStageIdx ? 'text-blue-700 font-semibold text-sm' : idx < currentStageIdx ? 'text-gray-900 font-medium text-sm' : 'text-gray-400 text-sm'}>
                                    {stage.name}
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="mt-auto pt-4 border-t border-gray-100">
                        <div className="flex items-center justify-between text-gray-600">
                            <span className="flex items-center gap-2 text-sm"><Clock size={16} /> Elapsed</span>
                            <span className="font-mono font-bold">{formatTime(timeElapsed)}</span>
                        </div>
                    </div>
                </div>

                <div className="flex-1 flex flex-col gap-4">
                    {/* Question Panel */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 flex-shrink-0">
                        <div className="flex items-center justify-between mb-4">
                            <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-xs font-bold uppercase tracking-wider">{topic}</span>
                            <span className="text-gray-500 text-sm flex items-center gap-1"><AlertCircle size={14}/> Read carefully</span>
                        </div>
                        <p className="text-xl text-gray-900 leading-relaxed font-medium">
                            {problem}
                        </p>
                    </div>

                    {/* Chat/Thinking Panel */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-200 flex-1 flex flex-col overflow-hidden relative">
                        <div className="absolute top-0 w-full bg-gradient-to-b from-white to-transparent h-6 z-10" />
                        
                        <div className="flex-1 overflow-y-auto p-6 space-y-6">
                            {chatHistory.map((msg, idx) => (
                                <motion.div 
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    key={idx} 
                                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                                >
                                    <div className={`max-w-[80%] rounded-2xl px-5 py-3.5 ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-none shadow-md' : 'bg-gray-100 text-gray-800 rounded-bl-none border border-gray-200'}`}>
                                        <p className="leading-relaxed">{msg.content}</p>
                                    </div>
                                </motion.div>
                            ))}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Input Area */}
                        <div className="p-4 bg-gray-50 border-t border-gray-200">
                            <div className="flex gap-2 mb-3 overflow-x-auto pb-1" style={{scrollbarWidth: 'none', msOverflowStyle: 'none'}}>
                                {guidedInputs.map(gi => (
                                    <button 
                                        key={gi} 
                                        onClick={() => setInputValue(gi)}
                                        className="whitespace-nowrap px-4 py-1.5 bg-white border border-gray-200 rounded-full text-sm font-medium text-gray-600 hover:text-blue-600 hover:border-blue-300 transition-colors shadow-sm"
                                    >
                                        {gi}
                                    </button>
                                ))}
                            </div>
                            <div className="flex items-end gap-3">
                                <button className="p-3 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-colors bg-white border border-gray-200 shadow-sm flex-shrink-0">
                                    <Mic size={20} />
                                </button>
                                <div className="flex-1 relative">
                                    <textarea
                                        value={inputValue}
                                        onChange={(e) => setInputValue(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                e.preventDefault();
                                                handleSend();
                                            }
                                        }}
                                        placeholder="Type your thinking process here..."
                                        className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none shadow-sm"
                                        rows={2}
                                    />
                                </div>
                                <button 
                                    onClick={handleSend}
                                    disabled={!inputValue.trim()}
                                    className="p-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
                                >
                                    <Send size={20} className="ml-0.5" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
