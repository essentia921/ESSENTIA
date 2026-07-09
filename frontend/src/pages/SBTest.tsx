import { useState } from 'react';
import Layout from '../components/Layout';
import { useSelection } from '../context/SelectionContext';
import { FlaskConical, Download, Loader2, Copy, Check, AlertCircle, Package, TrendingUp } from 'lucide-react';
import api from '../lib/api';

interface SBKeyword {
  keywordId: number;
  campaignId: number;
  adGroupId: number;
  keywordText: string;
  matchType: string;
  bid: number;
  state: string;
}

interface SBTarget {
  targetId: number;
  campaignId: number;
  adGroupId: number;
  expressionType: string;
  expression: any[];
  bid: number;
  state: string;
}

export default function SBTest() {
  const { selectedAccount } = useSelection();
  const [loadingKeywords, setLoadingKeywords] = useState(false);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [resultKeywords, setResultKeywords] = useState<any>(null);
  const [resultProducts, setResultProducts] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedKeywords, setCopiedKeywords] = useState(false);
  const [copiedProducts, setCopiedProducts] = useState(false);
  const [updatingKeywordId, setUpdatingKeywordId] = useState<number | null>(null);
  const [updatingTargetId, setUpdatingTargetId] = useState<number | null>(null);
  const [updateResult, setUpdateResult] = useState<any>(null);

  const handleFetchSBKeywords = async () => {
    if (!selectedAccount) {
      setError('Seleziona un account prima');
      return;
    }

    setLoadingKeywords(true);
    setError(null);
    setResultKeywords(null);
    setUpdateResult(null);

    try {
      const response = await api.get(`/autopilot/sb-test/keywords/${selectedAccount.id}`);
      setResultKeywords(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Errore nella richiesta');
    } finally {
      setLoadingKeywords(false);
    }
  };

  const handleFetchSBProducts = async () => {
    if (!selectedAccount) {
      setError('Seleziona un account prima');
      return;
    }

    setLoadingProducts(true);
    setError(null);
    setResultProducts(null);
    setUpdateResult(null);

    try {
      const response = await api.get(`/autopilot/sb-test/products/${selectedAccount.id}`);
      setResultProducts(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Errore nella richiesta');
    } finally {
      setLoadingProducts(false);
    }
  };

  const handleUpdateKeywordBid = async (keyword: SBKeyword) => {
    if (!selectedAccount || !resultKeywords?.profile_id_used) {
      setError('Profile ID non disponibile');
      return;
    }

    setUpdatingKeywordId(keyword.keywordId);
    setError(null);
    setUpdateResult(null);

    const newBid = Math.round((keyword.bid + 0.01) * 100) / 100;

    try {
      const response = await api.post(`/autopilot/sb-test/update-keyword-bid/${selectedAccount.id}`, {
        keyword_id: keyword.keywordId,
        ad_group_id: keyword.adGroupId,
        new_bid: newBid,
        profile_id: resultKeywords.profile_id_used
      });
      setUpdateResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Errore nell\'aggiornamento');
    } finally {
      setUpdatingKeywordId(null);
    }
  };

  const handleUpdateTargetBid = async (target: SBTarget) => {
    if (!selectedAccount || !resultProducts?.profile_id_used) {
      setError('Profile ID non disponibile');
      return;
    }

    setUpdatingTargetId(target.targetId);
    setError(null);
    setUpdateResult(null);

    const newBid = Math.round((target.bid + 0.01) * 100) / 100;

    try {
      const response = await api.post(`/autopilot/sb-test/update-target-bid/${selectedAccount.id}`, {
        target_id: target.targetId,
        ad_group_id: target.adGroupId,
        new_bid: newBid,
        profile_id: resultProducts.profile_id_used
      });
      setUpdateResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Errore nell\'aggiornamento');
    } finally {
      setUpdatingTargetId(null);
    }
  };

  const handleCopyKeywords = () => {
    if (resultKeywords) {
      navigator.clipboard.writeText(JSON.stringify(resultKeywords, null, 2));
      setCopiedKeywords(true);
      setTimeout(() => setCopiedKeywords(false), 2000);
    }
  };

  const handleCopyProducts = () => {
    if (resultProducts) {
      navigator.clipboard.writeText(JSON.stringify(resultProducts, null, 2));
      setCopiedProducts(true);
      setTimeout(() => setCopiedProducts(false), 2000);
    }
  };

  const handleDownloadKeywords = () => {
    if (resultKeywords) {
      const blob = new Blob([JSON.stringify(resultKeywords, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sb_keywords_${selectedAccount?.id}_${new Date().toISOString().slice(0,10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  const handleDownloadProducts = () => {
    if (resultProducts) {
      const blob = new Blob([JSON.stringify(resultProducts, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sb_products_${selectedAccount?.id}_${new Date().toISOString().slice(0,10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  const extractKeywords = (): SBKeyword[] => {
    if (!resultKeywords?.step2_sb_keywords) return [];
    const step2 = resultKeywords.step2_sb_keywords;
    
    if (step2.response_json) {
      const data = step2.response_json;
      return Array.isArray(data) ? data : (data.keywords || []);
    }
    
    if (step2.response_body && typeof step2.response_body === 'string') {
      try {
        const parsed = JSON.parse(step2.response_body);
        return Array.isArray(parsed) ? parsed : (parsed.keywords || []);
      } catch {
        return [];
      }
    }
    
    return [];
  };

  const extractTargets = (): SBTarget[] => {
    if (!resultProducts?.step2_sb_products) return [];
    const step2 = resultProducts.step2_sb_products;
    
    if (step2.response_json) {
      const data = step2.response_json;
      return Array.isArray(data) ? data : (data.targets || []);
    }
    
    if (step2.response_body && typeof step2.response_body === 'string') {
      try {
        const parsed = JSON.parse(step2.response_body);
        return Array.isArray(parsed) ? parsed : (parsed.targets || []);
      } catch {
        return [];
      }
    }
    
    return [];
  };

  const getTargetExpression = (target: SBTarget): string => {
    if (!target.expression || !Array.isArray(target.expression)) return '-';
    const expr = target.expression[0];
    if (!expr) return '-';
    if (expr.type === 'asinSameAs') return `ASIN: ${expr.value}`;
    if (expr.type === 'asinCategorySameAs') return `Category: ${expr.value}`;
    if (expr.type === 'asinBrandSameAs') return `Brand: ${expr.value}`;
    return JSON.stringify(expr);
  };

  const keywords = extractKeywords();
  const targets = extractTargets();

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center shadow-lg">
            <FlaskConical size={24} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800">SB Test</h1>
            <p className="text-gray-500">Test endpoint Sponsored Brands</p>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Account Selezionato</h2>
          {selectedAccount ? (
            <div className="flex items-center gap-3 p-4 bg-white rounded-lg border-2 border-[#00D4FF]">
              <div className="w-10 h-10 bg-[#00D4FF] rounded-lg flex items-center justify-center text-white font-bold">
                {selectedAccount.name.charAt(0)}
              </div>
              <div>
                <p className="font-medium text-slate-800">{selectedAccount.name}</p>
                <p className="text-sm text-gray-500">ID: {selectedAccount.id}</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 p-4 bg-cyan-50 rounded-lg border border-cyan-200">
              <AlertCircle className="text-cyan-500" size={20} />
              <p className="text-cyan-700">Seleziona un account dalla pagina Account</p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Test SB Keywords</h2>
            <p className="text-gray-600 mb-4">
              Scarica i dati delle keyword Sponsored Brands dall'API Amazon.
            </p>
            
            <button
              onClick={handleFetchSBKeywords}
              disabled={loadingKeywords || !selectedAccount}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-600 text-white rounded-lg hover:from-purple-600 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loadingKeywords ? (
                <>
                  <Loader2 className="animate-spin" size={18} />
                  Caricamento...
                </>
              ) : (
                <>
                  <Download size={18} />
                  Scarica SB Keywords
                </>
              )}
            </button>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Test SB Products</h2>
            <p className="text-gray-600 mb-4">
              Scarica i dati dei product targets Sponsored Brands dall'API Amazon.
            </p>
            
            <button
              onClick={handleFetchSBProducts}
              disabled={loadingProducts || !selectedAccount}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-cyan-500 to-red-600 text-white rounded-lg hover:from-cyan-600 hover:to-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loadingProducts ? (
                <>
                  <Loader2 className="animate-spin" size={18} />
                  Caricamento...
                </>
              ) : (
                <>
                  <Package size={18} />
                  Scarica SB Products
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4">
            <div className="flex items-center gap-2 text-red-700">
              <AlertCircle size={20} />
              <span className="font-medium">Errore</span>
            </div>
            <p className="text-red-600 mt-2">{error}</p>
          </div>
        )}

        {updateResult && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-4">
            <div className="flex items-center gap-2 text-green-700 mb-2">
              <Check size={20} />
              <span className="font-medium">Risultato Update Bid</span>
            </div>
            <pre className="bg-slate-900 text-green-400 p-4 rounded-lg overflow-x-auto text-sm max-h-[200px] overflow-y-auto">
              {JSON.stringify(updateResult, null, 2)}
            </pre>
          </div>
        )}

        {keywords.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-800">
                Keywords Trovate ({keywords.length})
              </h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDownloadKeywords}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-purple-100 hover:bg-purple-200 text-purple-700 rounded-lg transition-colors"
                >
                  <Download size={16} />
                  Scarica JSON
                </button>
                <button
                  onClick={handleCopyKeywords}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-slate-200 rounded-lg transition-colors"
                >
                  {copiedKeywords ? (
                    <>
                      <Check size={16} className="text-green-600" />
                      <span className="text-green-600">Copiato!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={16} />
                      Copia JSON
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left p-3 font-semibold text-slate-700">Keyword ID</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Campaign ID</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Keyword</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Match Type</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Bid</th>
                    <th className="text-left p-3 font-semibold text-slate-700">State</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Azione</th>
                  </tr>
                </thead>
                <tbody>
                  {keywords.slice(0, 20).map((kw: SBKeyword) => (
                    <tr key={kw.keywordId} className="border-b border-slate-100 hover:bg-gray-50">
                      <td className="p-3 font-mono text-xs">{kw.keywordId}</td>
                      <td className="p-3 font-mono text-xs">{kw.campaignId}</td>
                      <td className="p-3 font-medium">{kw.keywordText}</td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          kw.matchType === 'exact' ? 'bg-green-100 text-green-700' :
                          kw.matchType === 'phrase' ? 'bg-cyan-50 text-[#00A8CC]' :
                          'bg-cyan-100 text-cyan-700'
                        }`}>
                          {kw.matchType}
                        </span>
                      </td>
                      <td className="p-3 font-mono">${kw.bid?.toFixed(2) || '0.00'}</td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          kw.state === 'enabled' ? 'bg-green-100 text-green-700' :
                          kw.state === 'paused' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {kw.state}
                        </span>
                      </td>
                      <td className="p-3">
                        <button
                          onClick={() => handleUpdateKeywordBid(kw)}
                          disabled={updatingKeywordId === kw.keywordId}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded hover:from-green-600 hover:to-emerald-700 disabled:opacity-50 transition-all"
                        >
                          {updatingKeywordId === kw.keywordId ? (
                            <Loader2 className="animate-spin" size={14} />
                          ) : (
                            <>
                              <TrendingUp size={14} />
                              +$0.01
                            </>
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {keywords.length > 20 && (
                <p className="text-gray-500 text-sm mt-3 text-center">
                  Mostrate 20 di {keywords.length} keywords
                </p>
              )}
            </div>
          </div>
        )}

        {targets.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-800">
                Product Targets Trovati ({targets.length})
              </h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDownloadProducts}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-cyan-100 hover:bg-cyan-200 text-cyan-700 rounded-lg transition-colors"
                >
                  <Download size={16} />
                  Scarica JSON
                </button>
                <button
                  onClick={handleCopyProducts}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-slate-200 rounded-lg transition-colors"
                >
                  {copiedProducts ? (
                    <>
                      <Check size={16} className="text-green-600" />
                      <span className="text-green-600">Copiato!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={16} />
                      Copia JSON
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left p-3 font-semibold text-slate-700">Target ID</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Campaign ID</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Expression</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Type</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Bid</th>
                    <th className="text-left p-3 font-semibold text-slate-700">State</th>
                    <th className="text-left p-3 font-semibold text-slate-700">Azione</th>
                  </tr>
                </thead>
                <tbody>
                  {targets.slice(0, 20).map((target: SBTarget) => (
                    <tr key={target.targetId} className="border-b border-slate-100 hover:bg-gray-50">
                      <td className="p-3 font-mono text-xs">{target.targetId}</td>
                      <td className="p-3 font-mono text-xs">{target.campaignId}</td>
                      <td className="p-3 font-medium text-xs max-w-[200px] truncate" title={getTargetExpression(target)}>
                        {getTargetExpression(target)}
                      </td>
                      <td className="p-3">
                        <span className="px-2 py-1 rounded text-xs font-medium bg-indigo-100 text-indigo-700">
                          {target.expressionType || '-'}
                        </span>
                      </td>
                      <td className="p-3 font-mono">${target.bid?.toFixed(2) || '0.00'}</td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          target.state === 'enabled' ? 'bg-green-100 text-green-700' :
                          target.state === 'paused' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {target.state}
                        </span>
                      </td>
                      <td className="p-3">
                        <button
                          onClick={() => handleUpdateTargetBid(target)}
                          disabled={updatingTargetId === target.targetId}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-gradient-to-r from-cyan-500 to-red-600 text-white rounded hover:from-cyan-600 hover:to-red-700 disabled:opacity-50 transition-all"
                        >
                          {updatingTargetId === target.targetId ? (
                            <Loader2 className="animate-spin" size={14} />
                          ) : (
                            <>
                              <TrendingUp size={14} />
                              +$0.01
                            </>
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {targets.length > 20 && (
                <p className="text-gray-500 text-sm mt-3 text-center">
                  Mostrati 20 di {targets.length} targets
                </p>
              )}
            </div>
          </div>
        )}

        {resultKeywords && keywords.length === 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-800">Risposta SB Keywords (Raw)</h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDownloadKeywords}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-purple-100 hover:bg-purple-200 text-purple-700 rounded-lg transition-colors"
                >
                  <Download size={16} />
                  Scarica JSON
                </button>
                <button
                  onClick={handleCopyKeywords}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-slate-200 rounded-lg transition-colors"
                >
                  {copiedKeywords ? (
                    <>
                      <Check size={16} className="text-green-600" />
                      <span className="text-green-600">Copiato!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={16} />
                      Copia JSON
                    </>
                  )}
                </button>
              </div>
            </div>
            <pre className="bg-slate-900 text-green-400 p-4 rounded-lg overflow-x-auto text-sm max-h-[400px] overflow-y-auto">
              {JSON.stringify(resultKeywords, null, 2)}
            </pre>
          </div>
        )}

        {resultProducts && targets.length === 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-800">Risposta SB Products (Raw)</h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDownloadProducts}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-cyan-100 hover:bg-cyan-200 text-cyan-700 rounded-lg transition-colors"
                >
                  <Download size={16} />
                  Scarica JSON
                </button>
                <button
                  onClick={handleCopyProducts}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-slate-200 rounded-lg transition-colors"
                >
                  {copiedProducts ? (
                    <>
                      <Check size={16} className="text-green-600" />
                      <span className="text-green-600">Copiato!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={16} />
                      Copia JSON
                    </>
                  )}
                </button>
              </div>
            </div>
            <pre className="bg-slate-900 text-cyan-400 p-4 rounded-lg overflow-x-auto text-sm max-h-[400px] overflow-y-auto">
              {JSON.stringify(resultProducts, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </Layout>
  );
}
