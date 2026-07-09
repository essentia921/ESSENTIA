import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const processedRef = useRef(false);

  useEffect(() => {
    if (processedRef.current) return;
    
    const token = searchParams.get('token');
    
    if (token) {
      processedRef.current = true;
      localStorage.removeItem('selectedAccount');
      localStorage.removeItem('selectedProfiles');
      localStorage.removeItem('selectedProfile');
      localStorage.removeItem('selectedCampaigns');
      localStorage.setItem('token', token);
      refreshUser().then(() => {
        navigate('/accounts');
      });
    } else {
      navigate('/login');
    }
  }, [searchParams, navigate, refreshUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">Autenticazione in corso...</p>
      </div>
    </div>
  );
}
