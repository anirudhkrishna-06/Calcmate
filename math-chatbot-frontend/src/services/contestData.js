import {
    collection,
    doc,
    getDoc,
    getDocs,
    limit,
    orderBy,
    query,
    setDoc,
    writeBatch,
} from 'firebase/firestore';
import { db } from '../../firebase';
import { API_BASE } from '../config/api';
import { createClientId, listUserChats, syncUserStreakFromChats } from './userData';

const contestsCollectionRef = () => collection(db, 'contests');
const contestDocRef = (contestId) => doc(db, 'contests', contestId);
const contestSubmissionDocRef = (contestId, userId) => doc(db, 'contests', contestId, 'submissions', userId);
const contestLeaderboardDocRef = (contestId, userId) => doc(db, 'contests', contestId, 'leaderboard', userId);
const contestAuditDocRef = (contestId) => doc(db, 'contests', contestId, 'audit', 'latest');
const userNotificationDocRef = (userId, notificationId) => doc(db, 'users', userId, 'notifications', notificationId);
const userRatingDocRef = (userId) => doc(db, 'users', userId, 'rating', 'summary');

const normalizeIsoDate = (value) => {
    if (!value) return null;
    if (typeof value === 'string') return value;
    if (typeof value?.toDate === 'function') return value.toDate().toISOString();
    if (value instanceof Date) return value.toISOString();
    return null;
};

const normalizeContest = (contestId, data = {}) => {
    const startTime = normalizeIsoDate(data.startTime);
    const endTime = normalizeIsoDate(data.endTime);
    const now = Date.now();
    const startMs = startTime ? new Date(startTime).getTime() : 0;
    const endMs = endTime ? new Date(endTime).getTime() : 0;
    const derivedStatus = now < startMs ? 'UPCOMING' : now <= endMs ? 'LIVE' : 'COMPLETED';

    return {
        id: contestId,
        title: data.title || 'Untitled Contest',
        createdBy: data.createdBy || '',
        createdByName: data.createdByName || 'Teacher',
        visibility: data.visibility || 'private',
        startTime,
        endTime,
        duration: Number.isFinite(data.duration) ? data.duration : 3600,
        participantsCount: Number.isFinite(data.participantsCount) ? data.participantsCount : 0,
        invitedStudentIds: Array.isArray(data.invitedStudentIds) ? data.invitedStudentIds : [],
        questions: Array.isArray(data.questions) ? data.questions : [],
        status: data.status || derivedStatus,
        snapshotHash: data.snapshotHash || '',
        createdAt: normalizeIsoDate(data.createdAt),
        updatedAt: normalizeIsoDate(data.updatedAt),
        tags: Array.isArray(data.tags) ? data.tags : [],
    };
};

const sortByStartTime = (items = []) =>
    [...items].sort((left, right) => new Date(right.startTime || 0).getTime() - new Date(left.startTime || 0).getTime());

const questionSnapshotHash = (questions = []) => {
    const payload = JSON.stringify(
        questions.map((question) => ({
            questionId: question.questionId,
            difficultyRating: question.difficultyRating,
            topic: question.topic,
            correctAnswer: question.correctAnswer,
        }))
    );
    let hash = 0;
    for (let index = 0; index < payload.length; index += 1) {
        hash = (hash << 5) - hash + payload.charCodeAt(index);
        hash |= 0;
    }
    return `contest_${Math.abs(hash)}`;
};

export async function fetchContestProblemBank({ search = '', topic = '', level = '', limit: maxCount = 48 } = {}) {
    const params = new URLSearchParams();
    params.set('limit', String(maxCount));
    if (search.trim()) params.set('search', search.trim());
    if (topic.trim()) params.set('topic', topic.trim());
    if (level.trim()) params.set('level', level.trim());

    const response = await fetch(`${API_BASE}/contest/problems?${params.toString()}`);
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Unable to load olympiad problem bank.');
    }

    const data = await response.json();
    return Array.isArray(data.problems) ? data.problems : [];
}

export async function getServerContestTime() {
    const response = await fetch(`${API_BASE}/contest/server-time`);
    if (!response.ok) {
        throw new Error('Unable to verify server time.');
    }

    return response.json();
}

export async function getUserRatingProfile(userId) {
    if (!userId) {
        return {
            currentRating: 0,
            maxRating: 0,
            contestHistory: [],
            streak: 0,
            volatility: 1.15,
            contestsPlayed: 0,
            averageRank: null,
            lastRatingChange: 0,
        };
    }

    const ratingSnap = await getDoc(userRatingDocRef(userId));
    if (!ratingSnap.exists()) {
        return {
            currentRating: 0,
            maxRating: 0,
            contestHistory: [],
            streak: 0,
            volatility: 1.15,
            contestsPlayed: 0,
            averageRank: null,
            lastRatingChange: 0,
        };
    }

    const data = ratingSnap.data();
    return {
        currentRating: Number.isFinite(data.currentRating) ? data.currentRating : 0,
        maxRating: Number.isFinite(data.maxRating) ? data.maxRating : 0,
        contestHistory: Array.isArray(data.contestHistory) ? data.contestHistory : [],
        streak: Number.isFinite(data.streak) ? data.streak : 0,
        volatility: Number.isFinite(data.volatility) ? data.volatility : 1.15,
        contestsPlayed: Number.isFinite(data.contestsPlayed) ? data.contestsPlayed : 0,
        averageRank: Number.isFinite(data.averageRank) ? data.averageRank : null,
        lastRatingChange: Number.isFinite(data.lastRatingChange) ? data.lastRatingChange : 0,
    };
}

export async function createContest({
    teacherId,
    teacherName,
    visibility,
    title,
    startTime,
    endTime,
    questions,
    invitedStudentIds = [],
}) {
    if (!teacherId) throw new Error('Teacher ID is required.');
    if (!title?.trim()) throw new Error('Contest title is required.');
    if (!Array.isArray(questions) || questions.length === 0) throw new Error('Select at least one contest problem.');

    const contestId = createClientId();
    const createdAt = new Date().toISOString();
    const normalizedQuestions = questions.map((question) => ({
        questionId: question.questionId,
        statement: question.statement,
        correctAnswer: Number(question.correctAnswer),
        difficultyRating: Number(question.difficultyRating),
        topic: question.topic || 'Olympiad',
    }));
    const durationSeconds = Math.max(
        60,
        Math.round((new Date(endTime).getTime() - new Date(startTime).getTime()) / 1000)
    );
    const payload = {
        title: title.trim(),
        createdBy: teacherId,
        createdByName: teacherName || 'Teacher',
        visibility: visibility === 'public' ? 'public' : 'private',
        startTime,
        endTime,
        duration: durationSeconds,
        questions: normalizedQuestions,
        status: 'UPCOMING',
        participantsCount: 0,
        invitedStudentIds,
        snapshotHash: questionSnapshotHash(normalizedQuestions),
        createdAt,
        updatedAt: createdAt,
        tags: [...new Set(normalizedQuestions.map((question) => question.topic).filter(Boolean))].slice(0, 6),
    };

    await setDoc(contestDocRef(contestId), payload);

    if (payload.visibility === 'private' && invitedStudentIds.length > 0) {
        const notificationBatch = writeBatch(db);
        invitedStudentIds.forEach((studentId) => {
            const notificationId = createClientId();
            notificationBatch.set(userNotificationDocRef(studentId, notificationId), {
                id: notificationId,
                type: 'contest',
                title: `${payload.title} is scheduled`,
                body: `${teacherName || 'Your teacher'} assigned a time-bound olympiad contest. Review the window and join when it goes live.`,
                contestId,
                teacherId,
                teacherName: teacherName || 'Teacher',
                createdAt,
                read: false,
                attended: false,
                targetPath: `/contests?contest=${contestId}`,
            });
        });
        await notificationBatch.commit();
    }

    return normalizeContest(contestId, payload);
}

export async function listVisibleContests(user, maxCount = 36) {
    if (!user?.id) return [];

    const snapshot = await getDocs(query(contestsCollectionRef(), orderBy('startTime', 'desc'), limit(maxCount)));
    const contests = snapshot.docs.map((contestDoc) => normalizeContest(contestDoc.id, contestDoc.data()));

    return sortByStartTime(
        contests.filter((contest) => {
            if (contest.visibility === 'public') return true;
            if (user.role === 'teacher') return contest.createdBy === user.id;
            return contest.invitedStudentIds.includes(user.id) || contest.createdBy === user.teacherId;
        })
    );
}

export async function getContest(contestId) {
    if (!contestId) return null;
    const snapshot = await getDoc(contestDocRef(contestId));
    if (!snapshot.exists()) return null;
    return normalizeContest(snapshot.id, snapshot.data());
}

export async function listContestSubmissions(contestId) {
    if (!contestId) return [];
    const snapshot = await getDocs(query(collection(db, 'contests', contestId, 'submissions')));
    return snapshot.docs.map((submissionDoc) => ({
        id: submissionDoc.id,
        ...submissionDoc.data(),
        startTime: normalizeIsoDate(submissionDoc.data().startTime),
        endTime: normalizeIsoDate(submissionDoc.data().endTime),
    }));
}

export async function getContestSubmission(contestId, userId) {
    if (!contestId || !userId) return null;
    const submissionSnap = await getDoc(contestSubmissionDocRef(contestId, userId));
    if (!submissionSnap.exists()) return null;
    return {
        id: submissionSnap.id,
        ...submissionSnap.data(),
        startTime: normalizeIsoDate(submissionSnap.data().startTime),
        endTime: normalizeIsoDate(submissionSnap.data().endTime),
    };
}

export async function listContestLeaderboard(contestId) {
    if (!contestId) return [];
    const snapshot = await getDocs(query(collection(db, 'contests', contestId, 'leaderboard')));
    const entries = snapshot.docs.map((entryDoc) => ({ id: entryDoc.id, ...entryDoc.data() }));
    return [...entries].sort((left, right) => {
        const leftRank = left.rank == null ? Number.POSITIVE_INFINITY : left.rank;
        const rightRank = right.rank == null ? Number.POSITIVE_INFINITY : right.rank;
        return leftRank - rightRank || (right.score || 0) - (left.score || 0);
    });
}

async function evaluateContestOnServer(contest, submissions) {
    const ratingProfiles = await Promise.all(submissions.map((submission) => getUserRatingProfile(submission.userId)));
    const response = await fetch(`${API_BASE}/contest/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            contest: {
                contestId: contest.id,
                title: contest.title,
                visibility: contest.visibility,
                startTime: contest.startTime,
                endTime: contest.endTime,
                duration: contest.duration,
                questions: contest.questions,
            },
            submissions: submissions.map((submission, index) => ({
                userId: submission.userId,
                displayName: submission.displayName || submission.userId,
                startTime: submission.startTime,
                endTime: submission.endTime,
                answers: (submission.answers || []).map((answer) => ({
                    qId: answer.qId,
                    answer: answer.answer ?? null,
                    timestamp: answer.timestamp,
                })),
                currentRating: ratingProfiles[index].currentRating,
                maxRating: ratingProfiles[index].maxRating,
                experience: ratingProfiles[index].contestsPlayed,
                streak: ratingProfiles[index].streak,
                volatility: ratingProfiles[index].volatility,
            })),
        }),
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Contest evaluation failed.');
    }

    return response.json();
}

async function persistContestEvaluation(contest, evaluation) {
    const batch = writeBatch(db);
    const createdAt = new Date().toISOString();

    evaluation.evaluations.forEach((entry) => {
        batch.set(
            contestSubmissionDocRef(contest.id, entry.userId),
            {
                userId: entry.userId,
                displayName: entry.displayName,
                answers: entry.answers,
                startTime: entry.startTime,
                endTime: entry.endTime,
                totalCorrect: entry.totalCorrect,
                totalTime: entry.totalTime,
                penalties: entry.penalties,
                difficultySolved: entry.difficultySolved,
                performanceScore: entry.performanceScore,
                isValid: entry.isValid,
                fairnessFlags: entry.fairnessFlags,
                ratingChange: entry.ratingChange,
                newRating: entry.newRating,
                updatedAt: createdAt,
            },
            { merge: true }
        );
        batch.set(
            contestLeaderboardDocRef(contest.id, entry.userId),
            {
                userId: entry.userId,
                displayName: entry.displayName,
                score: entry.totalCorrect,
                rank: evaluation.leaderboard.find((item) => item.userId === entry.userId)?.rank ?? null,
                ratingChange: entry.ratingChange,
                newRating: entry.newRating,
                totalTime: entry.totalTime,
                difficultySolved: entry.difficultySolved,
                performanceScore: entry.performanceScore,
                disqualified: !entry.isValid,
                fairnessFlags: entry.fairnessFlags,
                updatedAt: createdAt,
            },
            { merge: true }
        );
    });

    batch.set(
        contestAuditDocRef(contest.id),
        {
            ...evaluation.audit,
            leaderboardHash: evaluation.audit.hash,
            updatedAt: createdAt,
        },
        { merge: true }
    );

    batch.set(
        contestDocRef(contest.id),
        {
            participantsCount: evaluation.evaluations.length,
            status: new Date(contest.endTime).getTime() < Date.now() ? 'COMPLETED' : contest.status,
            updatedAt: createdAt,
        },
        { merge: true }
    );

    await batch.commit();

    await Promise.all(
        evaluation.evaluations.map(async (entry) => {
            const profile = await getUserRatingProfile(entry.userId);
            const previousHistory = Array.isArray(profile.contestHistory) ? profile.contestHistory : [];
            const existingHistoryEntry = previousHistory.find((item) => item.contestId === contest.id);
            const nextHistoryEntry = {
                contestId: contest.id,
                contestTitle: contest.title,
                rank: evaluation.leaderboard.find((item) => item.userId === entry.userId)?.rank ?? null,
                score: entry.totalCorrect,
                ratingChange: entry.ratingChange,
                newRating: entry.newRating,
                completedAt: createdAt,
                isValid: entry.isValid,
            };
            const contestHistory = [nextHistoryEntry, ...previousHistory.filter((item) => item.contestId !== contest.id)].slice(0, 15);
            const validRanks = contestHistory.filter((item) => Number.isFinite(item.rank)).map((item) => item.rank);
            await setDoc(
                userRatingDocRef(entry.userId),
                {
                    currentRating: entry.newRating,
                    maxRating: Math.max(profile.maxRating || 0, entry.newRating),
                    contestHistory,
                    streak: existingHistoryEntry ? (profile.streak || 0) : entry.isValid ? (profile.streak || 0) + 1 : 0,
                    volatility: entry.volatility,
                    contestsPlayed: existingHistoryEntry ? (profile.contestsPlayed || 0) : (profile.contestsPlayed || 0) + 1,
                    averageRank:
                        validRanks.length > 0
                            ? Number((validRanks.reduce((sum, rank) => sum + rank, 0) / validRanks.length).toFixed(2))
                            : null,
                    lastRatingChange: entry.ratingChange,
                    updatedAt: createdAt,
                },
                { merge: true }
            );

            const chats = await listUserChats(entry.userId, 100);
            await syncUserStreakFromChats(entry.userId, chats);
        })
    );
}

export async function submitContestAttempt({ contest, user, answers, startTime, endTime }) {
    if (!contest?.id || !user?.id) throw new Error('Contest and user are required.');

    const existingSubmissions = await listContestSubmissions(contest.id);
    const candidateMap = new Map(existingSubmissions.map((submission) => [submission.userId, submission]));
    candidateMap.set(user.id, {
        userId: user.id,
        displayName: user.displayName || user.name || 'Student',
        startTime,
        endTime,
        answers,
    });

    const evaluation = await evaluateContestOnServer(contest, Array.from(candidateMap.values()));
    await persistContestEvaluation(contest, evaluation);
    return evaluation;
}
