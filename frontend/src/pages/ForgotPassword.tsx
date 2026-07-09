import { useState } from 'react';
import { Link } from 'react-router-dom';
import { LayoutDashboard, Mail, ArrowLeft } from 'lucide-react';
import axios from 'axios';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await axios.post('/api/auth/forgot-password', { email });
      setEmailSent(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'invio');
    } finally {
      setIsLoading(false);
    }
  };

  if (emailSent) {
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
              Se esiste un account con l'email <span className="font-medium">{email}</span>, 
              riceverai un link per reimpostare la password.
            </p>
            <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-cyan-800">
                Il link scade tra 1 ora. Controlla anche la cartella spam.
              </p>
            </div>
            <Link
              to="/login"
              className="text-[#00D4FF] hover:underline font-medium"
            >
              Torna al login
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
            <h1 className="text-2xl font-bold text-[#0F1D32]">Recupera Password</h1>
            <p className="text-gray-500 mt-2">Inserisci la tua email per reimpostare la password</p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none transition"
                placeholder="La tua email"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-[#00D4FF] text-white py-2.5 rounded-lg font-medium hover:bg-[#00B4D8] transition disabled:opacity-50"
            >
              {isLoading ? 'Invio in corso...' : 'Invia Link di Reset'}
            </button>
          </form>

          <p className="mt-6 text-center">
            <Link to="/login" className="text-[#00D4FF] hover:underline font-medium inline-flex items-center gap-1">
              <ArrowLeft size={16} />
              Torna al login
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
