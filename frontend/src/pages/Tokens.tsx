import { useState, useEffect } from 'react';
import api from '../lib/api';
import { Key, Download, Check, AlertCircle, Lock } from 'lucide-react';
import Layout from '../components/Layout';

interface AccountToken {
  id: number;
  name: string;
  has_token: boolean;
  token_expires_at: string | null;
}

export default function Tokens() {
  const [accounts, setAccounts] = useState<AccountToken[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      const response = await api.get('/tokens/accounts');
      setAccounts(response.data);
    } catch (error) {
      console.error('Failed to load accounts:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = async () => {
    setError(null);
    
    if (password.length < 4) {
      setError('La password deve essere di almeno 4 caratteri');
      return;
    }
    
    if (password !== confirmPassword) {
      setError('Le password non corrispondono');
      return;
    }

    setIsExporting(true);
    try {
      const response = await api.post('/tokens/export', { password }, {
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data], { type: 'application/octet-stream' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'amazon_tokens_encrypted.bin';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      setSuccess(true);
      setPassword('');
      setConfirmPassword('');
      setTimeout(() => setSuccess(false), 5000);
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Errore durante l\'esportazione');
    } finally {
      setIsExporting(false);
    }
  };

  const accountsWithTokens = accounts.filter(a => a.has_token);

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[#0F1D32]">Esporta Token</h1>
        <p className="text-gray-600 mt-1">
          Esporta i token degli account Amazon in un file criptato
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-[#0F1D32]">Account con Token</h2>
            <p className="text-sm text-gray-500 mt-1">Token disponibili per l'esportazione</p>
          </div>

          {isLoading ? (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            </div>
          ) : accountsWithTokens.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <Key className="mx-auto mb-3 text-slate-300" size={48} />
              <p>Nessun account con token collegato</p>
              <p className="text-sm mt-1">Collega un account Amazon per generare i token</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200">
              {accountsWithTokens.map((account) => (
                <div key={account.id} className="px-6 py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                      <Key className="text-green-600" size={20} />
                    </div>
                    <div>
                      <p className="font-medium text-[#0F1D32]">{account.name}</p>
                      <p className="text-sm text-gray-500">
                        {account.token_expires_at ? (
                          `Scade: ${new Date(account.token_expires_at).toLocaleString('it-IT')}`
                        ) : (
                          'Token attivo'
                        )}
                      </p>
                    </div>
                  </div>
                  <Check className="text-green-500" size={20} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
              <Lock className="text-[#00D4FF]" size={24} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-[#0F1D32]">Export Criptato</h2>
              <p className="text-sm text-gray-500">Proteggi i tuoi token con una password</p>
            </div>
          </div>

          {success && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6 flex items-center gap-3">
              <Check className="text-green-600" size={20} />
              <span className="text-green-800">File esportato con successo!</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center gap-3">
              <AlertCircle className="text-red-600" size={20} />
              <span className="text-red-800">{error}</span>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Password di criptazione
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Inserisci una password sicura"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Conferma password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Ripeti la password"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
              />
            </div>

            <button
              onClick={handleExport}
              disabled={isExporting || accountsWithTokens.length === 0 || !password || !confirmPassword}
              className="w-full py-3 bg-[#00D4FF] text-white font-semibold rounded-lg hover:bg-[#00A8CC] transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isExporting ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                  Esportazione...
                </>
              ) : (
                <>
                  <Download size={20} />
                  Scarica Token Criptati
                </>
              )}
            </button>
          </div>

          <div className="mt-6 p-4 bg-cyan-50 border border-cyan-200 rounded-lg">
            <p className="text-sm text-cyan-800">
              <strong>Importante:</strong> Conserva la password in un luogo sicuro. 
              Senza di essa non potrai decriptare il file. Il file contiene 
              access_token e refresh_token per tutti gli account collegati.
            </p>
          </div>
        </div>
      </div>
    </Layout>
  );
}
