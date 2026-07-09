import { useEffect, useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { CheckCircle, XCircle, Loader2, LayoutDashboard } from 'lucide-react';
import axios from 'axios';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    
    if (!token) {
      setStatus('error');
      setMessage('Token di verifica mancante');
      return;
    }

    const verifyEmail = async () => {
      try {
        const response = await axios.get(`/api/auth/verify-email?token=${token}`);
        if (response.status === 307 || response.status === 200) {
          setStatus('success');
          setMessage('Email verificata con successo!');
          setTimeout(() => {
            navigate('/accounts');
          }, 2000);
        }
      } catch (err: any) {
        setStatus('error');
        setMessage(err.response?.data?.detail || 'Errore nella verifica dell\'email');
      }
    };

    verifyEmail();
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0F1D32] px-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
          <div className="flex justify-center mb-4">
            <div className="w-14 h-14 bg-[#00D4FF] rounded-xl flex items-center justify-center">
              <LayoutDashboard size={28} className="text-[#0F1D32]" />
            </div>
          </div>

          {status === 'loading' && (
            <>
              <div className="flex justify-center mb-6">
                <Loader2 size={48} className="text-[#00D4FF] animate-spin" />
              </div>
              <h1 className="text-xl font-bold text-[#0F1D32] mb-2">Verifica in corso...</h1>
              <p className="text-gray-600">Stiamo verificando la tua email</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="flex justify-center mb-6">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                  <CheckCircle size={40} className="text-green-600" />
                </div>
              </div>
              <h1 className="text-xl font-bold text-[#0F1D32] mb-2">Email Verificata!</h1>
              <p className="text-gray-600 mb-6">{message}</p>
              <p className="text-sm text-gray-500">Verrai reindirizzato automaticamente...</p>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="flex justify-center mb-6">
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center">
                  <XCircle size={40} className="text-red-600" />
                </div>
              </div>
              <h1 className="text-xl font-bold text-[#0F1D32] mb-2">Verifica Fallita</h1>
              <p className="text-gray-600 mb-6">{message}</p>
              <div className="space-y-3">
                <Link
                  to="/register"
                  className="block w-full bg-[#00D4FF] text-white py-2.5 rounded-lg font-medium hover:bg-[#00B4D8] transition"
                >
                  Registrati di nuovo
                </Link>
                <Link
                  to="/login"
                  className="block text-[#00D4FF] hover:underline font-medium"
                >
                  Torna al login
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
