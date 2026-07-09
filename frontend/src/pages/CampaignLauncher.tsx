import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Rocket, Check, AlertCircle, Loader2, Package, Search, Zap } from 'lucide-react';
import api from '../lib/api';
import Layout from '../components/Layout';

interface Profile {
  id: number;
  account_id: number;
  account_name: string;
  profile_id: string;
  country_code: string;
  marketplace: string;
  region: string;
  api_url: string;
}

interface CampaignConfig {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  enabled: boolean;
  bid: number;
  type: string;
  biddingStrategy: string;
}

interface LaunchResult {
  campaign_type: string;
  success: boolean;
  campaign_id?: string;
  ad_group_id?: string;
  error?: string;
}

interface ExtractorJob {
  id: string;
  seed_keywords: string[];
  status: string;
  asins_found: number;
  keywords_found: number;
}

const countryFlags: Record<string, string> = {
  IT: '\u{1F1EE}\u{1F1F9}', DE: '\u{1F1E9}\u{1F1EA}', FR: '\u{1F1EB}\u{1F1F7}', ES: '\u{1F1EA}\u{1F1F8}', 
  UK: '\u{1F1EC}\u{1F1E7}', GB: '\u{1F1EC}\u{1F1E7}', US: '\u{1F1FA}\u{1F1F8}', CA: '\u{1F1E8}\u{1F1E6}', 
  MX: '\u{1F1F2}\u{1F1FD}', BR: '\u{1F1E7}\u{1F1F7}', JP: '\u{1F1EF}\u{1F1F5}', AU: '\u{1F1E6}\u{1F1FA}', 
  IN: '\u{1F1EE}\u{1F1F3}', AE: '\u{1F1E6}\u{1F1EA}', SA: '\u{1F1F8}\u{1F1E6}', NL: '\u{1F1F3}\u{1F1F1}', 
  BE: '\u{1F1E7}\u{1F1EA}', SE: '\u{1F1F8}\u{1F1EA}', PL: '\u{1F1F5}\u{1F1F1}',
};

export default function CampaignLauncher() {
  const navigate = useNavigate();
  
  const [isLoading, setIsLoading] = useState(false);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null);
  const [asin, setAsin] = useState('');
  const [campaignName, setCampaignName] = useState('');
  const [dailyBudget, setDailyBudget] = useState<number>(5);
  
  const [campaigns, setCampaigns] = useState<CampaignConfig[]>([
    { id: 'auto', name: 'Automatica', description: 'Amazon sceglie i target automaticamente', icon: <Zap className="w-5 h-5" />, enabled: true, bid: 0.20, type: 'automatica', biddingStrategy: 'DOWN_ONLY' },
    { id: 'product_exact', name: 'Product Exact', description: 'Targeting ASIN esatto', icon: <Package className="w-5 h-5" />, enabled: false, bid: 0.20, type: 'product_exact', biddingStrategy: 'DOWN_ONLY' },
    { id: 'product_expanded', name: 'Product Expanded', description: 'Targeting ASIN espanso', icon: <Package className="w-5 h-5" />, enabled: false, bid: 0.20, type: 'product_expanded', biddingStrategy: 'DOWN_ONLY' },
    { id: 'kws_phrase', name: 'KWS Phrase', description: 'Keywords con match phrase', icon: <Search className="w-5 h-5" />, enabled: false, bid: 0.20, type: 'keywords', biddingStrategy: 'DOWN_ONLY' },
    { id: 'kws_exact', name: 'KWS Exact', description: 'Keywords con match exact', icon: <Search className="w-5 h-5" />, enabled: false, bid: 0.25, type: 'keywords', biddingStrategy: 'DOWN_ONLY' },
    { id: 'kws_broad', name: 'KWS Broad', description: 'Keywords con match broad', icon: <Search className="w-5 h-5" />, enabled: false, bid: 0.15, type: 'keywords', biddingStrategy: 'DOWN_ONLY' },
  ]);

  const [extractorJobs, setExtractorJobs] = useState<ExtractorJob[]>([]);
  const [selectedAsinJobId, setSelectedAsinJobId] = useState<string | null>(null);
  const [selectedKwsJobId, setSelectedKwsJobId] = useState<string | null>(null);
  const [extractedAsins, setExtractedAsins] = useState<string[]>([]);
  const [extractedKeywords, setExtractedKeywords] = useState<string[]>([]);
  
  const [isLaunching, setIsLaunching] = useState(false);
  const [launchResults, setLaunchResults] = useState<LaunchResult[]>([]);
  const [launchProgress, setLaunchProgress] = useState<string>('');
  const [bidInputs, setBidInputs] = useState<Record<string, string>>({
    auto: '0.20', product_exact: '0.20', product_expanded: '0.20',
    kws_phrase: '0.20', kws_exact: '0.25', kws_broad: '0.15'
  });

  useEffect(() => {
    loadProfiles();
    loadExtractorJobs();
  }, []);

  const loadProfiles = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/campaign-launcher/profiles');
      setProfiles(response.data.profiles || []);
    } catch (err: any) {
      setError('Errore nel caricamento dei profili');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadExtractorJobs = async () => {
    try {
      const response = await api.get('/extractor/jobs?limit=20');
      const completedJobs = (response.data.items || []).filter((j: ExtractorJob) => j.status === 'completed');
      setExtractorJobs(completedJobs);
    } catch (err) {
      console.error('Failed to load extractor jobs:', err);
    }
  };

  const loadAsinJobData = async (jobId: string) => {
    try {
      const asinsRes = await api.get(`/extractor/asins?job_id=${jobId}&limit=1000`);
      setExtractedAsins((asinsRes.data.items || []).map((a: any) => a.asin));
    } catch (err) {
      console.error('Failed to load ASIN job data:', err);
    }
  };

  const loadKwsJobData = async (jobId: string) => {
    try {
      const kwsRes = await api.get(`/extractor/keywords?job_id=${jobId}&limit=1000`);
      setExtractedKeywords((kwsRes.data.items || []).map((k: any) => k.keyword));
    } catch (err) {
      console.error('Failed to load KWS job data:', err);
    }
  };

  const handleAsinJobSelect = async (jobId: string) => {
    setSelectedAsinJobId(jobId);
    await loadAsinJobData(jobId);
  };

  const handleKwsJobSelect = async (jobId: string) => {
    setSelectedKwsJobId(jobId);
    await loadKwsJobData(jobId);
  };

  const toggleCampaign = (id: string) => {
    setCampaigns(prev => prev.map(c => 
      c.id === id ? { ...c, enabled: !c.enabled } : c
    ));
  };

  const updateBid = (id: string, bid: number) => {
    setCampaigns(prev => prev.map(c => 
      c.id === id ? { ...c, bid } : c
    ));
  };

  const handleBidInputChange = (id: string, value: string) => {
    setBidInputs(prev => ({ ...prev, [id]: value }));
  };

  const handleBidInputBlur = (id: string) => {
    const val = bidInputs[id]?.replace(',', '.') || '0.20';
    const num = parseFloat(val);
    if (!isNaN(num) && num >= 0.02) {
      updateBid(id, num);
      setBidInputs(prev => ({ ...prev, [id]: num.toFixed(2) }));
    } else {
      setBidInputs(prev => ({ ...prev, [id]: '0.20' }));
      updateBid(id, 0.20);
    }
  };

  const enableAllCampaigns = () => {
    setCampaigns(prev => prev.map(c => ({ ...c, enabled: true })));
  };

  const disableAllCampaigns = () => {
    setCampaigns(prev => prev.map(c => ({ ...c, enabled: false })));
  };

  const canLaunch = (): boolean => {
    if (!selectedProfile) return false;
    if (asin.length < 10) return false;
    if (!campaignName.trim()) return false;
    if (!campaigns.some(c => c.enabled)) return false;
    
    const enabledCampaigns = campaigns.filter(c => c.enabled);
    const needsAsins = enabledCampaigns.some(c => c.id.startsWith('product_'));
    const needsKeywords = enabledCampaigns.some(c => c.id.startsWith('kws_'));
    
    if (needsAsins && extractedAsins.length === 0) return false;
    if (needsKeywords && extractedKeywords.length === 0) return false;
    
    return true;
  };

  const handleLaunch = async () => {
    if (!selectedProfile || !canLaunch()) return;

    setIsLaunching(true);
    setLaunchResults([]);
    setError(null);

    const enabledCampaigns = campaigns.filter(c => c.enabled);
    const results: LaunchResult[] = [];

    for (const campaign of enabledCampaigns) {
      setLaunchProgress(`Creazione: ${campaign.name}...`);

      try {
        let targets: any[] | undefined;

        if (campaign.id === 'product_exact') {
          targets = extractedAsins.map(a => ({ asin: a, bid: campaign.bid, expression_type: 'exact' }));
        } else if (campaign.id === 'product_expanded') {
          targets = extractedAsins.map(a => ({ asin: a, bid: campaign.bid, expression_type: 'expanded' }));
        } else if (campaign.id === 'kws_phrase') {
          targets = extractedKeywords.map(k => ({ keyword: k, match_type: 'phrase', bid: campaign.bid }));
        } else if (campaign.id === 'kws_exact') {
          targets = extractedKeywords.map(k => ({ keyword: k, match_type: 'exact', bid: campaign.bid }));
        } else if (campaign.id === 'kws_broad') {
          targets = extractedKeywords.map(k => ({ keyword: k, match_type: 'broad', bid: campaign.bid }));
        }

        const suffix = campaign.id === 'auto' ? 'AUTO' : 
                       campaign.id === 'product_exact' ? 'PROD-EX' :
                       campaign.id === 'product_expanded' ? 'PROD-EXP' :
                       campaign.id === 'kws_phrase' ? 'PHRASE' :
                       campaign.id === 'kws_exact' ? 'EXACT' : 'BROAD';

        const response = await api.post('/campaign-launcher/launch', {
          account_id: selectedProfile.account_id,
          profile_id: selectedProfile.profile_id,
          campaign_type: campaign.type,
          campaign_name: `${campaignName} - ${suffix}`,
          ad_group_name: `${campaignName} - ${suffix}`,
          asin: asin,
          daily_budget: dailyBudget,
          default_bid: campaign.bid,
          targets: targets,
          bidding_strategy: campaign.biddingStrategy,
        });

        results.push({
          campaign_type: campaign.name,
          success: response.data.success,
          campaign_id: response.data.campaign_id,
          ad_group_id: response.data.ad_group_id,
          error: response.data.error,
        });
      } catch (err: any) {
        results.push({
          campaign_type: campaign.name,
          success: false,
          error: err.response?.data?.detail || 'Errore durante la creazione',
        });
      }
    }

    setLaunchResults(results);
    setLaunchProgress('');
    setIsLaunching(false);
  };

  const resetForm = () => {
    setAsin('');
    setCampaignName('');
    setLaunchResults([]);
    setSelectedAsinJobId(null);
    setSelectedKwsJobId(null);
    setExtractedAsins([]);
    setExtractedKeywords([]);
    setCampaigns(prev => prev.map(c => ({ ...c, enabled: c.id === 'auto', biddingStrategy: 'DOWN_ONLY' })));
  };

  if (launchResults.length > 0) {
    const successCount = launchResults.filter(r => r.success).length;
    const failCount = launchResults.filter(r => !r.success).length;

    return (
      <Layout>
        <div className="max-w-3xl mx-auto">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Rocket className="w-6 h-6 text-cyan-500" />
              Risultato Lancio
            </h1>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-4 mb-6">
              {failCount === 0 ? (
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                  <Check className="w-8 h-8 text-green-600" />
                </div>
              ) : successCount === 0 ? (
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center">
                  <AlertCircle className="w-8 h-8 text-red-600" />
                </div>
              ) : (
                <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center">
                  <AlertCircle className="w-8 h-8 text-yellow-600" />
                </div>
              )}
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  {failCount === 0 ? 'Tutte le campagne create!' : 
                   successCount === 0 ? 'Errore nella creazione' : 
                   'Creazione parziale'}
                </h2>
                <p className="text-gray-600">
                  {successCount} campagne create, {failCount} errori
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {launchResults.map((result, idx) => (
                <div
                  key={idx}
                  className={`p-4 rounded-lg border ${
                    result.success 
                      ? 'bg-green-50 border-green-200' 
                      : 'bg-red-50 border-red-200'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {result.success ? (
                        <Check className="w-5 h-5 text-green-600" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-600" />
                      )}
                      <span className="font-medium">{result.campaign_type}</span>
                    </div>
                    {result.success && (
                      <code className="text-xs bg-green-100 px-2 py-1 rounded">
                        {result.campaign_id}
                      </code>
                    )}
                  </div>
                  {result.error && (
                    <p className="mt-2 text-sm text-red-600">{result.error}</p>
                  )}
                </div>
              ))}
            </div>

            <div className="flex gap-4 mt-6">
              <button
                onClick={resetForm}
                className="flex-1 py-3 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 transition-colors"
              >
                Lancia altre campagne
              </button>
              <button
                onClick={() => navigate('/campaigns')}
                className="flex-1 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Vai alle campagne
              </button>
            </div>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Rocket className="w-6 h-6 text-cyan-500" />
            Lancia Campagne
          </h1>
          <p className="text-gray-600">Crea automaticamente più campagne Sponsored Products</p>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
            <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
            <p className="text-red-700">{error}</p>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">1. Seleziona Profilo</h2>
              
              {profiles.length === 0 ? (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
                  <AlertCircle className="w-8 h-8 text-yellow-500 mx-auto mb-2" />
                  <p className="text-yellow-700">Nessun profilo disponibile</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {profiles.map((profile) => (
                    <button
                      key={`${profile.account_id}-${profile.profile_id}`}
                      onClick={() => setSelectedProfile(profile)}
                      className={`flex items-center p-3 rounded-lg border-2 transition-all text-left ${
                        selectedProfile?.profile_id === profile.profile_id
                          ? 'border-cyan-500 bg-cyan-50'
                          : 'border-gray-200 hover:border-cyan-300 bg-white'
                      }`}
                    >
                      <span className="text-xl mr-2">{countryFlags[profile.country_code] || '\u{1F310}'}</span>
                      <div className="min-w-0">
                        <div className="font-medium text-gray-900 text-sm truncate">{profile.account_name}</div>
                        <div className="text-xs text-gray-500">{profile.country_code}</div>
                      </div>
                      {selectedProfile?.profile_id === profile.profile_id && (
                        <Check className="w-4 h-4 text-cyan-500 ml-auto flex-shrink-0" />
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">2. Configurazione Base</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    ASIN Prodotto *
                  </label>
                  <input
                    type="text"
                    value={asin}
                    onChange={(e) => setAsin(e.target.value.toUpperCase())}
                    placeholder="B08N5WRWNW"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Nome Campagna *
                  </label>
                  <input
                    type="text"
                    value={campaignName}
                    onChange={(e) => setCampaignName(e.target.value)}
                    placeholder="Nome campagna"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Budget Giornaliero (EUR)
                  </label>
                  <input
                    type="number"
                    value={dailyBudget}
                    onChange={(e) => setDailyBudget(parseFloat(e.target.value) || 5)}
                    step="0.5"
                    min="1"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
                  />
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">3. Campagne da Lanciare</h2>
                <div className="flex items-center gap-3">
                  <select
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val) setCampaigns(prev => prev.map(c => ({ ...c, biddingStrategy: val })));
                    }}
                    defaultValue=""
                    className="text-xs px-2 py-1 border border-gray-300 rounded focus:ring-2 focus:ring-cyan-500"
                  >
                    <option value="" disabled>Strategia per tutte</option>
                    <option value="DOWN_ONLY">Down only</option>
                    <option value="UP_AND_DOWN">Up & Down</option>
                    <option value="FIXED">Fixed bid</option>
                  </select>
                  <span className="text-gray-300">|</span>
                  <button
                    onClick={enableAllCampaigns}
                    className="text-sm text-cyan-600 hover:text-cyan-700"
                  >
                    Seleziona tutte
                  </button>
                  <span className="text-gray-300">|</span>
                  <button
                    onClick={disableAllCampaigns}
                    className="text-sm text-gray-600 hover:text-gray-700"
                  >
                    Deseleziona tutte
                  </button>
                </div>
              </div>
              
              <div className="space-y-3">
                {campaigns.map((campaign) => (
                  <div
                    key={campaign.id}
                    className={`flex items-center gap-4 p-4 rounded-lg border-2 transition-all ${
                      campaign.enabled
                        ? 'border-cyan-500 bg-cyan-50'
                        : 'border-gray-200 bg-white'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={campaign.enabled}
                      onChange={() => toggleCampaign(campaign.id)}
                      className="w-5 h-5 rounded border-gray-300 text-cyan-500 focus:ring-cyan-500"
                    />
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      campaign.enabled ? 'bg-cyan-500 text-white' : 'bg-gray-100 text-gray-400'
                    }`}>
                      {campaign.icon}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">{campaign.name}</div>
                      <div className="text-sm text-gray-500">{campaign.description}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1">
                        <label className="text-sm text-gray-600">Bid:</label>
                        <input
                          type="text"
                          inputMode="decimal"
                          value={bidInputs[campaign.id] || campaign.bid.toFixed(2)}
                          onChange={(e) => handleBidInputChange(campaign.id, e.target.value)}
                          onBlur={() => handleBidInputBlur(campaign.id)}
                          disabled={!campaign.enabled}
                          className="w-20 px-2 py-1 border border-gray-300 rounded text-center focus:ring-2 focus:ring-cyan-500 disabled:bg-gray-100 disabled:text-gray-400"
                        />
                      </div>
                      <select
                        value={campaign.biddingStrategy}
                        onChange={(e) => {
                          setCampaigns(prev => prev.map(c => 
                            c.id === campaign.id ? { ...c, biddingStrategy: e.target.value } : c
                          ));
                        }}
                        disabled={!campaign.enabled}
                        className="text-xs px-2 py-1 border border-gray-300 rounded focus:ring-2 focus:ring-cyan-500 disabled:bg-gray-100 disabled:text-gray-400"
                      >
                        <option value="DOWN_ONLY">Down only</option>
                        <option value="UP_AND_DOWN">Up & Down</option>
                        <option value="FIXED">Fixed bid</option>
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">4. Dati Extractor</h2>
              <p className="text-sm text-gray-600 mb-4">
                Seleziona le estrazioni per importare ASINs e Keywords separatamente
              </p>

              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <Package className="w-4 h-4" />
                    Selezione ASIN (per campagne Product)
                  </h3>
                  {!campaigns.some(c => c.enabled && c.id.startsWith('product_')) ? (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center opacity-60">
                      <p className="text-sm text-gray-400">Abilita una campagna product per selezionare</p>
                    </div>
                  ) : extractorJobs.filter(j => j.asins_found > 0).length === 0 ? (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center">
                      <Package className="w-8 h-8 text-gray-300 mx-auto mb-1" />
                      <p className="text-gray-500 text-sm">Nessuna estrazione con ASIN disponibile</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {extractorJobs.filter(j => j.asins_found > 0).map((job) => (
                        <button
                          key={job.id}
                          onClick={() => handleAsinJobSelect(job.id)}
                          className={`w-full flex items-center gap-3 p-3 rounded-lg border-2 transition-all text-left ${
                            selectedAsinJobId === job.id
                              ? 'border-cyan-500 bg-cyan-50'
                              : 'border-gray-200 hover:border-cyan-300'
                          }`}
                        >
                          <div className="w-8 h-8 bg-cyan-100 rounded-lg flex items-center justify-center">
                            <Package className="w-4 h-4 text-cyan-500" />
                          </div>
                          <div className="flex-1">
                            <div className="font-medium text-gray-900 text-sm">
                              {job.seed_keywords.slice(0, 3).join(', ')}
                              {job.seed_keywords.length > 3 && ` +${job.seed_keywords.length - 3}`}
                            </div>
                            <div className="text-xs text-gray-500">{job.asins_found} ASINs</div>
                          </div>
                          {selectedAsinJobId === job.id && (
                            <Check className="w-4 h-4 text-cyan-500" />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                  {selectedAsinJobId && extractedAsins.length > 0 && (
                    <div className="mt-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                      <div className="flex items-center gap-2 text-green-700 text-sm">
                        <Check className="w-4 h-4" />
                        <span className="font-medium">{extractedAsins.length} ASINs caricati</span>
                      </div>
                    </div>
                  )}
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <Search className="w-4 h-4" />
                    Selezione Keywords (per campagne Keyword)
                  </h3>
                  {!campaigns.some(c => c.enabled && c.id.startsWith('kws_')) ? (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center opacity-60">
                      <p className="text-sm text-gray-400">Abilita una campagna keyword per selezionare</p>
                    </div>
                  ) : extractorJobs.filter(j => j.keywords_found > 0).length === 0 ? (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center">
                      <Search className="w-8 h-8 text-gray-300 mx-auto mb-1" />
                      <p className="text-gray-500 text-sm">Nessuna estrazione con Keywords disponibile</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {extractorJobs.filter(j => j.keywords_found > 0).map((job) => (
                        <button
                          key={job.id}
                          onClick={() => handleKwsJobSelect(job.id)}
                          className={`w-full flex items-center gap-3 p-3 rounded-lg border-2 transition-all text-left ${
                            selectedKwsJobId === job.id
                              ? 'border-cyan-500 bg-cyan-50'
                              : 'border-gray-200 hover:border-cyan-300'
                          }`}
                        >
                          <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center">
                            <Search className="w-4 h-4 text-purple-500" />
                          </div>
                          <div className="flex-1">
                            <div className="font-medium text-gray-900 text-sm">
                              {job.seed_keywords.slice(0, 3).join(', ')}
                              {job.seed_keywords.length > 3 && ` +${job.seed_keywords.length - 3}`}
                            </div>
                            <div className="text-xs text-gray-500">{job.keywords_found} Keywords</div>
                          </div>
                          {selectedKwsJobId === job.id && (
                            <Check className="w-4 h-4 text-cyan-500" />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                  {selectedKwsJobId && extractedKeywords.length > 0 && (
                    <div className="mt-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                      <div className="flex items-center gap-2 text-green-700 text-sm">
                        <Check className="w-4 h-4" />
                        <span className="font-medium">{extractedKeywords.length} Keywords caricate</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <button
              onClick={handleLaunch}
              disabled={!canLaunch() || isLaunching}
              className="w-full py-4 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-colors flex items-center justify-center gap-3 text-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLaunching ? (
                <>
                  <Loader2 className="w-6 h-6 animate-spin" />
                  {launchProgress || 'Creazione in corso...'}
                </>
              ) : (
                <>
                  <Rocket className="w-6 h-6" />
                  Lancia {campaigns.filter(c => c.enabled).length} Campagne
                </>
              )}
            </button>

            {!canLaunch() && selectedProfile && (
              <div className="text-center text-sm text-gray-500">
                {!campaignName.trim() && <p>Inserisci il nome della campagna</p>}
                {asin.length < 10 && <p>Inserisci un ASIN valido</p>}
                {!campaigns.some(c => c.enabled) && <p>Seleziona almeno una campagna</p>}
                {campaigns.some(c => c.enabled && c.id.startsWith('product_')) && extractedAsins.length === 0 && (
                  <p>Seleziona un'estrazione ASIN per le campagne Product</p>
                )}
                {campaigns.some(c => c.enabled && c.id.startsWith('kws_')) && extractedKeywords.length === 0 && (
                  <p>Seleziona un'estrazione per le campagne Keywords</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}
