import { type ReactNode, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSelection } from '../context/SelectionContext';
import { 
  Users, 
  Globe,
  LogOut,
  Lock,
  Rocket,
  Bot,
  Sparkles,
  Search,
  History,
  Database,
  PlusCircle,
  X,
  Settings,
} from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { user, isSubscribed, logout, token } = useAuth();
  const { selectedAccount, selectedProfiles, clearSelections } = useSelection();
  const location = useLocation();
  const navigate = useNavigate();
  const validatedRef = useRef(false);

  useEffect(() => {
    validatedRef.current = false;
  }, [user?.id]);

  useEffect(() => {
    if (!user || !token || validatedRef.current) return;
    
    const validateCachedAccount = async () => {
      if (!selectedAccount) {
        validatedRef.current = true;
        return;
      }
      
      try {
        const response = await fetch('/api/accounts/', {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (response.ok) {
          const accounts = await response.json();
          const accountExists = accounts.some((acc: { id: number }) => acc.id === selectedAccount.id);
          if (!accountExists) {
            clearSelections();
          }
        }
        validatedRef.current = true;
      } catch (error) {
        console.error('Failed to validate cached account:', error);
      }
    };
    
    validateCachedAccount();
  }, [user, token, selectedAccount, clearSelections]);

  const mainMenuItems = [
    { path: '/accounts', label: 'Accounts', icon: Users, requiresSubscription: false },
    { path: '/profiles', label: 'Marketplace', icon: Globe, requiresSubscription: false },
    { path: '/autopilot', label: 'Automation', icon: Bot, requiresSubscription: true },
  ];

  const extractorMenuItems = [
    { path: '/campaign-launcher', label: 'Campaign Launchers', icon: Rocket, requiresSubscription: true },
    { path: '/extractor/new', label: 'Search', icon: PlusCircle, requiresSubscription: true },
    { path: '/extractor/asins', label: 'ASINs', icon: Database, requiresSubscription: true },
    { path: '/extractor/keywords', label: 'Keywords', icon: Search, requiresSubscription: true },
    { path: '/extractor/history', label: 'Storage', icon: History, requiresSubscription: true },
  ];

  const handleLogout = () => {
    clearSelections();
    logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen bg-[#f5f5f5]">
      <aside className="w-72 bg-[#0F1D32] text-white flex flex-col">
        <div className="p-5 border-b border-[#1E3254]">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Logo" className="w-11 h-11 rounded-xl object-cover" loading="eager" decoding="async" width={44} height={44} />
            <div>
              <h1 className="text-lg font-bold text-white">
                Essentia Suite
              </h1>
              <p className="text-xs text-gray-400">Advertising Automation</p>
            </div>
          </div>
        </div>

        {user && (
          <div className="px-4 py-3 border-b border-[#1E3254]">
            <div className="p-3 bg-[#162844] rounded-lg">
              <p className="text-sm font-medium text-white truncate">{user.email}</p>
              <p className="text-xs mt-1">
                {isSubscribed ? (
                  <span className="text-green-400 flex items-center gap-1">
                    <Sparkles size={12} /> Pro Plan Active
                  </span>
                ) : (
                  <span className="text-[#00D4FF]">Free Plan</span>
                )}
              </p>
            </div>
          </div>
        )}

        {(selectedAccount || selectedProfiles.length > 0) && (
          <div className="px-4 py-3 border-b border-[#1E3254]">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-gray-500 uppercase tracking-wider">Active Selection</p>
              <button
                onClick={clearSelections}
                className="text-gray-500 hover:text-red-400 transition p-1 rounded hover:bg-[#1E3254]"
                title="Clear Selection"
              >
                <X size={14} />
              </button>
            </div>
            {selectedAccount && (
              <div className="flex items-center gap-2 text-sm">
                <Users size={14} className="text-[#00D4FF]" />
                <span className="text-gray-300 truncate">{selectedAccount.name}</span>
              </div>
            )}
            {selectedProfiles.map((profile) => (
              <div key={profile.profileId} className="flex items-center gap-2 text-sm mt-1">
                <Globe size={14} className="text-green-400" />
                <span className="text-gray-300">{profile.countryCode}</span>
              </div>
            ))}
          </div>
        )}

        <nav className="flex-1 p-4 overflow-y-auto">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-3 px-3">NEXUS ADS MANAGER</p>
          <ul className="space-y-1">
            {mainMenuItems.map((item) => {
              const isActive = location.pathname === item.path;
              const isLocked = item.requiresSubscription && !isSubscribed;
              const Icon = item.icon;

              return (
                <li key={item.path}>
                  <Link
                    to={isLocked ? '/pricing' : item.path}
                    className={`group flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-200 ${
                      isActive
                        ? 'bg-[#162844] text-white'
                        : 'text-gray-400 hover:text-white hover:bg-[#162844]/50'
                    }`}
                  >
                    <Icon size={20} className={isActive ? 'text-[#00D4FF]' : 'text-gray-500 group-hover:text-[#00D4FF]'} />
                    <span className="font-medium">{item.label}</span>
                    {isLocked && (
                      <Lock size={14} className="ml-auto text-[#00D4FF]" />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>

          <p className="text-xs text-gray-500 uppercase tracking-wider mt-6 mb-3 px-3">EXPLORA SCOUTER</p>
          <ul className="space-y-1">
            {extractorMenuItems.map((item) => {
              const isActive = location.pathname === item.path;
              const isLocked = item.requiresSubscription && !isSubscribed;
              const Icon = item.icon;

              return (
                <li key={item.path}>
                  <Link
                    to={isLocked ? '/pricing' : item.path}
                    className={`group flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-200 ${
                      isActive
                        ? 'bg-[#162844] text-white'
                        : 'text-gray-400 hover:text-white hover:bg-[#162844]/50'
                    }`}
                  >
                    <Icon size={20} className={isActive ? 'text-[#00D4FF]' : 'text-gray-500 group-hover:text-[#00D4FF]'} />
                    <span className="font-medium">{item.label}</span>
                    {isLocked && (
                      <Lock size={14} className="ml-auto text-[#00D4FF]" />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="p-4 border-t border-[#1E3254]">
          <div className="mb-3 p-3 bg-gradient-to-r from-[#00D4FF]/20 to-[#00D4FF]/10 rounded-lg border border-[#00D4FF]/30">
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-[#00D4FF]" />
              <span className="text-sm font-semibold text-[#00D4FF]">Pro Version</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">Unlimited Features</p>
          </div>
          <Link
            to="/settings"
            className={`flex items-center gap-3 px-4 py-2.5 w-full rounded-lg transition-all duration-200 ${
              location.pathname === '/settings'
                ? 'bg-[#162844] text-white'
                : 'text-gray-400 hover:text-white hover:bg-[#162844]/50'
            }`}
          >
            <Settings size={20} className={location.pathname === '/settings' ? 'text-[#00D4FF]' : 'text-gray-500'} />
            <span className="font-medium">Settings</span>
          </Link>
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-2.5 w-full rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-all duration-200"
          >
            <LogOut size={20} />
            <span className="font-medium">Logout</span>
          </button>
        </div>
      </aside>

      <main className="flex-1 bg-[#f5f5f5] overflow-auto">
        <div className="p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
