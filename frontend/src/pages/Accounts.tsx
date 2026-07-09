import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api, { accountsAPI } from '../lib/api';
import { Plus, Trash2, Link as LinkIcon, Check, ChevronRight, Copy, X, Pencil, RefreshCw } from 'lucide-react';
import Layout from '../components/Layout';
import { useSelection } from '../context/SelectionContext';

interface Account {
  id: number;
  name: string;
  has_token: boolean;
}


export default function Accounts() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [newAccountName, setNewAccountName] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const { selectedAccount, setSelectedAccount } = useSelection();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  const [copiedAccountId, setCopiedAccountId] = useState<number | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showRegionModal, setShowRegionModal] = useState(false);
  const [pendingAccountId, setPendingAccountId] = useState<number | null>(null);
  const [selectedRegion, setSelectedRegion] = useState('na');
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [renameAccountId, setRenameAccountId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);

  useEffect(() => {
    loadAccounts();
    
    const connected = searchParams.get('connected');
    if (connected) {
      setSuccessMessage(`Account #${connected} collegato con successo!`);
      setTimeout(() => setSuccessMessage(null), 5000);
    }
  }, [searchParams]);

  const loadAccounts = async () => {
    try {
      const response = await accountsAPI.getAll();
      const accountsList = Array.isArray(response.data) ? response.data : [];
      setAccounts(accountsList);
      
      // Clear selection if selected account no longer exists
      if (selectedAccount && !accountsList.find((a: Account) => a.id === selectedAccount.id)) {
        setSelectedAccount(null);
      }
    } catch (error) {
      console.error('Failed to load accounts:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const copyAccountLink = async (accountId: number, region: string = 'na') => {
    try {
      const response = await api.post(`/auth/amazon/init?account_id=${accountId}&region=${region}`);
      const { redirect_token } = response.data;
      const link = `${window.location.origin}/api/auth/amazon?redirect_token=${redirect_token}`;
      await navigator.clipboard.writeText(link);
      setCopiedAccountId(accountId);
      setSuccessMessage('Link copiato negli appunti!');
      setTimeout(() => {
        setCopiedAccountId(null);
        setSuccessMessage(null);
      }, 3000);
    } catch (error) {
      console.error('Failed to generate link:', error);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAccountName.trim()) return;

    setIsCreating(true);
    try {
      await accountsAPI.create(newAccountName.trim());
      setNewAccountName('');
      await loadAccounts();
    } catch (error) {
      console.error('Failed to create account:', error);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Sei sicuro di voler eliminare questo account?')) return;

    try {
      await accountsAPI.delete(id);
      if (selectedAccount?.id === id) {
        setSelectedAccount(null);
      }
      await loadAccounts();
    } catch (error) {
      console.error('Failed to delete account:', error);
    }
  };

  const openRenameModal = (account: Account) => {
    setRenameAccountId(account.id);
    setRenameValue(account.name);
    setShowRenameModal(true);
  };

  const handleRename = async () => {
    if (!renameAccountId || !renameValue.trim()) return;
    
    setIsRenaming(true);
    try {
      await accountsAPI.rename(renameAccountId, renameValue.trim());
      setShowRenameModal(false);
      setRenameAccountId(null);
      setRenameValue('');
      await loadAccounts();
      setSuccessMessage('Account rinominato con successo!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (error) {
      console.error('Failed to rename account:', error);
    } finally {
      setIsRenaming(false);
    }
  };

  const handleConnectClick = (accountId: number) => {
    setPendingAccountId(accountId);
    setShowRegionModal(true);
  };

  const handleConnect = async () => {
    if (!pendingAccountId) return;
    
    try {
      const response = await api.post(`/auth/amazon/init?account_id=${pendingAccountId}&region=${selectedRegion}`);
      const { redirect_token } = response.data;
      window.location.href = `/api/auth/amazon?redirect_token=${redirect_token}`;
    } catch (error: any) {
      console.error('Failed to start Amazon connection:', error);
      alert(error.response?.data?.detail || 'Errore durante il collegamento con Amazon');
    }
  };

  const handleSelectAccount = (account: Account) => {
    if (!account.has_token) return;
    setSelectedAccount(account);
    navigate('/profiles');
  };

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[#0F1D32]">Account Amazon Ads</h1>
        <p className="text-gray-600 mt-1">
          Gestisci i tuoi account Amazon Advertising
        </p>
      </div>

      {selectedAccount && (
        <div className="bg-white border-2 border-[#00D4FF] rounded-xl p-4 mb-6 flex items-center justify-between">
          <div>
            <p className="text-sm text-[#00D4FF] font-medium">Account selezionato</p>
            <p className="text-lg font-semibold text-[#0F1D32]">{selectedAccount.name}</p>
          </div>
          <button
            onClick={() => navigate('/profiles')}
            className="flex items-center gap-2 bg-[#00D4FF] text-white px-4 py-2 rounded-lg hover:bg-[#00A8CC] transition"
          >
            Vai ai Profili
            <ChevronRight size={18} />
          </button>
        </div>
      )}

      {successMessage && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6 flex items-center gap-3">
          <Check className="text-green-600" size={20} />
          <span className="text-green-800">{successMessage}</span>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-[#0F1D32] mb-4">Nuovo Account</h2>
        <form onSubmit={handleCreate} className="flex gap-4">
          <input
            type="text"
            value={newAccountName}
            onChange={(e) => setNewAccountName(e.target.value)}
            placeholder="Nome account (es. Brand Italia)"
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
          />
          <button
            type="submit"
            disabled={isCreating || !newAccountName.trim()}
            className="bg-[#00D4FF] text-white px-6 py-2.5 rounded-lg font-medium hover:bg-[#00A8CC] transition disabled:opacity-50 flex items-center gap-2"
          >
            <Plus size={20} />
            Crea
          </button>
        </form>
        <p className="text-xs text-gray-500 mt-3">
          Crea un account e collegalo con Amazon
        </p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-[#0F1D32]">I tuoi Account</h2>
            <p className="text-sm text-gray-500 mt-1">Clicca su un account collegato per selezionarlo</p>
          </div>
          <button
            onClick={() => { setIsLoading(true); loadAccounts(); }}
            className="p-2 text-gray-500 hover:text-[#00D4FF] hover:bg-gray-100 rounded-lg transition"
            title="Aggiorna lista"
          >
            <RefreshCw size={18} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>

        {isLoading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          </div>
        ) : accounts.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            Nessun account creato. Crea il tuo primo account per iniziare.
          </div>
        ) : (
          <div className="divide-y divide-slate-200">
            {accounts.map((account) => (
              <div
                key={account.id}
                onClick={() => handleSelectAccount(account)}
                className={`px-6 py-4 flex items-center justify-between transition ${
                  account.has_token 
                    ? 'hover:bg-gray-50 cursor-pointer' 
                    : 'bg-gray-50'
                } ${selectedAccount?.id === account.id ? 'bg-white border-l-4 border-blue-500' : ''}`}
              >
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    selectedAccount?.id === account.id ? 'bg-blue-100' : 'bg-gray-100'
                  }`}>
                    <span className={`font-medium ${
                      selectedAccount?.id === account.id ? 'text-[#00D4FF]' : 'text-gray-600'
                    }`}>
                      {account.name.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <p className="font-medium text-[#0F1D32]">{account.name}</p>
                    <p className="text-sm text-gray-500">
                      {account.has_token ? (
                        <span className="text-green-600 flex items-center gap-1">
                          <Check size={14} />
                          Collegato
                        </span>
                      ) : (
                        'Non collegato'
                      )}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  {!account.has_token && (
                    <>
                      <button
                        onClick={() => handleConnectClick(account.id)}
                        className="flex items-center gap-2 px-4 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 transition"
                      >
                        <LinkIcon size={16} />
                        Collega Amazon
                      </button>
                      <button
                        onClick={() => copyAccountLink(account.id)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition ${
                          copiedAccountId === account.id
                            ? 'bg-green-500 text-white'
                            : 'bg-cyan-100 text-cyan-700 hover:bg-cyan-200'
                        }`}
                      >
                        <Copy size={16} />
                        {copiedAccountId === account.id ? 'Copiato!' : 'Copia Link'}
                      </button>
                    </>
                  )}
                  {account.has_token && selectedAccount?.id !== account.id && (
                    <ChevronRight size={20} className="text-slate-400" />
                  )}
                  <button
                    onClick={() => openRenameModal(account)}
                    className="p-2 text-slate-400 hover:text-blue-500 transition"
                    title="Rinomina account"
                  >
                    <Pencil size={18} />
                  </button>
                  <button
                    onClick={() => handleDelete(account.id)}
                    className="p-2 text-slate-400 hover:text-red-500 transition"
                    title="Elimina account"
                  >
                    <Trash2 size={20} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showRenameModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-[#0F1D32]">Rinomina Account</h2>
              <button
                onClick={() => {
                  setShowRenameModal(false);
                  setRenameAccountId(null);
                  setRenameValue('');
                }}
                className="p-2 hover:bg-gray-100 rounded-lg transition"
              >
                <X size={20} className="text-gray-500" />
              </button>
            </div>

            <p className="text-gray-600 mb-4">
              Inserisci il nuovo nome per questo account.
            </p>

            <input
              type="text"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              placeholder="Nuovo nome account"
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[#00D4FF] focus:border-transparent outline-none mb-4"
              onKeyDown={(e) => e.key === 'Enter' && handleRename()}
            />

            <button
              onClick={handleRename}
              disabled={isRenaming || !renameValue.trim()}
              className="w-full py-3 bg-[#00D4FF] text-white font-semibold rounded-xl hover:bg-[#00A8CC] transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isRenaming ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                  Salvando...
                </>
              ) : (
                <>
                  <Check size={18} />
                  Salva
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {showRegionModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-[#0F1D32]">Seleziona Regione Amazon</h2>
              <button
                onClick={() => setShowRegionModal(false)}
                className="p-2 hover:bg-gray-100 rounded-lg transition"
              >
                <X size={20} className="text-gray-500" />
              </button>
            </div>

            <p className="text-gray-600 mb-4">
              Seleziona la regione del marketplace Amazon dove è registrato l'account pubblicitario.
            </p>

            <div className="space-y-3 mb-6">
              <label className={`flex items-center p-4 border-2 rounded-xl cursor-pointer transition ${selectedRegion === 'na' ? 'border-cyan-500 bg-cyan-50' : 'border-gray-200 hover:border-gray-300'}`}>
                <input
                  type="radio"
                  name="region"
                  value="na"
                  checked={selectedRegion === 'na'}
                  onChange={(e) => setSelectedRegion(e.target.value)}
                  className="sr-only"
                />
                <div>
                  <p className="font-medium text-[#0F1D32]">🇺🇸 North America (NA)</p>
                  <p className="text-sm text-gray-500">USA, Canada, Mexico, Brazil</p>
                </div>
              </label>

              <label className={`flex items-center p-4 border-2 rounded-xl cursor-pointer transition ${selectedRegion === 'eu' ? 'border-cyan-500 bg-cyan-50' : 'border-gray-200 hover:border-gray-300'}`}>
                <input
                  type="radio"
                  name="region"
                  value="eu"
                  checked={selectedRegion === 'eu'}
                  onChange={(e) => setSelectedRegion(e.target.value)}
                  className="sr-only"
                />
                <div>
                  <p className="font-medium text-[#0F1D32]">🇪🇺 Europe (EU)</p>
                  <p className="text-sm text-gray-500">UK, Germany, France, Italy, Spain, etc.</p>
                </div>
              </label>

              <label className={`flex items-center p-4 border-2 rounded-xl cursor-pointer transition ${selectedRegion === 'fe' ? 'border-cyan-500 bg-cyan-50' : 'border-gray-200 hover:border-gray-300'}`}>
                <input
                  type="radio"
                  name="region"
                  value="fe"
                  checked={selectedRegion === 'fe'}
                  onChange={(e) => setSelectedRegion(e.target.value)}
                  className="sr-only"
                />
                <div>
                  <p className="font-medium text-[#0F1D32]">🌏 Far East (FE)</p>
                  <p className="text-sm text-gray-500">Japan, Australia, Singapore</p>
                </div>
              </label>
            </div>

            <button
              onClick={() => {
                setShowRegionModal(false);
                handleConnect();
              }}
              className="w-full py-3 bg-gradient-to-r from-cyan-500 to-cyan-600 text-white font-semibold rounded-xl hover:from-cyan-600 hover:to-cyan-700 transition flex items-center justify-center gap-2"
            >
              <LinkIcon size={18} />
              Collega con Amazon
            </button>
          </div>
        </div>
      )}
    </Layout>
  );
}
