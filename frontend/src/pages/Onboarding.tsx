import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../lib/api';

export default function Onboarding() {
  const { token } = useParams<{ token: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clientName, setClientName] = useState<string>('');
  const [region, setRegion] = useState<string>('eu');
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('Link non valido');
      setLoading(false);
      return;
    }

    api.get(`/api/auth/onboarding/${token}`)
      .then((response) => {
        setClientName(response.data.client_name);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.response?.data?.detail || 'Link non valido o scaduto');
        setLoading(false);
      });
  }, [token]);

  const handleConnect = () => {
    setConnecting(true);
    window.location.href = `/api/auth/onboarding/${token}/start?region=${region}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-blue-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-blue-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Link non valido</h1>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-blue-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-lg w-full">
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-cyan-400 to-cyan-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Collega il tuo Account Amazon Ads</h1>
          <p className="text-gray-600">
            Stai collegando l'account <span className="font-semibold text-gray-900">{clientName}</span>
          </p>
        </div>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Seleziona la regione Amazon
            </label>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[#00D4FF] focus:border-transparent transition-all"
            >
              <option value="eu">Europa (UK, DE, FR, IT, ES)</option>
              <option value="na">Nord America (US, CA, MX, BR)</option>
              <option value="fe">Far East (JP, AU, SG)</option>
            </select>
          </div>

          <div className="bg-cyan-50 rounded-xl p-4">
            <h3 className="font-medium text-[#0F1D32] mb-2">Cosa succede dopo?</h3>
            <ul className="text-sm text-[#0F1D32] space-y-2">
              <li className="flex items-start gap-2">
                <svg className="w-5 h-5 text-[#00D4FF] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Verrai reindirizzato ad Amazon per autorizzare l'accesso
              </li>
              <li className="flex items-start gap-2">
                <svg className="w-5 h-5 text-[#00D4FF] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Dopo l'autorizzazione, il tuo account sarà collegato automaticamente
              </li>
              <li className="flex items-start gap-2">
                <svg className="w-5 h-5 text-[#00D4FF] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                I tuoi dati sono al sicuro e protetti
              </li>
            </ul>
          </div>

          <button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full py-4 bg-gradient-to-r from-cyan-500 to-cyan-600 text-white font-semibold rounded-xl hover:from-cyan-600 hover:to-cyan-700 transition-all shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {connecting ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                Reindirizzamento...
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                Collega con Amazon
              </>
            )}
          </button>
        </div>

        <p className="text-xs text-gray-500 text-center mt-6">
          Cliccando su "Collega con Amazon", accetti di condividere i tuoi dati Amazon Ads
          con il gestore del tuo account pubblicitario.
        </p>
      </div>
    </div>
  );
}
