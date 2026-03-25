import React, { createContext, useContext, useState, useEffect } from 'react';
import { 
    signInWithEmailAndPassword, 
    createUserWithEmailAndPassword, 
    signOut, 
    onAuthStateChanged 
} from 'firebase/auth';
import { doc, setDoc, getDoc } from 'firebase/firestore';
import { auth, db } from '../../firebase';
import { getUserProfile, saveUserAnalytics, saveUserProfile, saveUserStreak } from '../services/userData';

const AuthContext = createContext(null);

async function ensureUserRecord(firebaseUser, existingUserData = null) {
    const baseUserData = existingUserData || {
        name: firebaseUser.displayName || 'User',
        email: firebaseUser.email || '',
        role: 'student',
        createdAt: new Date().toISOString(),
        teacherId: null,
    };

    await setDoc(doc(db, 'users', firebaseUser.uid), baseUserData, { merge: true });
    await Promise.all([
        saveUserProfile(firebaseUser.uid, {
            displayName: baseUserData.name || firebaseUser.displayName || 'User',
            preferences: {
                emailNotifications: true,
                darkMode: false,
            },
        }),
        saveUserStreak(firebaseUser.uid, {
            activeDays: [],
            totalSolved: 0,
            currentStreak: 0,
            longestStreak: 0,
        }),
        saveUserAnalytics(firebaseUser.uid, {
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
        }),
        setDoc(doc(db, 'users', firebaseUser.uid, 'rating', 'summary'), {
            currentRating: 0,
            maxRating: 0,
            contestHistory: [],
            streak: 0,
            volatility: 1.15,
            contestsPlayed: 0,
            averageRank: null,
            lastRatingChange: 0,
        }, { merge: true }),
    ]);

    return baseUserData;
}

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
            if (firebaseUser) {
                try {
                    const userDocRef = doc(db, 'users', firebaseUser.uid);
                    const userDoc = await getDoc(userDocRef);
                    if (userDoc.exists()) {
                        const userData = userDoc.data();
                        const profile = await getUserProfile(firebaseUser.uid, userData);

                        setUser({
                            id: firebaseUser.uid,
                            ...userData,
                            displayName: profile.displayName || userData.name || 'User',
                            preferences: profile.preferences,
                        });
                    } else {
                        const repairedUserData = await ensureUserRecord(firebaseUser);
                        const fallbackUser = {
                            id: firebaseUser.uid,
                            ...repairedUserData,
                        };
                        const profile = await getUserProfile(firebaseUser.uid, repairedUserData);
                        setUser({
                            ...fallbackUser,
                            displayName: profile.displayName,
                            preferences: profile.preferences,
                        });
                    }
                } catch (error) {
                    console.error("Error fetching user data:", error);
                    setUser({ id: firebaseUser.uid, email: firebaseUser.email, name: 'User', role: 'student' });
                }
            } else {
                setUser(null);
            }
            setIsLoading(false);
        });

        return () => unsubscribe();
    }, []);

    const login = async (email, password) => {
        try {
            await signInWithEmailAndPassword(auth, email, password);
            return { success: true };
        } catch (error) {
            return { success: false, error: 'Invalid email or password' };
        }
    };

    const signup = async (name, email, password, role = 'student') => {
        try {
            const userCredential = await createUserWithEmailAndPassword(auth, email, password);
            const uid = userCredential.user.uid;
            
            const userData = {
                name,
                email,
                role,
                createdAt: new Date().toISOString(),
            };

            if (role === 'student') {
                userData.teacherId = null;
            } else if (role === 'teacher') {
                userData.studentIds = [];
            }

            await setDoc(doc(db, 'users', uid), userData);
            await Promise.all([
                saveUserProfile(uid, {
                    displayName: name,
                    preferences: {
                        emailNotifications: true,
                        darkMode: false,
                    },
                }),
                saveUserStreak(uid, {
                    activeDays: [],
                    totalSolved: 0,
                    currentStreak: 0,
                    longestStreak: 0,
                }),
                saveUserAnalytics(uid, {
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
                }),
                setDoc(doc(db, 'users', uid, 'rating', 'summary'), {
                    currentRating: 0,
                    maxRating: 0,
                    contestHistory: [],
                    streak: 0,
                    volatility: 1.15,
                    contestsPlayed: 0,
                    averageRank: null,
                    lastRatingChange: 0,
                }, { merge: true }),
            ]);
            return { success: true };
        } catch (error) {
            return { success: false, error: error.message };
        }
    };

    const logout = async () => {
        try {
            await signOut(auth);
        } catch (error) {
            console.error("Error signing out:", error);
        }
    };

    const updateProfile = async (updates) => {
        if (!user) return;
        try {
            const mergedPreferences = {
                ...(user.preferences || {}),
                ...(updates.preferences || {}),
            };
            const normalizedDisplayName = updates.displayName || updates.name || user.displayName || user.name || 'User';
            const userDocUpdates = {
                ...(updates.name ? { name: updates.name } : {}),
            };
            const updated = {
                ...user,
                ...updates,
                displayName: normalizedDisplayName,
                preferences: mergedPreferences,
                name: updates.name || user.name,
            };

            if (Object.keys(userDocUpdates).length > 0) {
                await setDoc(doc(db, 'users', user.id), userDocUpdates, { merge: true });
            }

            await saveUserProfile(user.id, {
                displayName: normalizedDisplayName,
                preferences: mergedPreferences,
            });
            setUser(updated);
        } catch (error) {
            console.error("Error updating profile:", error);
        }
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                isAuthenticated: !!user,
                isLoading,
                login,
                signup,
                logout,
                updateProfile,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}

export default AuthContext;
