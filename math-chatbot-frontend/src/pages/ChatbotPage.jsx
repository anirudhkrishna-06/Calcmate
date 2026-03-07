import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Send,
    Image as ImageIcon,
    X,
    Loader2,
    Plus,
    MessageSquare,
    Clock,
    Trash2,
    ChevronLeft,
    Bot,
    User as UserIcon,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/Navbar';

// Generate a unique ID
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2);

// Chat session storage helpers
const STORAGE_KEY = 'mathmend_chat_sessions';

const loadSessions = () => {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    } catch {
        return [];
    }
};

const saveSessions = (sessions) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
};

export default function ChatbotPage() {
    const { user } = useAuth();
    const [searchParams, setSearchParams] = useSearchParams();

    const [sessions, setSessions] = useState(loadSessions);
    const [activeSessionId, setActiveSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [inputText, setInputText] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [selectedImage, setSelectedImage] = useState(null);
    const [imagePreview, setImagePreview] = useState(null);
    const [sidebarOpen, setSidebarOpen] = useState(true);

    const messagesEndRef = useRef(null);
    const fileInputRef = useRef(null);
    const inputRef = useRef(null);

    // Load session from URL query
    useEffect(() => {
        const sessionId = searchParams.get('session');
        if (sessionId) {
            const found = sessions.find((s) => s.id === sessionId);
            if (found) {
                setActiveSessionId(found.id);
                setMessages(found.messages || []);
            }
        }
    }, []);

    // Scroll to bottom
    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, scrollToBottom]);

    // Persist sessions
    const persistSessions = useCallback(
        (updatedSessions) => {
            setSessions(updatedSessions);
            saveSessions(updatedSessions);
        },
        []
    );

    // Create new chat
    const createNewChat = () => {
        const newSession = {
            id: uid(),
            title: 'New conversation',
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
        };
        const updated = [newSession, ...sessions];
        persistSessions(updated);
        setActiveSessionId(newSession.id);
        setMessages([]);
        setInputText('');
        clearImage();
        inputRef.current?.focus();
    };

    // Load a session
    const loadSession = (session) => {
        setActiveSessionId(session.id);
        setMessages(session.messages || []);
        setInputText('');
        clearImage();
    };

    // Delete a session
    const deleteSession = (e, sessionId) => {
        e.stopPropagation();
        const updated = sessions.filter((s) => s.id !== sessionId);
        persistSessions(updated);
        if (activeSessionId === sessionId) {
            setActiveSessionId(null);
            setMessages([]);
        }
    };

    // Handle image upload
    const handleImageUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onloadend = () => setImagePreview(reader.result);
        reader.readAsDataURL(file);
        setSelectedImage(file);

        try {
            setIsLoading(true);
            const formData = new FormData();
            formData.append('image', file);
            const response = await fetch('http://localhost:8000/ocr', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            setInputText(data.extracted_text || data.extractedText || data.text || '');
        } catch (error) {
            console.error('OCR Error:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const clearImage = () => {
        setSelectedImage(null);
        setImagePreview(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    // Send message
    const handleSendMessage = async () => {
        if (!inputText.trim() || isLoading) return;

        // Auto-create session if none
        let currentId = activeSessionId;
        let currentSessions = [...sessions];
        if (!currentId) {
            const newSession = {
                id: uid(),
                title: inputText.trim().slice(0, 60),
                messages: [],
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
            };
            currentSessions = [newSession, ...currentSessions];
            currentId = newSession.id;
            setActiveSessionId(currentId);
        }

        const userMsg = {
            id: uid(),
            type: 'user',
            content: inputText.trim(),
            timestamp: new Date().toISOString(),
        };

        const newMessages = [...messages, userMsg];
        setMessages(newMessages);
        setInputText('');
        clearImage();
        setIsLoading(true);

        // Update session title if first message
        const sessionIdx = currentSessions.findIndex((s) => s.id === currentId);
        if (sessionIdx !== -1 && currentSessions[sessionIdx].messages.length === 0) {
            currentSessions[sessionIdx].title = userMsg.content.slice(0, 60);
        }

        try {
            const response = await fetch('http://localhost:8000/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: userMsg.content }),
            });
            const data = await response.json();

            const botMsg = {
                id: uid(),
                type: 'bot',
                content: data.answer || data.response || 'Sorry, I could not process your request.',
                timestamp: new Date().toISOString(),
            };

            const finalMessages = [...newMessages, botMsg];
            setMessages(finalMessages);

            // Persist
            if (sessionIdx !== -1) {
                currentSessions[sessionIdx].messages = finalMessages;
                currentSessions[sessionIdx].updatedAt = new Date().toISOString();
            }
            persistSessions(currentSessions);
        } catch (error) {
            console.error('Chat Error:', error);
            const errMsg = {
                id: uid(),
                type: 'bot',
                content: 'Sorry, there was an error connecting to the server. Please ensure the backend is running.',
                timestamp: new Date().toISOString(),
            };
            const finalMessages = [...newMessages, errMsg];
            setMessages(finalMessages);

            if (sessionIdx !== -1) {
                currentSessions[sessionIdx].messages = finalMessages;
                currentSessions[sessionIdx].updatedAt = new Date().toISOString();
            }
            persistSessions(currentSessions);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    const formatTime = (ts) => {
        try {
            return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch {
            return '';
        }
    };

    const formatDate = (ts) => {
        try {
            const d = new Date(ts);
            const now = new Date();
            const diff = now - d;
            if (diff < 86400000) return 'Today';
            if (diff < 172800000) return 'Yesterday';
            return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
        } catch {
            return '';
        }
    };

    return (
        <div className="min-h-screen bg-white flex flex-col">
            <Navbar />
            <div className="flex-1 flex overflow-hidden">
                {/* Sidebar — Chat History */}
                <AnimatePresence>
                    {sidebarOpen && (
                        <motion.aside
                            className="w-72 bg-gray-50 border-r border-gray-100 flex flex-col flex-shrink-0"
                            initial={{ x: -288, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            exit={{ x: -288, opacity: 0 }}
                            transition={{ type: 'tween', duration: 0.25 }}
                        >
                            {/* Sidebar header */}
                            <div className="p-4 flex items-center justify-between border-b border-gray-100">
                                <h2 className="text-sm font-semibold text-gray-700">History</h2>
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={createNewChat}
                                        className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                                        title="New chat"
                                    >
                                        <Plus size={16} className="text-gray-600" />
                                    </button>
                                    <button
                                        onClick={() => setSidebarOpen(false)}
                                        className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors md:hidden"
                                    >
                                        <X size={16} className="text-gray-600" />
                                    </button>
                                </div>
                            </div>

                            {/* Session list */}
                            <div className="flex-1 overflow-y-auto py-2">
                                {sessions.length === 0 ? (
                                    <div className="px-4 py-8 text-center">
                                        <MessageSquare size={24} className="text-gray-300 mx-auto mb-2" />
                                        <p className="text-xs text-gray-400">No conversations yet</p>
                                    </div>
                                ) : (
                                    sessions.map((session) => (
                                        <button
                                            key={session.id}
                                            onClick={() => loadSession(session)}
                                            className={`w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-100 transition-colors group ${activeSessionId === session.id ? 'bg-blue-50' : ''
                                                }`}
                                        >
                                            <MessageSquare
                                                size={14}
                                                className={
                                                    activeSessionId === session.id
                                                        ? 'text-blue-600 flex-shrink-0'
                                                        : 'text-gray-400 flex-shrink-0'
                                                }
                                            />
                                            <div className="flex-1 min-w-0">
                                                <p
                                                    className={`text-sm truncate ${activeSessionId === session.id
                                                            ? 'text-blue-700 font-medium'
                                                            : 'text-gray-700'
                                                        }`}
                                                >
                                                    {session.title}
                                                </p>
                                                <p className="text-[10px] text-gray-400 mt-0.5 flex items-center gap-1">
                                                    <Clock size={8} />
                                                    {formatDate(session.updatedAt)}
                                                </p>
                                            </div>
                                            <button
                                                onClick={(e) => deleteSession(e, session.id)}
                                                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded transition-all"
                                                title="Delete"
                                            >
                                                <Trash2 size={12} className="text-gray-400 hover:text-red-500" />
                                            </button>
                                        </button>
                                    ))
                                )}
                            </div>
                        </motion.aside>
                    )}
                </AnimatePresence>

                {/* Main Chat Area */}
                <div className="flex-1 flex flex-col min-w-0">
                    {/* Toggle sidebar button */}
                    {!sidebarOpen && (
                        <button
                            onClick={() => setSidebarOpen(true)}
                            className="absolute left-2 top-20 z-10 p-2 bg-white border border-gray-200 rounded-lg shadow-sm hover:bg-gray-50 transition-colors"
                        >
                            <ChevronLeft size={16} className="text-gray-600 rotate-180" />
                        </button>
                    )}

                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto px-4 py-6">
                        <div className="max-w-3xl mx-auto space-y-1">
                            {messages.length === 0 && (
                                <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
                                    <motion.div
                                        className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mb-6"
                                        initial={{ scale: 0.5, opacity: 0 }}
                                        animate={{ scale: 1, opacity: 1 }}
                                        transition={{ type: 'spring', duration: 0.6 }}
                                    >
                                        <Bot size={28} className="text-blue-600" />
                                    </motion.div>
                                    <h2 className="text-xl font-semibold text-gray-800 mb-2">
                                        Ask me anything
                                    </h2>
                                    <p className="text-gray-400 text-sm text-center max-w-sm">
                                        Type a math problem or upload an image. I'll solve it step by step.
                                    </p>
                                    {/* Quick prompts */}
                                    <div className="flex flex-wrap gap-2 mt-8 justify-center">
                                        {[
                                            'Solve x² + 5x + 6 = 0',
                                            'What is the derivative of sin(x)?',
                                            'Simplify 3/4 + 2/3',
                                        ].map((prompt) => (
                                            <button
                                                key={prompt}
                                                onClick={() => {
                                                    setInputText(prompt);
                                                    inputRef.current?.focus();
                                                }}
                                                className="text-xs px-4 py-2 bg-gray-50 border border-gray-200 rounded-full text-gray-600 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-all"
                                            >
                                                {prompt}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <AnimatePresence>
                                {messages.map((msg, idx) => (
                                    <motion.div
                                        key={msg.id}
                                        className={`flex gap-3 py-3 ${msg.type === 'user' ? 'justify-end' : 'justify-start'
                                            }`}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.3, delay: idx === messages.length - 1 ? 0.1 : 0 }}
                                    >
                                        {msg.type === 'bot' && (
                                            <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                                                <Bot size={16} className="text-blue-600" />
                                            </div>
                                        )}
                                        <div
                                            className={`max-w-[75%] rounded-2xl px-4 py-3 ${msg.type === 'user'
                                                    ? 'bg-blue-600 text-white rounded-br-md'
                                                    : 'bg-gray-50 text-gray-800 border border-gray-100 rounded-bl-md'
                                                }`}
                                        >
                                            <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                                                {msg.content}
                                            </div>
                                            <div
                                                className={`text-[10px] mt-2 ${msg.type === 'user' ? 'text-blue-200' : 'text-gray-400'
                                                    }`}
                                            >
                                                {formatTime(msg.timestamp)}
                                            </div>
                                        </div>
                                        {msg.type === 'user' && (
                                            <div className="w-8 h-8 bg-gray-900 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                                                <UserIcon size={14} className="text-white" />
                                            </div>
                                        )}
                                    </motion.div>
                                ))}
                            </AnimatePresence>

                            {/* Typing indicator */}
                            {isLoading && (
                                <motion.div
                                    className="flex gap-3 py-3"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                >
                                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                                        <Bot size={16} className="text-blue-600" />
                                    </div>
                                    <div className="bg-gray-50 border border-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
                                        <div className="flex items-center gap-1.5">
                                            <motion.span
                                                className="w-2 h-2 bg-blue-400 rounded-full"
                                                animate={{ opacity: [0.3, 1, 0.3] }}
                                                transition={{ duration: 1.2, repeat: Infinity, delay: 0 }}
                                            />
                                            <motion.span
                                                className="w-2 h-2 bg-blue-400 rounded-full"
                                                animate={{ opacity: [0.3, 1, 0.3] }}
                                                transition={{ duration: 1.2, repeat: Infinity, delay: 0.2 }}
                                            />
                                            <motion.span
                                                className="w-2 h-2 bg-blue-400 rounded-full"
                                                animate={{ opacity: [0.3, 1, 0.3] }}
                                                transition={{ duration: 1.2, repeat: Infinity, delay: 0.4 }}
                                            />
                                        </div>
                                    </div>
                                </motion.div>
                            )}

                            <div ref={messagesEndRef} />
                        </div>
                    </div>

                    {/* Input Area */}
                    <div className="border-t border-gray-100 bg-white px-4 py-4">
                        <div className="max-w-3xl mx-auto">
                            {/* Image preview */}
                            {imagePreview && (
                                <div className="mb-3 relative inline-block">
                                    <img
                                        src={imagePreview}
                                        alt="Preview"
                                        className="max-h-28 rounded-xl border border-gray-200"
                                    />
                                    <button
                                        onClick={clearImage}
                                        className="absolute -top-2 -right-2 bg-gray-900 text-white rounded-full p-1 hover:bg-red-500 transition-colors"
                                    >
                                        <X size={12} />
                                    </button>
                                </div>
                            )}

                            <div className="flex items-end gap-2">
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    onChange={handleImageUpload}
                                    accept="image/*"
                                    className="hidden"
                                />
                                <button
                                    onClick={() => fileInputRef.current?.click()}
                                    disabled={isLoading}
                                    className="flex-shrink-0 p-3 bg-gray-50 hover:bg-gray-100 rounded-xl transition-colors disabled:opacity-50"
                                    title="Upload image"
                                >
                                    <ImageIcon size={18} className="text-gray-500" />
                                </button>

                                <textarea
                                    ref={inputRef}
                                    value={inputText}
                                    onChange={(e) => setInputText(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    placeholder="Type your math question here..."
                                    disabled={isLoading}
                                    rows={1}
                                    className="flex-1 resize-none border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 text-sm"
                                    style={{ minHeight: '48px', maxHeight: '120px' }}
                                />

                                <motion.button
                                    onClick={handleSendMessage}
                                    disabled={!inputText.trim() || isLoading}
                                    className="flex-shrink-0 p-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-colors disabled:opacity-40"
                                    title="Send"
                                    whileTap={{ scale: 0.95 }}
                                >
                                    <Send size={18} />
                                </motion.button>
                            </div>

                            <p className="text-[10px] text-gray-400 mt-2 text-center">
                                Press Enter to send · Shift+Enter for new line
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
