import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Bell, Brain, Flame, LayoutDashboard, LogOut, Menu, MessageSquare, Trophy, User, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { listUserNotifications, markNotificationRead } from '../services/classroomData';

export default function Navbar() {
    const { user, logout } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [notificationsOpen, setNotificationsOpen] = useState(false);
    const [notifications, setNotifications] = useState([]);

    useEffect(() => {
        let isMounted = true;
        const loadNotifications = async () => {
            if (!user?.id) return;
            try {
                const items = await listUserNotifications(user.id, 12);
                if (isMounted) setNotifications(items);
            } catch (error) {
                console.error('Error loading notifications:', error);
            }
        };
        loadNotifications();
        const intervalId = window.setInterval(loadNotifications, 20000);
        return () => {
            isMounted = false;
            window.clearInterval(intervalId);
        };
    }, [location.pathname, user?.id]);

    const navItems = [
        { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
        { path: '/chat', label: 'Ask a Question', icon: MessageSquare },
        { path: '/quiz', label: 'Adaptive Quiz', icon: Brain },
        { path: '/contests', label: 'Contests', icon: Trophy },
        { path: '/streak', label: 'Streak', icon: Flame },
        { path: '/profile', label: 'Profile', icon: User },
    ];

    const unreadCount = notifications.filter((item) => !item.read).length;
    const isActive = (path) => location.pathname === path;

    const handleLogout = async () => {
        await logout();
        navigate('/');
    };

    const handleNotificationClick = async (notification) => {
        if (!user?.id) return;
        try {
            await markNotificationRead(user.id, notification.id);
            setNotifications((current) => current.map((item) => (item.id === notification.id ? { ...item, read: true } : item)));
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
        setNotificationsOpen(false);
        navigate(notification.targetPath || '/dashboard');
    };

    return (
        <nav className="bg-white border-b border-gray-100 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                    <Link to="/dashboard" className="flex items-center gap-2 group">
                        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center group-hover:bg-blue-700 transition-colors">
                            <span className="text-white font-bold text-sm">M</span>
                        </div>
                        <span className="text-lg font-bold text-gray-900 tracking-tight">Math<span className="text-blue-600">Mend</span></span>
                    </Link>

                    <div className="hidden md:flex items-center gap-1">
                        {navItems.map((item) => {
                            const Icon = item.icon;
                            return (
                                <Link key={item.path} to={item.path} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${isActive(item.path) ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}>
                                    <Icon size={16} />
                                    {item.label}
                                </Link>
                            );
                        })}
                    </div>

                    <div className="hidden md:flex items-center gap-3">
                        <div className="relative">
                            <button onClick={() => setNotificationsOpen((open) => !open)} className="relative p-2 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 transition-colors" title="Notifications">
                                <Bell size={17} className="text-gray-600" />
                                {unreadCount > 0 && <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white flex items-center justify-center">{unreadCount > 9 ? '9+' : unreadCount}</span>}
                            </button>
                            {notificationsOpen && (
                                <div className="absolute right-0 top-12 w-80 rounded-2xl border border-gray-100 bg-white shadow-xl shadow-gray-200/50 overflow-hidden">
                                    <div className="px-4 py-3 border-b border-gray-100">
                                        <p className="text-sm font-semibold text-gray-900">Notifications</p>
                                        <p className="text-xs text-gray-500 mt-1">Quizzes, contests, and classroom alerts</p>
                                    </div>
                                    <div className="max-h-96 overflow-y-auto">
                                        {notifications.length === 0 ? (
                                            <div className="px-4 py-8 text-center">
                                                <Bell size={20} className="mx-auto text-gray-300 mb-2" />
                                                <p className="text-sm text-gray-500">No notifications yet</p>
                                            </div>
                                        ) : notifications.map((notification) => (
                                            <button key={notification.id} onClick={() => handleNotificationClick(notification)} className={`w-full px-4 py-3 text-left border-b border-gray-50 hover:bg-gray-50 transition-colors ${notification.read ? 'bg-white' : 'bg-blue-50/60'}`}>
                                                <div className="flex items-start justify-between gap-3">
                                                    <div>
                                                        <p className="text-sm font-medium text-gray-900">{notification.title}</p>
                                                        <p className="text-xs text-gray-500 mt-1 leading-relaxed">{notification.body}</p>
                                                        <p className="text-[11px] text-gray-400 mt-2">{notification.teacherName ? `From ${notification.teacherName}` : 'Classroom update'}</p>
                                                    </div>
                                                    {!notification.read && <span className="mt-1 w-2.5 h-2.5 rounded-full bg-blue-500 flex-shrink-0" />}
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                                <span className="text-blue-700 font-semibold text-xs">{(user?.displayName || user?.name || 'U').split(' ').map((n) => n[0]).join('').toUpperCase() || 'U'}</span>
                            </div>
                            <span className="text-sm font-medium text-gray-700">{user?.displayName || user?.name}</span>
                        </div>
                        <button onClick={handleLogout} className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all duration-200" title="Logout">
                            <LogOut size={18} />
                        </button>
                    </div>

                    <button onClick={() => setMobileOpen((open) => !open)} className="md:hidden p-2 text-gray-600 hover:bg-gray-100 rounded-lg">
                        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
                    </button>
                </div>
            </div>

            {mobileOpen && (
                <div className="md:hidden border-t border-gray-100 bg-white">
                    <div className="px-4 py-3 space-y-1">
                        {navItems.map((item) => {
                            const Icon = item.icon;
                            return (
                                <Link key={item.path} to={item.path} onClick={() => setMobileOpen(false)} className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive(item.path) ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}>
                                    <Icon size={18} />
                                    {item.label}
                                </Link>
                            );
                        })}
                        <hr className="my-2 border-gray-100" />
                        <button onClick={handleLogout} className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-red-500 hover:bg-red-50 w-full transition-colors">
                            <LogOut size={18} />
                            Sign out
                        </button>
                    </div>
                </div>
            )}
        </nav>
    );
}
