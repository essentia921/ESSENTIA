import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Globe, Check, RefreshCw, AlertCircle, ChevronRight, ArrowLeft } from 'lucide-react';
import api from '../lib/api';
import Layout from '../components/Layout';
import { useSelection } from '../context/SelectionContext';

interface Profile {
  profileId: string;
  countryCode: string;
  marketplace?: string;
  accountId?: string;
  region?: string;
}

export default function Profiles() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { selectedAccount, selectedProfiles, setSelectedProfiles } = useSelection();
  const navigate = useNavigate();

  const selectedProfileIds = new Set(selectedProfiles.map(p => p.profileId));

  useEffect(() => {
    if (selectedAccount) {
      loadProfiles();
    }
  }, [selectedAccount]);

  const loadProfiles = async () => {
    if (!selectedAccount) return;
    
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.get(`/profiles/${selectedAccount.id}`);
      setProfiles(Array.isArray(response.data) ? response.data : []);
    } catch (err: any) {
      console.error('Failed to load profiles:', err);
      if (err.response?.status === 401) {
        setError('Account non collegato ad Amazon Ads. Torna agli account e collega questo account.');
      } else {
        setError('Errore nel caricamento dei profili.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSync = async () => {
    if (!selectedAccount) return;
    
    setIsSyncing(true);
    try {
      await api.get(`/profiles/${selectedAccount.id}?force_refresh=true`);
      await loadProfiles();
    } catch (error) {
      console.error('Failed to sync profiles:', error);
    } finally {
      setIsSyncing(false);
    }
  };

  const toggleProfile = (profile: Profile) => {
    if (selectedProfileIds.has(profile.profileId)) {
      setSelectedProfiles(selectedProfiles.filter(p => p.profileId !== profile.profileId));
    } else {
      setSelectedProfiles([...selectedProfiles, profile]);
    }
  };

  const selectAll = () => {
    setSelectedProfiles(profiles);
  };

  const deselectAll = () => {
    setSelectedProfiles([]);
  };

  const handleContinue = () => {
    navigate('/autopilot');
  };

  const countryFlags: Record<string, string> = {
    IT: '🇮🇹', DE: '🇩🇪', FR: '🇫🇷', ES: '🇪🇸', UK: '🇬🇧', US: '🇺🇸',
    CA: '🇨🇦', MX: '🇲🇽', BR: '🇧🇷', JP: '🇯🇵', AU: '🇦🇺', IN: '🇮🇳',
    AE: '🇦🇪', SA: '🇸🇦', NL: '🇳🇱', BE: '🇧🇪', SE: '🇸🇪', PL: '🇵🇱',
  };

  if (!selectedAccount) {
    return (
      <Layout>
        <div className="text-center py-12">
          <AlertCircle size={48} className="mx-auto mb-4 text-cyan-500" />
          <h2 className="text-xl font-semibold text-[#0F1D32] mb-2">Nessun account selezionato</h2>
          <p className="text-gray-600 mb-6">Seleziona un account Amazon Ads per vedere i profili disponibili.</p>
          <button
            onClick={() => navigate('/accounts')}
            className="bg-[#00D4FF] text-white px-6 py-3 rounded-lg font-medium hover:bg-[#00A8CC] transition"
          >
            Vai agli Account
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mb-6">
        <button
          onClick={() => navigate('/accounts')}
          className="flex items-center gap-2 text-gray-600 hover:text-[#0F1D32] transition mb-4"
        >
          <ArrowLeft size={18} />
          Torna agli Account
        </button>
        
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-[#00D4FF] font-medium">{selectedAccount.name}</p>
            <h1 className="text-2xl font-bold text-[#0F1D32]">Profili Amazon Ads</h1>
            <p className="text-gray-600 mt-1">
              Seleziona uno o piu marketplace da gestire
            </p>
          </div>
          <button
            onClick={handleSync}
            disabled={isSyncing}
            className="flex items-center gap-2 bg-[#00D4FF] text-white px-4 py-2.5 rounded-lg font-medium hover:bg-[#00A8CC] transition disabled:opacity-50"
          >
            <RefreshCw size={18} className={isSyncing ? 'animate-spin' : ''} />
            Sincronizza
          </button>
        </div>
      </div>

      {selectedProfiles.length > 0 && (
        <div className="bg-white border-2 border-[#00D4FF] rounded-xl p-4 mb-6 flex items-center justify-between">
          <div>
            <p className="text-[#0F1D32] font-medium">{selectedProfiles.length} profili selezionati</p>
            <p className="text-sm text-[#00D4FF]">
              {selectedProfiles.map(p => p.countryCode).join(', ')}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={deselectAll}
              className="text-[#00D4FF] hover:underline text-sm"
            >
              Deseleziona tutto
            </button>
            <button
              onClick={handleContinue}
              className="flex items-center gap-2 bg-[#00D4FF] text-white px-4 py-2 rounded-lg hover:bg-[#00A8CC] transition"
            >
              Continua
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-[#0F1D32]">
              {profiles.length} Profili disponibili
            </h2>
          </div>
          {profiles.length > 0 && (
            <button
              onClick={selectAll}
              className="text-sm text-[#00D4FF] hover:underline"
            >
              Seleziona tutti
            </button>
          )}
        </div>

        {isLoading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-500">Caricamento profili...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center">
            <AlertCircle size={48} className="mx-auto mb-4 text-red-500" />
            <p className="text-red-600">{error}</p>
            <button
              onClick={() => navigate('/accounts')}
              className="mt-4 text-[#00D4FF] hover:underline"
            >
              Torna agli Account
            </button>
          </div>
        ) : profiles.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <Globe size={48} className="mx-auto mb-4 text-slate-300" />
            <p>Nessun profilo trovato.</p>
            <p className="text-sm mt-2">Prova a sincronizzare i profili.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-200">
            {profiles.map((profile) => (
              <div
                key={profile.profileId}
                onClick={() => toggleProfile(profile)}
                className={`px-6 py-4 flex items-center justify-between hover:bg-gray-50 cursor-pointer transition ${
                  selectedProfileIds.has(profile.profileId) ? 'bg-white border-l-4 border-l-[#00D4FF]' : ''
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className={`w-6 h-6 rounded border-2 flex items-center justify-center transition ${
                    selectedProfileIds.has(profile.profileId) 
                      ? 'bg-[#00D4FF] border-[#00D4FF]' 
                      : 'border-gray-300'
                  }`}>
                    {selectedProfileIds.has(profile.profileId) && <Check size={14} className="text-white" />}
                  </div>
                  <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center text-2xl">
                    {countryFlags[profile.countryCode] || '🌍'}
                  </div>
                  <div>
                    <p className="font-medium text-[#0F1D32]">
                      {profile.countryCode} - {profile.marketplace || profile.region || 'Marketplace'}
                    </p>
                    <p className="text-sm text-gray-500">
                      Profile ID: {profile.profileId}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
