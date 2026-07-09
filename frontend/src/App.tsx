import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { AuthProvider } from './context/AuthContext';
import { initGA, trackPageView } from './lib/analytics';
import { SelectionProvider } from './context/SelectionContext';
import ProtectedRoute from './components/ProtectedRoute';
import LandingPage from './pages/LandingPage';
import Login from './pages/Login';
import Register from './pages/Register';
import AuthCallback from './pages/AuthCallback';
import Pricing from './pages/Pricing';
import Accounts from './pages/Accounts';
import Profiles from './pages/Profiles';
import Settings from './pages/Settings';
import Tokens from './pages/Tokens';
import CampaignLauncher from './pages/CampaignLauncher';
import AutopilotDev from './pages/AutopilotDev';
import SBTest from './pages/SBTest';
import Onboarding from './pages/Onboarding';
import OnboardingSuccess from './pages/OnboardingSuccess';
import ExtractorNew from './pages/ExtractorNew';
import ExtractorAsins from './pages/ExtractorAsins';
import ExtractorKeywords from './pages/ExtractorKeywords';
import ExtractorHistory from './pages/ExtractorHistory';
import ExtractorLogs from './pages/ExtractorLogs';
import ExtractorStatus from './pages/ExtractorStatus';
import VerifyEmail from './pages/VerifyEmail';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import Admin from './pages/Admin';
import Blog from './pages/Blog';
import BlogPost from './pages/BlogPost';
import AdminBlog from './pages/AdminBlog';
import AuthorPage from './pages/AuthorPage';
import Dashboard from './pages/Dashboard';
import AcosCalculator from './pages/AcosCalculator';
import CampaignAnalyzer from './pages/CampaignAnalyzer';
import PurchaseSuccess from './pages/PurchaseSuccess';

const queryClient = new QueryClient();

initGA();

function RouteTracker() {
  const location = useLocation();
  useEffect(() => {
    if (location.pathname.startsWith('/blog')) return;
    trackPageView(location.pathname + location.search);
  }, [location]);
  return null;
}

function App() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = params.get('ref');
    if (ref) {
      localStorage.setItem('affiliate_ref', ref.toUpperCase().trim());
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <SelectionProvider>
          <BrowserRouter>
            <RouteTracker />
            <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/onboarding/:token" element={<Onboarding />} />
            <Route path="/onboarding/success" element={<OnboardingSuccess />} />
            <Route path="/" element={<LandingPage />} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/accounts" element={<ProtectedRoute><Accounts /></ProtectedRoute>} />
            <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
            <Route path="/profiles" element={<ProtectedRoute requireSubscription><Profiles /></ProtectedRoute>} />
            <Route path="/campaign-launcher" element={<ProtectedRoute requireSubscription><CampaignLauncher /></ProtectedRoute>} />
            <Route path="/autopilot" element={<ProtectedRoute requireSubscription><AutopilotDev /></ProtectedRoute>} />
            <Route path="/autopilot-dev" element={<Navigate to="/autopilot" replace />} />
            <Route path="/sb-test" element={<ProtectedRoute><SBTest /></ProtectedRoute>} />
            <Route path="/flash-agent" element={<Navigate to="/autopilot" replace />} />
            <Route path="/tokens" element={<ProtectedRoute><Tokens /></ProtectedRoute>} />
            
            <Route path="/extractor" element={<Navigate to="/extractor/new" replace />} />
            <Route path="/extractor/new" element={<ProtectedRoute requireSubscription><ExtractorNew /></ProtectedRoute>} />
            <Route path="/extractor/asins" element={<ProtectedRoute requireSubscription><ExtractorAsins /></ProtectedRoute>} />
            <Route path="/extractor/keywords" element={<ProtectedRoute requireSubscription><ExtractorKeywords /></ProtectedRoute>} />
            <Route path="/extractor/history" element={<ProtectedRoute requireSubscription><ExtractorHistory /></ProtectedRoute>} />
            <Route path="/extractor/logs" element={<ProtectedRoute requireSubscription><ExtractorLogs /></ProtectedRoute>} />
            <Route path="/extractor/status" element={<ProtectedRoute requireSubscription><ExtractorStatus /></ProtectedRoute>} />
            
            <Route path="/admin" element={<ProtectedRoute><Admin /></ProtectedRoute>} />
            <Route path="/adminblog" element={<AdminBlog />} />
            <Route path="/blog" element={<Blog />} />
            <Route path="/blog/:slug" element={<BlogPost />} />
            <Route path="/author" element={<AuthorPage />} />
            <Route path="/tool" element={<Navigate to="/acos-calculator" replace />} />
            <Route path="/acos-calculator" element={<AcosCalculator />} />
            <Route path="/campaign-analyzer" element={<CampaignAnalyzer />} />
            <Route path="/purchase-success" element={<PurchaseSuccess />} />
            <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </SelectionProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
