import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

// Mock users database
const MOCK_USERS = [
    { id: 1, email: 'demo@mathmend.com', password: 'demo123', name: 'Alex Johnson', avatar: null },
    { id: 2, email: 'student@mathmend.com', password: 'student123', name: 'Sam Rivera', avatar: null },
];

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    // Check for existing session on mount
    useEffect(() => {
        const stored = localStorage.getItem('mathmend_user');
        if (stored) {
            try {
                setUser(JSON.parse(stored));
            } catch {
                localStorage.removeItem('mathmend_user');
            }
        }
        setIsLoading(false);
    }, []);

    const login = (email, password) => {
        const found = MOCK_USERS.find(
            (u) => u.email.toLowerCase() === email.toLowerCase() && u.password === password
        );
        if (found) {
            const userData = { id: found.id, email: found.email, name: found.name };
            setUser(userData);
            localStorage.setItem('mathmend_user', JSON.stringify(userData));
            return { success: true };
        }
        return { success: false, error: 'Invalid email or password' };
    };

    const signup = (name, email, password) => {
        const exists = MOCK_USERS.find((u) => u.email.toLowerCase() === email.toLowerCase());
        if (exists) {
            return { success: false, error: 'Email already registered' };
        }
        const newUser = { id: Date.now(), email, name };
        MOCK_USERS.push({ ...newUser, password });
        setUser(newUser);
        localStorage.setItem('mathmend_user', JSON.stringify(newUser));
        return { success: true };
    };

    const logout = () => {
        setUser(null);
        localStorage.removeItem('mathmend_user');
    };

    const updateProfile = (updates) => {
        if (!user) return;
        const updated = { ...user, ...updates };
        setUser(updated);
        localStorage.setItem('mathmend_user', JSON.stringify(updated));
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
