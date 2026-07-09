import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Database, Search, BookOpen, Grid3X3, Plus, X, Loader2, AlertCircle, Zap, Shield, Radio, StopCircle } from 'lucide-react';
import Layout from '../components/Layout';
import PageHeader from '../components/PageHeader';
import api from '../lib/api';

export default function ExtractorNew() {
  const [seedKeywords, setSeedKeywords] = useState<string[]>([]);
  const [currentKeyword, setCurrentKeyword] = useState('');
  const [extractionType, setExtractionType] = useState<'asins' | 'keywords'>('asins');
  const [categoryMode, setCategoryMode] = useState<'books' | 'all'>('books');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [showProgress, setShowProgress] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const pollInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const navigate = useNavigate();

  const getProgressLabel = (pct: number, type: string): string => {
    if (type === 'asins') {
      if (pct <= 5)  return 'Avvio estrazione...';
      if (pct <= 55) return 'Ricerca ASIN su Amazon...';
      if (pct <= 80) return 'Arricchimento dati prodotto...';
      if (pct <= 95) return 'Salvataggio risultati...';
      return 'Completamento...';
    }
    if (pct <= 5)  return 'Avvio estrazione...';
    if (pct <= 20) return 'Autocomplete L1 (seed keywords)...';
    if (pct <= 40) return 'Autocomplete L2 (espansione)...';
    if (pct <= 65) return 'Ricerca SERP Amazon...';
    if (pct <= 90) return 'Salvataggio keywords...';
    return 'Completamento...';
  };

  const startPolling = useCallback((type: 'asins' | 'keywords') => {
    if (pollInterval.current) clearInterval(pollInterval.current);

    pollInterval.current = setInterval(async () => {
      try {
        const res = await api.get('/extractor/current');
        if (res.data) {
          const serverProgress = res.data.progress || 0;
          setProgress(serverProgress);

          const currentType = res.data.extraction_type || type;
          const found = currentType === 'asins'
            ? `${res.data.asins_found || 0} ASIN trovati`
            : `${res.data.keywords_found || 0} keywords trovate`;
          const phaseLabel = getProgressLabel(serverProgress, currentType);
          setProgressMessage(`${phaseLabel} — ${found}`);

          if (res.data.status === 'completed' || res.data.status === 'error') {
            if (pollInterval.current) clearInterval(pollInterval.current);
            if (res.data.status === 'error') {
              setLoading(false);
              setShowProgress(false);
              setError(res.data.error || 'Estrazione terminata con errore');
              return;
            }
            setProgress(100);
            setProgressMessage('Completato!');
            setTimeout(() => {
              navigate(currentType === 'asins' ? '/extractor/asins' : '/extractor/keywords');
            }, 600);
          }
        } else {
          if (pollInterval.current) clearInterval(pollInterval.current);
          setLoading(false);
          setShowProgress(false);
        }
      } catch {
      }
    }, 1500);
  }, [navigate]);

  useEffect(() => {
    const checkExisting = async () => {
      try {
        const res = await api.get('/extractor/current');
        if (res.data && res.data.status === 'processing') {
          const type = res.data.extraction_type || 'asins';
          setExtractionType(type);
          setLoading(true);
          setShowProgress(true);
          setProgress(res.data.progress || 0);
          const found = type === 'asins'
            ? `${res.data.asins_found || 0} ASIN trovati`
            : `${res.data.keywords_found || 0} keywords trovate`;
          setProgressMessage(`${getProgressLabel(res.data.progress || 0, type)} — ${found}`);
          startPolling(type);
        }
      } catch {
      }
    };
    checkExisting();

    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current);
    };
  }, [startPolling]);

  const addKeyword = () => {
    const keywords = currentKeyword.split(';').map(k => k.trim()).filter(k => k);
    const newKeywords = keywords.filter(k => !seedKeywords.includes(k));
    if (seedKeywords.length + newKeywords.length <= 15) {
      setSeedKeywords([...seedKeywords, ...newKeywords]);
      setCurrentKeyword('');
    }
  };

  const removeKeyword = (kw: string) => {
    setSeedKeywords(seedKeywords.filter(k => k !== kw));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addKeyword();
    }
  };

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await api.post('/extractor/stop');
      if (pollInterval.current) clearInterval(pollInterval.current);
      setLoading(false);
      setShowProgress(false);
      setProgress(0);
      setProgressMessage('');
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'annullamento');
    } finally {
      setCancelling(false);
    }
  };

  const startExtraction = async () => {
    if (seedKeywords.length === 0) {
      setError('Aggiungi almeno una keyword seed');
      return;
    }

    setLoading(true);
    setError(null);
    setShowProgress(true);
    setProgress(0);
    setProgressMessage('Avvio estrazione...');

    try {
      await api.post('/extractor/start', {
        extraction_type: extractionType,
        category_mode: categoryMode,
        seed_keywords: seedKeywords,
        max_asins: 1000,
        max_keywords: 1000,
        include_merch: false
      });

      setProgressMessage('Estrazione in corso...');
      startPolling(extractionType);

    } catch (err: any) {
      setLoading(false);
      setShowProgress(false);
      setError(err.response?.data?.detail || 'Errore nell\'avvio dell\'estrazione');
    }
  };

  return (
    <Layout>
      <PageHeader
        title="Nuova Estrazione"
        subtitle="Estrai ASINs e keywords da Amazon utilizzando le tue seed keywords"
      />

      <div className="max-w-4xl">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3 text-red-700">
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-[#00D4FF]/10 rounded-lg flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-[#00D4FF]" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-[#0F1D32]">Nuova Estrazione</h3>
              <p className="text-sm text-gray-500">Inserisci le keyword seed per estrarre dati da Amazon</p>
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">Tipo di Estrazione</label>
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => setExtractionType('asins')}
                disabled={loading}
                className={`p-4 rounded-xl border-2 transition flex flex-col items-center gap-2 ${
                  extractionType === 'asins'
                    ? 'border-[#00D4FF] bg-white'
                    : 'border-gray-200 hover:border-gray-300'
                } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <Database size={24} className={extractionType === 'asins' ? 'text-[#00D4FF]' : 'text-gray-400'} />
                <span className="font-medium text-[#0F1D32]">ASIN</span>
                <span className="text-xs text-gray-500">Estrai codici prodotto</span>
              </button>
              <button
                onClick={() => setExtractionType('keywords')}
                disabled={loading}
                className={`p-4 rounded-xl border-2 transition flex flex-col items-center gap-2 ${
                  extractionType === 'keywords'
                    ? 'border-[#00D4FF] bg-white'
                    : 'border-gray-200 hover:border-gray-300'
                } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <Search size={24} className={extractionType === 'keywords' ? 'text-[#00D4FF]' : 'text-gray-400'} />
                <span className="font-medium text-[#0F1D32]">Keywords</span>
                <span className="text-xs text-gray-500">Estrai parole chiave</span>
              </button>
            </div>
          </div>

          <div className={`mb-6 ${extractionType === 'keywords' ? 'opacity-50 pointer-events-none' : ''}`}>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Modalità Categoria
              {extractionType === 'keywords' && <span className="ml-2 text-xs text-gray-400">(non disponibile per ricerca keywords)</span>}
            </label>
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => setCategoryMode('books')}
                disabled={extractionType === 'keywords' || loading}
                className={`p-4 rounded-xl border-2 transition flex flex-col items-center gap-2 ${
                  categoryMode === 'books'
                    ? 'border-[#00D4FF] bg-white'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <BookOpen size={24} className={categoryMode === 'books' ? 'text-[#00D4FF]' : 'text-gray-400'} />
                <span className="font-medium text-[#0F1D32]">Solo Libri</span>
                <span className="text-xs text-gray-500">Solo libri e cookbook (consigliato)</span>
              </button>
              <button
                onClick={() => setCategoryMode('all')}
                disabled={extractionType === 'keywords' || loading}
                className={`p-4 rounded-xl border-2 transition flex flex-col items-center gap-2 ${
                  categoryMode === 'all'
                    ? 'border-[#00D4FF] bg-white'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <Grid3X3 size={24} className={categoryMode === 'all' ? 'text-[#00D4FF]' : 'text-gray-400'} />
                <span className="font-medium text-[#0F1D32]">Tutte le Categorie</span>
                <span className="text-xs text-gray-500">Libri + accessori correlati</span>
              </button>
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">Keyword Seed</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={currentKeyword}
                onChange={(e) => setCurrentKeyword(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Inserisci keyword (separa con ; per inserimento multiplo)"
                className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
                disabled={loading}
              />
              <button
                onClick={addKeyword}
                disabled={!currentKeyword.trim() || seedKeywords.length >= 15 || loading}
                className="px-4 py-2.5 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition"
              >
                <Plus size={20} />
              </button>
            </div>
            <p className="text-xs text-gray-500 mb-3">
              {seedKeywords.length}/15 keyword aggiunte. Usa il punto e virgola (;) per aggiungerne multiple.
            </p>

            <div className="flex flex-wrap gap-2">
              {seedKeywords.map((kw) => (
                <span
                  key={kw}
                  className="inline-flex items-center gap-2 px-3 py-1.5 bg-white border-2 border-[#00D4FF] rounded-lg text-sm"
                >
                  {kw}
                  <button onClick={() => removeKeyword(kw)} className="text-gray-400 hover:text-red-500" disabled={loading}>
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>
          </div>

          {showProgress && (
            <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-[#0F1D32]">{progressMessage}</span>
                <span className="text-sm font-medium text-[#00D4FF]">{Math.round(progress)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{ 
                    width: `${progress}%`,
                    background: 'linear-gradient(90deg, #00D4FF, #00A8CC)'
                  }}
                />
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={startExtraction}
              disabled={loading || seedKeywords.length === 0}
              className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-[#00D4FF] text-white rounded-lg font-medium hover:bg-[#00A8CC] disabled:opacity-50 transition"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles size={20} />}
              {loading ? 'Estrazione in corso...' : 'Estrai'}
            </button>
            {loading && (
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="flex items-center justify-center gap-2 px-6 py-3 bg-red-500 text-white rounded-lg font-medium hover:bg-red-600 disabled:opacity-50 transition"
              >
                {cancelling ? <Loader2 className="w-5 h-5 animate-spin" /> : <StopCircle size={20} />}
                Annulla
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-white rounded-xl p-4 border border-gray-200 flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
              <Zap className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h4 className="font-medium text-[#0F1D32]">Estrazione Veloce</h4>
              <p className="text-xs text-gray-500">Chiamate API parallele per massima velocità</p>
            </div>
          </div>
          <div className="bg-white rounded-xl p-4 border border-gray-200 flex items-center gap-3">
            <div className="w-10 h-10 bg-cyan-100 rounded-full flex items-center justify-center">
              <Shield className="w-5 h-5 text-cyan-600" />
            </div>
            <div>
              <h4 className="font-medium text-[#0F1D32]">Dati Affidabili</h4>
              <p className="text-xs text-gray-500">Alimentato da Oxylabs & Canopy APIs</p>
            </div>
          </div>
          <div className="bg-white rounded-xl p-4 border border-gray-200 flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center">
              <Radio className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <h4 className="font-medium text-[#0F1D32]">Aggiornamenti Live</h4>
              <p className="text-xs text-gray-500">Monitora il progresso in tempo reale</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-[#0F1D32] mb-2">Come Funziona</h3>
          <p className="text-sm text-gray-500 mb-6">Il nostro processo di estrazione segue questi passaggi</p>

          <div className="space-y-4">
            {[
              'Cerca su Amazon ogni seed keyword usando Canopy API',
              'Raccoglie i prodotti top e best seller dai risultati',
              'Recupera prodotti correlati (Altri Clienti Hanno Comprato)',
              'Estrae keywords dai titoli dei prodotti',
              'Deduplica e categorizza tutti i dati',
              'Esporta i risultati in file CSV o XLSX'
            ].map((step, idx) => (
              <div key={idx} className="flex items-center gap-4">
                <div className="w-8 h-8 bg-[#00D4FF] rounded-full flex items-center justify-center text-white font-bold text-sm">
                  {idx + 1}
                </div>
                <p className="text-gray-700">{step}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
}
