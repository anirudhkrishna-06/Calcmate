import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
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
import { API_BASE } from '../config/api';
import {
    createClientId,
    deleteUserChat,
    getRecentChats,
    saveUserChat,
    sortUserChats,
    syncUserAnalyticsFromChats,
    syncUserStreakFromChats,
} from '../services/userData';
import { classifyMathTopic } from '../services/topicIntelligence';

const readErrorMessage = async (response, fallbackMessage) => {
    const contentType = response.headers.get('content-type') || '';

    try {
        if (contentType.includes('application/json')) {
            const payload = await response.json();
            return payload.detail || payload.error || payload.message || fallbackMessage;
        }

        const text = await response.text();
        return text || fallbackMessage;
    } catch {
        return fallbackMessage;
    }
};

export default function ChatbotPage() {
    const { user } = useAuth();
    const [searchParams, setSearchParams] = useSearchParams();

    const [sessions, setSessions] = useState([]);
    const [activeSessionId, setActiveSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [inputText, setInputText] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isHistoryLoading, setIsHistoryLoading] = useState(true);
    const [selectedImage, setSelectedImage] = useState(null);
    const [imagePreview, setImagePreview] = useState(null);
    const [sidebarOpen, setSidebarOpen] = useState(true);

    const messagesEndRef = useRef(null);
    const fileInputRef = useRef(null);
    const inputRef = useRef(null);
    const liveTopicInsight = useMemo(() => classifyMathTopic(inputText), [inputText]);

    useEffect(() => {
        let isMounted = true;

        const loadChats = async () => {
            if (!user?.id) {
                if (isMounted) {
                    setSessions([]);
                    setMessages([]);
                    setActiveSessionId(null);
                    setIsHistoryLoading(false);
                }
                return;
            }

            setIsHistoryLoading(true);

            try {
                const chats = await getRecentChats(user.id, 100);
                if (!isMounted) return;

                setSessions(chats);

                const requestedSessionId = searchParams.get('session');
                const selectedChat = requestedSessionId
                    ? chats.find((session) => session.id === requestedSessionId)
                    : chats.find((session) => session.id === activeSessionId);

                if (selectedChat) {
                    setActiveSessionId(selectedChat.id);
                    setMessages(selectedChat.messages || []);
                } else if (requestedSessionId) {
                    setSearchParams({});
                    setActiveSessionId(null);
                    setMessages([]);
                }
            } catch (error) {
                console.error('Error loading chat history:', error);
            } finally {
                if (isMounted) {
                    setIsHistoryLoading(false);
                }
            }
        };

        loadChats();

        return () => {
            isMounted = false;
        };
    }, [user?.id]);

    useEffect(() => {
        const sessionId = searchParams.get('session');
        if (!sessionId) {
            return;
        }

        const found = sessions.find((session) => session.id === sessionId);
        if (found) {
            setActiveSessionId(found.id);
            setMessages(found.messages || []);
        }
    }, [searchParams, sessions]);

    // Scroll to bottom
    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, scrollToBottom]);

    const updateSessionsState = useCallback((session) => {
        setSessions((currentSessions) =>
            sortUserChats([
                session,
                ...currentSessions.filter((existingSession) => existingSession.id !== session.id),
            ])
        );
    }, []);

    const createEmptySession = useCallback(() => ({
        id: createClientId(),
        title: 'New conversation',
        messages: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
    }), []);

    const persistSession = useCallback(async (session, allSessionsOverride) => {
        if (!user?.id) return session;

        const savedSession = await saveUserChat(user.id, session);
        const nextSessions = sortUserChats(
            allSessionsOverride
                ? allSessionsOverride.map((item) => (item.id === savedSession.id ? savedSession : item))
                : [
                    savedSession,
                    ...sessions.filter((existingSession) => existingSession.id !== savedSession.id),
                ]
        );

        setSessions(nextSessions);
        await Promise.all([
            syncUserStreakFromChats(user.id, nextSessions),
            syncUserAnalyticsFromChats(user.id, nextSessions),
        ]);
        return savedSession;
    }, [sessions, user?.id]);

    // Create new chat
    const createNewChat = async () => {
        const newSession = createEmptySession();
        updateSessionsState(newSession);
        await persistSession(newSession);
        setSearchParams({ session: newSession.id });
        setActiveSessionId(newSession.id);
        setMessages([]);
        setInputText('');
        clearImage();
        inputRef.current?.focus();
    };

    // Load a session
    const loadSession = (session) => {
        setSearchParams({ session: session.id });
        setActiveSessionId(session.id);
        setMessages(session.messages || []);
        setInputText('');
        clearImage();
    };

    // Delete a session
    const deleteSession = async (e, sessionId) => {
        e.stopPropagation();

        const updatedSessions = sessions.filter((session) => session.id !== sessionId);
        setSessions(updatedSessions);

        if (activeSessionId === sessionId) {
            setSearchParams({});
            setActiveSessionId(null);
            setMessages([]);
        }

        try {
            if (user?.id) {
                await deleteUserChat(user.id, sessionId);
                await Promise.all([
                    syncUserStreakFromChats(user.id, updatedSessions),
                    syncUserAnalyticsFromChats(user.id, updatedSessions),
                ]);
            }
        } catch (error) {
            console.error('Error deleting session:', error);
        }
    };

    const clearImage = () => {
        setSelectedImage(null);
        setImagePreview(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
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
            const response = await fetch(`${API_BASE}/ocr`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) {
                const message = await readErrorMessage(response, `OCR request failed with status ${response.status}.`);
                throw new Error(message);
            }
            const data = await response.json();
            setInputText(data.extracted_text || data.extractedText || data.text || '');
        } catch (error) {
            console.error('OCR Error:', error);
        } finally {
            setIsLoading(false);
        }
    };

    // Send message
    const handleSendMessage = async () => {
        if (!inputText.trim() || isLoading) return;

        const questionText = inputText.trim();
        const messageTimestamp = new Date().toISOString();
        const topicInsight = classifyMathTopic(questionText);
        const userMsg = {
            id: createClientId(),
            type: 'user',
            role: 'user',
            content: questionText,
            text: questionText,
            timestamp: messageTimestamp,
            topicTag: topicInsight.topicTag,
            topicConfidence: topicInsight.confidence,
        };

        const baseSession =
            sessions.find((session) => session.id === activeSessionId) ||
            {
                ...createEmptySession(),
                title: questionText.slice(0, 60),
            };

        const sessionId = baseSession.id;
        const newMessages = [...(baseSession.messages || messages), userMsg];
        const optimisticSession = {
            ...baseSession,
            title:
                (baseSession.messages || []).length === 0
                    ? questionText.slice(0, 60)
                    : baseSession.title || questionText.slice(0, 60),
            messages: newMessages,
            updatedAt: messageTimestamp,
        };

        setActiveSessionId(sessionId);
        setSearchParams({ session: sessionId });
        setMessages(newMessages);
        setInputText('');
        clearImage();
        setIsLoading(true);
        updateSessionsState(optimisticSession);

        try {
            await persistSession(optimisticSession);

            const response = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: userMsg.content }),
            });
            if (!response.ok) {
                const message = await readErrorMessage(response, `Chat request failed with status ${response.status}.`);
                throw new Error(message);
            }
            const data = await response.json();

            const botMsg = {
                id: createClientId(),
                type: 'bot',
                role: 'bot',
                content: data.answer || data.response || 'Sorry, I could not process your request.',
                text: data.answer || data.response || 'Sorry, I could not process your request.',
                timestamp: new Date().toISOString(),
            };

            const finalMessages = [...newMessages, botMsg];
            const finalSession = {
                ...optimisticSession,
                messages: finalMessages,
                updatedAt: botMsg.timestamp,
            };

            setMessages(finalMessages);
            updateSessionsState(finalSession);
            await persistSession(finalSession);
        } catch (error) {
            console.error('Chat Error:', error);
            const errMsg = {
                id: createClientId(),
                type: 'bot',
                role: 'bot',
                content: `Backend error: ${error.message || `Unable to reach ${API_BASE}`}`,
                text: `Backend error: ${error.message || `Unable to reach ${API_BASE}`}`,
                timestamp: new Date().toISOString(),
            };
            const finalMessages = [...newMessages, errMsg];
            const finalSession = {
                ...optimisticSession,
                messages: finalMessages,
                updatedAt: errMsg.timestamp,
            };

            setMessages(finalMessages);
            updateSessionsState(finalSession);
            await persistSession(finalSession);
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
        <div className="h-screen overflow-hidden bg-white flex flex-col">
            <Navbar />
            <div className="flex-1 min-h-0 flex overflow-hidden">
                {/* Sidebar — Chat History */}
                <AnimatePresence>
                    {sidebarOpen && (
                        <motion.aside
                            className="h-full w-72 bg-gray-50 border-r border-gray-100 flex flex-col flex-shrink-0"
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
                            <div className="flex-1 min-h-0 overflow-y-auto py-2">
                                {isHistoryLoading ? (
                                    <div className="px-4 py-8 text-center">
                                        <Loader2 size={20} className="text-gray-300 mx-auto mb-2 animate-spin" />
                                        <p className="text-xs text-gray-400">Loading conversations</p>
                                    </div>
                                ) : sessions.length === 0 ? (
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
                <div className="relative flex-1 min-h-0 min-w-0 flex flex-col">
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
                    <div className="flex-1 min-h-0 overflow-y-auto px-4 py-6">
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
                                            {msg.type === 'user' && msg.topicTag && (
                                                <div className="mt-2 inline-flex items-center rounded-full bg-blue-500/20 px-2.5 py-1 text-[10px] font-medium text-blue-100">
                                                    {msg.topicTag}
                                                </div>
                                            )}
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

                            {inputText.trim() && (
                                <div className="mt-3 flex items-center justify-center">
                                    <div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-[11px] text-blue-700">
                                        <span className="font-semibold">Detected topic</span>
                                        <span>{liveTopicInsight.topicTag}</span>
                                        <span className="text-blue-400">
                                            {Math.round((liveTopicInsight.confidence || 0) * 100)}%
                                        </span>
                                    </div>
                                </div>
                            )}
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
