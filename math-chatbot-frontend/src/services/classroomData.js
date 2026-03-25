import {
    arrayUnion,
    collection,
    doc,
    getDoc,
    getDocs,
    limit,
    orderBy,
    query,
    setDoc,
    updateDoc,
} from 'firebase/firestore';
import { db } from '../../firebase';
import {
    createClientId,
    getUserAnalytics,
    listUserChats,
    saveUserAnalytics,
} from './userData';
import { getUserRatingProfile } from './contestData';

const teacherStudentsCollectionRef = (teacherId) => collection(db, 'teachers', teacherId, 'students');
const teacherStudentDocRef = (teacherId, studentId) => doc(db, 'teachers', teacherId, 'students', studentId);
const notificationsCollectionRef = (userId) => collection(db, 'users', userId, 'notifications');
const notificationDocRef = (userId, notificationId) => doc(db, 'users', userId, 'notifications', notificationId);
const quizAttemptsCollectionRef = (userId) => collection(db, 'users', userId, 'quizAttempts');
const quizAttemptDocRef = (userId, attemptId) => doc(db, 'users', userId, 'quizAttempts', attemptId);

const normalizeIsoDate = (value) => {
    if (!value) return null;
    if (typeof value === 'string') return value;
    if (typeof value?.toDate === 'function') return value.toDate().toISOString();
    if (value instanceof Date) return value.toISOString();
    return null;
};

export async function addStudentToTeacher(teacherId, studentId) {
    if (!teacherId || !studentId) {
        throw new Error('Teacher ID and student ID are required.');
    }

    const studentSnap = await getDoc(doc(db, 'users', studentId));
    if (!studentSnap.exists()) {
        throw new Error('No student account was found for that ID.');
    }

    const studentData = studentSnap.data();
    if (studentData.role !== 'student') {
        throw new Error('That user is not registered as a student.');
    }

    const linkedAt = new Date().toISOString();

    await Promise.all([
        setDoc(
            teacherStudentDocRef(teacherId, studentId),
            {
                studentId,
                displayName: studentData.name || 'Student',
                email: studentData.email || '',
                linkedAt,
            },
            { merge: true }
        ),
        setDoc(
            doc(db, 'users', teacherId),
            {
                studentIds: arrayUnion(studentId),
            },
            { merge: true }
        ),
        setDoc(
            doc(db, 'users', studentId),
            {
                teacherId,
            },
            { merge: true }
        ),
    ]);

    return {
        id: studentId,
        name: studentData.name || 'Student',
        email: studentData.email || '',
        teacherId,
        linkedAt,
    };
}

export async function listTeacherStudents(teacherId) {
    if (!teacherId) return [];

    const snapshot = await getDocs(query(teacherStudentsCollectionRef(teacherId), orderBy('linkedAt', 'desc')));

    const students = await Promise.all(
        snapshot.docs.map(async (studentDoc) => {
            const base = studentDoc.data();
            const studentId = studentDoc.id;
            const [userSnap, analytics, chats, quizSummary, ratingProfile] = await Promise.all([
                getDoc(doc(db, 'users', studentId)),
                getUserAnalytics(studentId),
                listUserChats(studentId, 25),
                getUserQuizSummary(studentId),
                getUserRatingProfile(studentId),
            ]);

            const userData = userSnap.exists() ? userSnap.data() : {};
            const chatQuestions = chats.reduce(
                (sum, chat) =>
                    sum +
                    (chat.messages?.filter((message) => (message.role || message.type) === 'user').length || 0),
                0
            );
            const latestChat = chats[0] || null;

            return {
                id: studentId,
                name: userData.name || base.displayName || 'Student',
                email: userData.email || base.email || '',
                linkedAt: normalizeIsoDate(base.linkedAt),
                analytics,
                chatSummary: {
                    totalSessions: chats.length,
                    totalQuestions: chatQuestions,
                    latestChatTitle: latestChat?.title || 'No conversations yet',
                    latestChatAt: latestChat?.updatedAt || null,
                },
                quizSummary,
                ratingProfile,
            };
        })
    );

    return students;
}

export async function createQuizNotification({ teacherId, teacherName, studentIds, title, body }) {
    if (!teacherId || !Array.isArray(studentIds) || studentIds.length === 0) {
        throw new Error('At least one linked student is required.');
    }

    const notificationId = createClientId();
    const createdAt = new Date().toISOString();
    const payload = {
        id: notificationId,
        type: 'quiz',
        title: title || 'Adaptive Quiz Assigned',
        body: body || 'Your teacher has asked you to attend an adaptive quiz session.',
        teacherId,
        teacherName: teacherName || 'Teacher',
        createdAt,
        read: false,
        attended: false,
        targetPath: `/quiz?notification=${notificationId}`,
    };

    await Promise.all(
        studentIds.map((studentId) =>
            setDoc(notificationDocRef(studentId, notificationId), {
                ...payload,
                studentId,
            })
        )
    );

    return payload;
}

export async function listUserNotifications(userId, maxCount = 10) {
    if (!userId) return [];

    const snapshot = await getDocs(
        query(notificationsCollectionRef(userId), orderBy('createdAt', 'desc'), limit(maxCount))
    );

    return snapshot.docs.map((notificationDoc) => ({
        id: notificationDoc.id,
        ...notificationDoc.data(),
        createdAt: normalizeIsoDate(notificationDoc.data().createdAt),
    }));
}

export async function getUserNotification(userId, notificationId) {
    if (!userId || !notificationId) return null;

    const notificationSnap = await getDoc(notificationDocRef(userId, notificationId));
    if (!notificationSnap.exists()) return null;

    return {
        id: notificationSnap.id,
        ...notificationSnap.data(),
        createdAt: normalizeIsoDate(notificationSnap.data().createdAt),
    };
}

export async function markNotificationRead(userId, notificationId, updates = {}) {
    if (!userId || !notificationId) return;

    await setDoc(
        notificationDocRef(userId, notificationId),
        {
            read: true,
            readAt: new Date().toISOString(),
            ...updates,
        },
        { merge: true }
    );
}

export async function listUserQuizAttempts(userId, maxCount = 20) {
    if (!userId) return [];

    const snapshot = await getDocs(
        query(quizAttemptsCollectionRef(userId), orderBy('completedAt', 'desc'), limit(maxCount))
    );

    return snapshot.docs.map((attemptDoc) => ({
        id: attemptDoc.id,
        ...attemptDoc.data(),
        completedAt: normalizeIsoDate(attemptDoc.data().completedAt),
    }));
}

export async function getUserQuizSummary(userId) {
    const attempts = await listUserQuizAttempts(userId, 25);

    if (attempts.length === 0) {
        return {
            attended: 0,
            averageScore: 0,
            bestScore: 0,
            latestScore: 0,
            recentAttempts: [],
        };
    }

    const totalPercentage = attempts.reduce((sum, attempt) => sum + (attempt.percentage || 0), 0);

    return {
        attended: attempts.length,
        averageScore: Number((totalPercentage / attempts.length).toFixed(1)),
        bestScore: Math.max(...attempts.map((attempt) => attempt.percentage || 0)),
        latestScore: attempts[0]?.percentage || 0,
        recentAttempts: attempts.slice(0, 4),
    };
}

export async function recordQuizAttempt(userId, attempt) {
    if (!userId) return null;

    const attemptId = createClientId();
    const completedAt = new Date().toISOString();
    const normalizedAttempt = {
        id: attemptId,
        source: attempt.source || 'self_practice',
        notificationId: attempt.notificationId || null,
        teacherId: attempt.teacherId || null,
        sessionId: attempt.sessionId || null,
        score: Number.isFinite(attempt.score) ? attempt.score : 0,
        totalQuestions: Number.isFinite(attempt.totalQuestions) ? attempt.totalQuestions : 0,
        percentage: Number.isFinite(attempt.percentage) ? attempt.percentage : 0,
        topicBreakdown: Array.isArray(attempt.topicBreakdown) ? attempt.topicBreakdown : [],
        completedAt,
    };

    await setDoc(quizAttemptDocRef(userId, attemptId), normalizedAttempt);

    const analytics = await getUserAnalytics(userId);
    const quizzesAttended = (analytics.quizzesAttended || 0) + 1;
    const cumulativeQuizScore = (analytics.cumulativeQuizScore || 0) + normalizedAttempt.percentage;
    const averageQuizScore = cumulativeQuizScore / quizzesAttended;
    const recentQuizScores = [
        normalizedAttempt.percentage,
        ...((analytics.recentQuizScores || []).slice(0, 4)),
    ].slice(0, 5);

    await saveUserAnalytics(userId, {
        ...analytics,
        quizzesAttended,
        cumulativeQuizScore,
        averageQuizScore: Number(averageQuizScore.toFixed(1)),
        bestQuizScore: Math.max(analytics.bestQuizScore || 0, normalizedAttempt.percentage),
        lastQuizScore: normalizedAttempt.percentage,
        recentQuizScores,
    });

    if (normalizedAttempt.notificationId) {
        await markNotificationRead(userId, normalizedAttempt.notificationId, {
            attended: true,
            attendedAt: completedAt,
        });
    }

    return normalizedAttempt;
}
