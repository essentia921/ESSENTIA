import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Mail } from 'lucide-react';
import axios from 'axios';

export default function Register() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [registrationComplete, setRegistrationComplete] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState('');
  const [triggerPasswordSave, setTriggerPasswordSave] = useState(false);
  const { loginWithGoogle } = useAuth();
  const hiddenFormRef = useRef<HTMLFormElement>(null);

  // Submit hidden form to trigger password save after registration
  useEffect(() => {
    if (triggerPasswordSave && hiddenFormRef.current) {
      hiddenFormRef.current.submit();
    }
  }, [triggerPasswordSave]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await axios.post('/api/auth/register', {
        email,
        password,
        full_name: fullName || undefined
      });
      
      setRegisteredEmail(response.data.email);
      setTriggerPasswordSave(true);
      setTimeout(() => setRegistrationComplete(true), 100);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registrazione fallita');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendEmail = async () => {
    setIsLoading(true);
    try {
      await axios.post('/api/auth/resend-verification', null, {
        params: { email: registeredEmail }
      });
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'invio');
    } finally {
      setIsLoading(false);
    }
  };

  if (registrationComplete) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0F1D32] px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                <Mail size={32} className="text-green-600" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-[#0F1D32] mb-2">Controlla la tua email</h1>
            <p className="text-gray-600 mb-6">
              Abbiamo inviato un link di verifica a<br />
              <span className="font-medium text-[#0F1D32]">{registeredEmail}</span>
            </p>
            <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-cyan-800">
                Clicca sul link nell'email per attivare il tuo account. Il link scade tra 24 ore.
              </p>
            </div>
            <button
              onClick={handleResendEmail}
              disabled={isLoading}
              className="text-[#00D4FF] hover:underline font-medium disabled:opacity-50"
            >
              {isLoading ? 'Invio in corso...' : 'Non hai ricevuto l\'email? Invia di nuovo'}
            </button>
            <p className="mt-6 text-sm text-gray-600">
              <Link to="/login" className="text-[#00D4FF] hover:underline font-medium">
                Torna al login
              </Link>
            </p>
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
              <img src="/logo-login.png" alt="Logo" className="w-14 h-14 rounded-xl object-cover" loading="eager" decoding="async" width={56} height={56} />
            </div>
            <h1 className="text-2xl font-bold text-[#0F1D32]">Essentia Suite</h1>
            <p className="text-gray-500 mt-2">Crea il tuo account</p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-gray-700 mb-1">
                Nome completo
              </label>
              <input
                id="fullName"
                name="name"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none transition"
                placeholder="Mario Rossi"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none transition"
                placeholder="La tua email"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none transition"
                placeholder="Minimo 6 caratteri"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-[#00D4FF] text-white py-2.5 rounded-lg font-medium hover:bg-[#00B4D8] transition disabled:opacity-50"
            >
              {isLoading ? 'Registrazione...' : 'Registrati'}
            </button>
          </form>

          <div className="my-6 flex items-center">
            <div className="flex-1 border-t border-gray-200"></div>
            <span className="px-4 text-sm text-gray-500">oppure</span>
            <div className="flex-1 border-t border-gray-200"></div>
          </div>

          <button
            onClick={loginWithGoogle}
            className="w-full flex items-center justify-center gap-3 bg-white border border-gray-300 text-gray-700 py-2.5 rounded-lg font-medium hover:bg-gray-50 transition"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="currentColor"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="currentColor"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="currentColor"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Registrati con Google
          </button>

          <p className="mt-6 text-center text-sm text-gray-600">
            Hai già un account?{' '}
            <Link to="/login" className="text-[#00D4FF] hover:underline font-medium">
              Accedi
            </Link>
          </p>
        </div>
      </div>
      
      {/* Hidden iframe and form to trigger browser password save */}
      <iframe name="hidden-register-frame" style={{ display: 'none' }} title="register frame" />
      <form
        ref={hiddenFormRef}
        action="about:blank"
        method="POST"
        target="hidden-register-frame"
        style={{ display: 'none' }}
      >
        <input type="email" name="email" autoComplete="email" value={email} readOnly />
        <input type="password" name="password" autoComplete="new-password" value={password} readOnly />
      </form>
    </div>
  );
}
