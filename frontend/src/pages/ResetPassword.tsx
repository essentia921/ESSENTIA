import { useState, useEffect } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { LayoutDashboard, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import axios from 'axios';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<'form' | 'success' | 'error'>('form');
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);

  const token = searchParams.get('token');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setError('Token di reset mancante');
      setTokenValid(false);
    } else {
      setTokenValid(true);
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Le password non coincidono');
      return;
    }

    if (password.length < 6) {
      setError('La password deve essere di almeno 6 caratteri');
      return;
    }

    setIsLoading(true);

    try {
      await axios.post('/api/auth/reset-password', {
        token,
        new_password: password
      });
      setStatus('success');
      setTimeout(() => navigate('/login'), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nel reset della password');
      if (err.response?.status === 400) {
        setStatus('error');
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (tokenValid === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0F1D32] px-4">
        <Loader2 size={48} className="text-[#00D4FF] animate-spin" />
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0F1D32] px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                <CheckCircle size={40} className="text-green-600" />
              </div>
            </div>
            <h1 className="text-xl font-bold text-[#0F1D32] mb-2">Password Reimpostata!</h1>
            <p className="text-gray-600 mb-6">La tua password è stata cambiata con successo.</p>
            <p className="text-sm text-gray-500">Verrai reindirizzato al login...</p>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'error' && !tokenValid) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0F1D32] px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center">
                <XCircle size={40} className="text-red-600" />
              </div>
            </div>
            <h1 className="text-xl font-bold text-[#0F1D32] mb-2">Link Non Valido</h1>
            <p className="text-gray-600 mb-6">{error}</p>
            <Link
              to="/forgot-password"
              className="block w-full bg-[#00D4FF] text-white py-2.5 rounded-lg font-medium hover:bg-[#00B4D8] transition"
            >
              Richiedi nuovo link
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0F1D32] px-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="w-14 h-14 bg-[#00D4FF] rounded-xl flex items-center justify-center">
                <LayoutDashboard size={28} className="text-[#0F1D32]" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-[#0F1D32]">Nuova Password</h1>
            <p className="text-gray-500 mt-2">Inserisci la tua nuova password</p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Nuova Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none transition"
                placeholder="Minimo 6 caratteri"
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                Conferma Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none transition"
                placeholder="Ripeti la password"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-[#00D4FF] text-white py-2.5 rounded-lg font-medium hover:bg-[#00B4D8] transition disabled:opacity-50"
            >
              {isLoading ? 'Salvataggio...' : 'Reimposta Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
