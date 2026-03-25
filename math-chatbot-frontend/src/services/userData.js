import {
    collection,
    deleteDoc,
    doc,
    getDoc,
    getDocs,
    limit,
    orderBy,
    query,
    setDoc,
} from 'firebase/firestore';
import { db } from '../../firebase';
import { classifyMathTopic, TOPIC_CATALOG } from './topicIntelligence';

const DEFAULT_PREFERENCES = {
    emailNotifications: true,
    darkMode: false,
};

const DEFAULT_PROFILE = {
    displayName: 'User',
    preferences: DEFAULT_PREFERENCES,
};

const DEFAULT_STREAK = {
    activeDays: [],
    totalSolved: 0,
    totalActivities: 0,
    chatActivities: 0,
    quizActivities: 0,
    contestActivities: 0,
    currentStreak: 0,
    longestStreak: 0,
    lastActivityAt: null,
    updatedAt: null,
};

const DEFAULT_ANALYTICS = {
    weakTopics: [],
    mostAskedTopics: [],
    topicCounts: [],
    activityLevel: 'New',
    totalQuestions: 0,
    activeDays: 0,
    totalSessions: 0,
    quizzesAttended: 0,
    cumulativeQuizScore: 0,
    averageQuizScore: 0,
    bestQuizScore: 0,
    lastQuizScore: 0,
    recentQuizScores: [],
    updatedAt: null,
};

export const createClientId = () => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
    }

    return `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
};

const chatsCollectionRef = (userId) => collection(db, 'users', userId, 'chats');
const chatDocRef = (userId, chatId) => doc(db, 'users', userId, 'chats', chatId);
const profileDocRef = (userId) => doc(db, 'users', userId, 'profile', 'settings');
const streakDocRef = (userId) => doc(db, 'users', userId, 'streak', 'summary');
const analyticsDocRef = (userId) => doc(db, 'users', userId, 'analytics', 'summary');
const quizAttemptsCollectionRef = (userId) => collection(db, 'users', userId, 'quizAttempts');
const ratingDocRef = (userId) => doc(db, 'users', userId, 'rating', 'summary');

const normalizeIsoDate = (value) => {
    if (!value) return null;

    if (typeof value === 'string') {
        return value;
    }

    if (typeof value?.toDate === 'function') {
        return value.toDate().toISOString();
    }

    if (value instanceof Date) {
        return value.toISOString();
    }

    return null;
};

export const inferTopicTag = (text = '') => classifyMathTopic(text).topicTag;

export const serializeChatMessages = (messages = []) =>
    messages.map((message) => {
        const role = message.role || (message.type === 'user' ? 'user' : 'bot');
        const text = message.text || message.content || '';
        const timestamp = normalizeIsoDate(message.timestamp) || new Date().toISOString();

        return {
            role,
            text,
            timestamp,
            ...(role === 'user'
                ? {
                    topicTag: message.topicTag || inferTopicTag(text),
                    topicConfidence:
                        message.topicConfidence ??
                        classifyMathTopic(text).confidence,
                }
                : {}),
        };
    });

export const deserializeChatMessages = (messages = []) =>
    messages.map((message) => ({
        id: createClientId(),
        type: message.role === 'user' ? 'user' : 'bot',
        role: message.role === 'user' ? 'user' : 'bot',
        content: message.text || '',
        text: message.text || '',
        timestamp: normalizeIsoDate(message.timestamp) || new Date().toISOString(),
        ...(message.topicTag ? { topicTag: message.topicTag } : {}),
        ...(message.topicConfidence ? { topicConfidence: message.topicConfidence } : {}),
    }));

const normalizeChat = (chatId, data = {}) => {
    const createdAt = normalizeIsoDate(data.createdAt) || new Date().toISOString();
    const updatedAt = normalizeIsoDate(data.updatedAt) || createdAt;
    const messages = deserializeChatMessages(data.messages || []);

    return {
        id: chatId,
        title: data.title || 'New conversation',
        createdAt,
        updatedAt,
        messages,
    };
};

const sortChatsByUpdatedAt = (chats = []) =>
    [...chats].sort((left, right) => {
        const leftTime = new Date(left.updatedAt || left.createdAt || 0).getTime();
        const rightTime = new Date(right.updatedAt || right.createdAt || 0).getTime();
        return rightTime - leftTime;
    });

export async function listUserChats(userId, maxCount = 50) {
    if (!userId) return [];

    const chatQuery = query(chatsCollectionRef(userId), orderBy('updatedAt', 'desc'), limit(maxCount));
    const snapshot = await getDocs(chatQuery);

    return snapshot.docs.map((chatDoc) => normalizeChat(chatDoc.id, chatDoc.data()));
}

export async function getRecentChats(userId, maxCount = 5) {
    return listUserChats(userId, maxCount);
}

export async function saveUserChat(userId, chat) {
    if (!userId || !chat?.id) return null;

    const createdAt = normalizeIsoDate(chat.createdAt) || new Date().toISOString();
    const updatedAt = normalizeIsoDate(chat.updatedAt) || new Date().toISOString();
    const normalizedChat = {
        title: chat.title || 'New conversation',
        createdAt,
        updatedAt,
        messages: serializeChatMessages(chat.messages || []),
    };

    await setDoc(chatDocRef(userId, chat.id), normalizedChat, { merge: true });

    return normalizeChat(chat.id, normalizedChat);
}

export async function deleteUserChat(userId, chatId) {
    if (!userId || !chatId) return;
    await deleteDoc(chatDocRef(userId, chatId));
}

export async function getUserProfile(userId, fallbackUser = {}) {
    if (!userId) {
        return {
            ...DEFAULT_PROFILE,
            displayName: fallbackUser.name || DEFAULT_PROFILE.displayName,
        };
    }

    const profileSnap = await getDoc(profileDocRef(userId));
    const profileData = profileSnap.exists() ? profileSnap.data() : {};

    return {
        displayName: profileData.displayName || fallbackUser.name || DEFAULT_PROFILE.displayName,
        preferences: {
            ...DEFAULT_PREFERENCES,
            ...(profileData.preferences || {}),
        },
    };
}

export async function saveUserProfile(userId, profile = {}) {
    if (!userId) return null;

    const mergedProfile = {
        displayName: profile.displayName || DEFAULT_PROFILE.displayName,
        preferences: {
            ...DEFAULT_PREFERENCES,
            ...(profile.preferences || {}),
        },
    };

    await setDoc(profileDocRef(userId), mergedProfile, { merge: true });
    return mergedProfile;
}

export function computeStreakFromChats(chats = []) {
    const activeDaySet = new Set();
    let totalSolved = 0;

    chats.forEach((chat) => {
        (chat.messages || []).forEach((message) => {
            const role = message.role || (message.type === 'user' ? 'user' : 'bot');
            if (role !== 'user') return;

            totalSolved += 1;

            const timestamp = normalizeIsoDate(message.timestamp);
            if (timestamp) {
                activeDaySet.add(timestamp.slice(0, 10));
            }
        });
    });

    const activeDays = Array.from(activeDaySet).sort();

    let longestStreak = 0;
    let rollingStreak = 0;

    activeDays.forEach((day, index) => {
        if (index === 0) {
            rollingStreak = 1;
        } else {
            const previous = new Date(activeDays[index - 1]);
            const current = new Date(day);
            const diffDays = Math.round((current - previous) / 86400000);
            rollingStreak = diffDays === 1 ? rollingStreak + 1 : 1;
        }

        longestStreak = Math.max(longestStreak, rollingStreak);
    });

    let currentStreak = 0;
    if (activeDays.length > 0) {
        const cursor = new Date();
        cursor.setHours(0, 0, 0, 0);

        for (let offset = 0; offset < 366; offset += 1) {
            const dateKey = cursor.toISOString().slice(0, 10);
            if (activeDaySet.has(dateKey)) {
                currentStreak += 1;
                cursor.setDate(cursor.getDate() - 1);
                continue;
            }

            if (offset === 0) {
                cursor.setDate(cursor.getDate() - 1);
                continue;
            }

            break;
        }
    }

    return {
        activeDays,
        totalSolved,
        totalActivities: totalSolved,
        chatActivities: totalSolved,
        quizActivities: 0,
        contestActivities: 0,
        currentStreak,
        longestStreak,
        lastActivityAt: null,
        updatedAt: new Date().toISOString(),
    };
}

function normalizeActivityDateKey(timestamp) {
    const normalized = normalizeIsoDate(timestamp);
    return normalized ? normalized.slice(0, 10) : null;
}

function computeStreakSummaryFromDays(activeDays = []) {
    const sortedDays = [...new Set(activeDays)].sort();
    let longestStreak = 0;
    let rollingStreak = 0;

    sortedDays.forEach((day, index) => {
        if (index === 0) {
            rollingStreak = 1;
        } else {
            const previous = new Date(sortedDays[index - 1]);
            const current = new Date(day);
            const diffDays = Math.round((current - previous) / 86400000);
            rollingStreak = diffDays === 1 ? rollingStreak + 1 : 1;
        }

        longestStreak = Math.max(longestStreak, rollingStreak);
    });

    let currentStreak = 0;
    if (sortedDays.length > 0) {
        const activeDaySet = new Set(sortedDays);
        const cursor = new Date();
        cursor.setHours(0, 0, 0, 0);

        for (let offset = 0; offset < 366; offset += 1) {
            const dateKey = cursor.toISOString().slice(0, 10);
            if (activeDaySet.has(dateKey)) {
                currentStreak += 1;
                cursor.setDate(cursor.getDate() - 1);
                continue;
            }

            if (offset === 0) {
                cursor.setDate(cursor.getDate() - 1);
                continue;
            }

            break;
        }
    }

    return {
        activeDays: sortedDays,
        currentStreak,
        longestStreak,
    };
}

function buildStreakFromActivitySources({ chats = [], quizAttempts = [], contestHistory = [] }) {
    const activeDaySet = new Set();
    let chatActivities = 0;
    let quizActivities = 0;
    let contestActivities = 0;
    let lastActivityAt = null;

    chats.forEach((chat) => {
        (chat.messages || []).forEach((message) => {
            const role = message.role || (message.type === 'user' ? 'user' : 'bot');
            if (role !== 'user') return;

            chatActivities += 1;
            const timestamp = normalizeIsoDate(message.timestamp);
            const dateKey = normalizeActivityDateKey(timestamp);
            if (dateKey) activeDaySet.add(dateKey);
            if (timestamp && (!lastActivityAt || new Date(timestamp) > new Date(lastActivityAt))) {
                lastActivityAt = timestamp;
            }
        });
    });

    quizAttempts.forEach((attempt) => {
        const timestamp = normalizeIsoDate(attempt.completedAt);
        const dateKey = normalizeActivityDateKey(timestamp);
        quizActivities += 1;
        if (dateKey) activeDaySet.add(dateKey);
        if (timestamp && (!lastActivityAt || new Date(timestamp) > new Date(lastActivityAt))) {
            lastActivityAt = timestamp;
        }
    });

    contestHistory.forEach((entry) => {
        const timestamp = normalizeIsoDate(entry.completedAt);
        const dateKey = normalizeActivityDateKey(timestamp);
        contestActivities += 1;
        if (dateKey) activeDaySet.add(dateKey);
        if (timestamp && (!lastActivityAt || new Date(timestamp) > new Date(lastActivityAt))) {
            lastActivityAt = timestamp;
        }
    });

    const streakSummary = computeStreakSummaryFromDays(Array.from(activeDaySet));
    const totalActivities = chatActivities + quizActivities + contestActivities;

    return {
        ...streakSummary,
        totalSolved: totalActivities,
        totalActivities,
        chatActivities,
        quizActivities,
        contestActivities,
        lastActivityAt,
        updatedAt: new Date().toISOString(),
    };
}

const topicIndex = new Map(TOPIC_CATALOG.map((topic) => [topic.label, topic]));

const normalizeTopicTag = (message = {}) => {
    if (message.topicTag) return message.topicTag;
    return inferTopicTag(message.text || message.content || '');
};

const computeActivityLevel = ({ totalQuestions, activeDays, totalSessions, weakTopics }) => {
    const weakDepth = weakTopics.length > 0 ? weakTopics[0].score : 0;
    const engagementScore =
        totalQuestions * 1.3 +
        activeDays * 2.2 +
        totalSessions * 1.6 +
        weakDepth * 0.08;

    if (engagementScore >= 85) return 'Highly Active';
    if (engagementScore >= 45) return 'Consistent';
    if (engagementScore >= 18) return 'Developing';
    return 'New';
};

export function computeAnalyticsFromChats(chats = []) {
    const topicMap = new Map(
        TOPIC_CATALOG.map((topic) => [
            topic.label,
            {
                topic: topic.label,
                topicId: topic.id,
                count: 0,
                recentCount: 0,
                sessionCount: 0,
                lastAskedAt: null,
                recencyScore: 0,
                spreadScore: 0,
                persistenceScore: 0,
                score: 0,
            },
        ])
    );

    const activeDaySet = new Set();
    let totalQuestions = 0;
    let repeatTopicStreak = 0;
    let previousTopic = null;

    const sortedChats = sortChatsByUpdatedAt(chats).reverse();

    sortedChats.forEach((chat, chatIndex) => {
        const sessionTopics = new Set();
        const messages = (chat.messages || []).filter((message) => (message.role || message.type) === 'user');

        messages.forEach((message, messageIndex) => {
            const topicTag = normalizeTopicTag(message);
            const topicEntry = topicMap.get(topicTag);
            if (!topicEntry) return;

            totalQuestions += 1;
            sessionTopics.add(topicTag);

            const timestamp = normalizeIsoDate(message.timestamp) || new Date().toISOString();
            activeDaySet.add(timestamp.slice(0, 10));

            topicEntry.count += 1;
            if (chatIndex >= Math.max(sortedChats.length - 5, 0)) {
                topicEntry.recentCount += 1;
            }

            if (!topicEntry.lastAskedAt || new Date(timestamp) > new Date(topicEntry.lastAskedAt)) {
                topicEntry.lastAskedAt = timestamp;
            }

            const confidence = Number.isFinite(message.topicConfidence) ? message.topicConfidence : 0.55;
            topicEntry.recencyScore += confidence * (1 + messageIndex * 0.04);

            if (previousTopic === topicTag) {
                repeatTopicStreak += 1;
            } else {
                repeatTopicStreak = 1;
                previousTopic = topicTag;
            }

            topicEntry.persistenceScore += Math.min(repeatTopicStreak, 4) * 0.9;
        });

        sessionTopics.forEach((topicTag) => {
            const topicEntry = topicMap.get(topicTag);
            if (topicEntry) {
                topicEntry.sessionCount += 1;
                topicEntry.spreadScore += 2.4;
            }
        });
    });

    const topicCounts = Array.from(topicMap.values())
        .filter((topic) => topic.count > 0)
        .map((topic) => {
            const share = totalQuestions > 0 ? topic.count / totalQuestions : 0;
            const recentWeight = topic.recentCount * 1.7;
            const volumeWeight = topic.count * 2.6;
            const recencySignal = topic.recencyScore * 1.15;
            const spreadWeight = topic.spreadScore;
            const persistenceWeight = topic.persistenceScore;
            const domainWeight = topicIndex.get(topic.topic)?.weight || 1;
            const score = (volumeWeight + recentWeight + recencySignal + spreadWeight + persistenceWeight) * domainWeight;

            return {
                ...topic,
                share: Number((share * 100).toFixed(1)),
                score: Number(score.toFixed(2)),
            };
        })
        .sort((left, right) => right.score - left.score);

    const weakTopics = topicCounts.slice(0, 3).map((topic) => ({
        topic: topic.topic,
        count: topic.count,
        score: topic.score,
        share: topic.share,
    }));

    const mostAskedTopics = [...topicCounts]
        .sort((left, right) => right.count - left.count || right.score - left.score)
        .slice(0, 4)
        .map((topic) => ({
            topic: topic.topic,
            count: topic.count,
            share: topic.share,
            score: topic.score,
        }));

    const activeDays = activeDaySet.size;
    const totalSessions = chats.filter((chat) => (chat.messages || []).length > 0).length;
    const activityLevel = computeActivityLevel({
        totalQuestions,
        activeDays,
        totalSessions,
        weakTopics,
    });

    return {
        weakTopics,
        mostAskedTopics,
        topicCounts: topicCounts.map((topic) => ({
            topic: topic.topic,
            count: topic.count,
            recentCount: topic.recentCount,
            sessionCount: topic.sessionCount,
            share: topic.share,
            score: topic.score,
        })),
        activityLevel,
        totalQuestions,
        activeDays,
        totalSessions,
        updatedAt: new Date().toISOString(),
    };
}

export async function getUserStreak(userId) {
    if (!userId) return DEFAULT_STREAK;

    const streakSnap = await getDoc(streakDocRef(userId));
    if (!streakSnap.exists()) {
        return DEFAULT_STREAK;
    }

    const data = streakSnap.data();
    return {
        activeDays: Array.isArray(data.activeDays) ? data.activeDays : [],
        totalSolved: Number.isFinite(data.totalSolved) ? data.totalSolved : 0,
        totalActivities: Number.isFinite(data.totalActivities) ? data.totalActivities : Number.isFinite(data.totalSolved) ? data.totalSolved : 0,
        chatActivities: Number.isFinite(data.chatActivities) ? data.chatActivities : Number.isFinite(data.totalSolved) ? data.totalSolved : 0,
        quizActivities: Number.isFinite(data.quizActivities) ? data.quizActivities : 0,
        contestActivities: Number.isFinite(data.contestActivities) ? data.contestActivities : 0,
        currentStreak: Number.isFinite(data.currentStreak) ? data.currentStreak : 0,
        longestStreak: Number.isFinite(data.longestStreak) ? data.longestStreak : 0,
        lastActivityAt: normalizeIsoDate(data.lastActivityAt),
        updatedAt: normalizeIsoDate(data.updatedAt),
    };
}

export async function getUserAnalytics(userId) {
    if (!userId) return DEFAULT_ANALYTICS;

    const analyticsSnap = await getDoc(analyticsDocRef(userId));
    if (!analyticsSnap.exists()) {
        return DEFAULT_ANALYTICS;
    }

    const data = analyticsSnap.data();
    return {
        weakTopics: Array.isArray(data.weakTopics) ? data.weakTopics : [],
        mostAskedTopics: Array.isArray(data.mostAskedTopics) ? data.mostAskedTopics : [],
        topicCounts: Array.isArray(data.topicCounts) ? data.topicCounts : [],
        activityLevel: data.activityLevel || 'New',
        totalQuestions: Number.isFinite(data.totalQuestions) ? data.totalQuestions : 0,
        activeDays: Number.isFinite(data.activeDays) ? data.activeDays : 0,
        totalSessions: Number.isFinite(data.totalSessions) ? data.totalSessions : 0,
        quizzesAttended: Number.isFinite(data.quizzesAttended) ? data.quizzesAttended : 0,
        cumulativeQuizScore: Number.isFinite(data.cumulativeQuizScore) ? data.cumulativeQuizScore : 0,
        averageQuizScore: Number.isFinite(data.averageQuizScore) ? data.averageQuizScore : 0,
        bestQuizScore: Number.isFinite(data.bestQuizScore) ? data.bestQuizScore : 0,
        lastQuizScore: Number.isFinite(data.lastQuizScore) ? data.lastQuizScore : 0,
        recentQuizScores: Array.isArray(data.recentQuizScores) ? data.recentQuizScores : [],
        updatedAt: normalizeIsoDate(data.updatedAt),
    };
}

export async function saveUserStreak(userId, streak = {}) {
    if (!userId) return DEFAULT_STREAK;

    const normalizedStreak = {
        activeDays: Array.isArray(streak.activeDays) ? streak.activeDays : [],
        totalSolved: Number.isFinite(streak.totalSolved) ? streak.totalSolved : 0,
        totalActivities: Number.isFinite(streak.totalActivities) ? streak.totalActivities : Number.isFinite(streak.totalSolved) ? streak.totalSolved : 0,
        chatActivities: Number.isFinite(streak.chatActivities) ? streak.chatActivities : 0,
        quizActivities: Number.isFinite(streak.quizActivities) ? streak.quizActivities : 0,
        contestActivities: Number.isFinite(streak.contestActivities) ? streak.contestActivities : 0,
        currentStreak: Number.isFinite(streak.currentStreak) ? streak.currentStreak : 0,
        longestStreak: Number.isFinite(streak.longestStreak) ? streak.longestStreak : 0,
        lastActivityAt: normalizeIsoDate(streak.lastActivityAt),
        updatedAt: normalizeIsoDate(streak.updatedAt) || new Date().toISOString(),
    };

    await setDoc(streakDocRef(userId), normalizedStreak, { merge: true });
    return normalizedStreak;
}

export async function saveUserAnalytics(userId, analytics = {}) {
    if (!userId) return DEFAULT_ANALYTICS;

    const normalizedAnalytics = {
        weakTopics: Array.isArray(analytics.weakTopics) ? analytics.weakTopics : [],
        mostAskedTopics: Array.isArray(analytics.mostAskedTopics) ? analytics.mostAskedTopics : [],
        topicCounts: Array.isArray(analytics.topicCounts) ? analytics.topicCounts : [],
        activityLevel: analytics.activityLevel || 'New',
        totalQuestions: Number.isFinite(analytics.totalQuestions) ? analytics.totalQuestions : 0,
        activeDays: Number.isFinite(analytics.activeDays) ? analytics.activeDays : 0,
        totalSessions: Number.isFinite(analytics.totalSessions) ? analytics.totalSessions : 0,
        quizzesAttended: Number.isFinite(analytics.quizzesAttended) ? analytics.quizzesAttended : 0,
        cumulativeQuizScore: Number.isFinite(analytics.cumulativeQuizScore) ? analytics.cumulativeQuizScore : 0,
        averageQuizScore: Number.isFinite(analytics.averageQuizScore) ? analytics.averageQuizScore : 0,
        bestQuizScore: Number.isFinite(analytics.bestQuizScore) ? analytics.bestQuizScore : 0,
        lastQuizScore: Number.isFinite(analytics.lastQuizScore) ? analytics.lastQuizScore : 0,
        recentQuizScores: Array.isArray(analytics.recentQuizScores) ? analytics.recentQuizScores : [],
        updatedAt: normalizeIsoDate(analytics.updatedAt) || new Date().toISOString(),
    };

    await setDoc(analyticsDocRef(userId), normalizedAnalytics, { merge: true });
    return normalizedAnalytics;
}

export async function syncUserStreakFromChats(userId, chats = []) {
    if (!userId) return DEFAULT_STREAK;

    const [quizAttemptsSnap, ratingSnap] = await Promise.all([
        getDocs(query(quizAttemptsCollectionRef(userId), orderBy('completedAt', 'desc'), limit(100))),
        getDoc(ratingDocRef(userId)),
    ]);

    const quizAttempts = quizAttemptsSnap.docs.map((attemptDoc) => ({
        id: attemptDoc.id,
        ...attemptDoc.data(),
        completedAt: normalizeIsoDate(attemptDoc.data().completedAt),
    }));
    const contestHistory = ratingSnap.exists() && Array.isArray(ratingSnap.data().contestHistory)
        ? ratingSnap.data().contestHistory.map((entry) => ({
            ...entry,
            completedAt: normalizeIsoDate(entry.completedAt),
        }))
        : [];

    const streak = buildStreakFromActivitySources({ chats, quizAttempts, contestHistory });
    await saveUserStreak(userId, streak);
    return streak;
}

export async function syncUserAnalyticsFromChats(userId, chats = []) {
    const analytics = computeAnalyticsFromChats(chats);
    await saveUserAnalytics(userId, analytics);
    return analytics;
}

export function sortUserChats(chats = []) {
    return sortChatsByUpdatedAt(chats);
}
