import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, AlertCircle, RefreshCw, Loader2 } from 'lucide-react';
import Layout from '../components/Layout';
import PageHeader from '../components/PageHeader';
import api from '../lib/api';

interface ApiStatus {
  oxylabs: { status: string; message?: string };
  canopy: { status: string; message?: string };
}

export default function ExtractorStatus() {
  const [status, setStatus] = useState<ApiStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    setChecking(true);
    try {
      const response = await api.get('/extractor/status');
      setStatus(response.data);
    } catch (error) {
      console.error('Failed to check status:', error);
    } finally {
      setLoading(false);
      setChecking(false);
    }
  };

  const getStatusIcon = (apiStatus: { status: string }) => {
    if (apiStatus.status === 'connected') {
      return <CheckCircle className="w-8 h-8 text-green-500" />;
    }
    if (apiStatus.status === 'not_configured') {
      return <AlertCircle className="w-8 h-8 text-cyan-500" />;
    }
    return <XCircle className="w-8 h-8 text-red-500" />;
  };

  const getStatusText = (apiStatus: { status: string }) => {
    if (apiStatus.status === 'connected') return 'Connesso';
    if (apiStatus.status === 'not_configured') return 'Non configurato';
    return 'Errore';
  };

  const getStatusColor = (apiStatus: { status: string }) => {
    if (apiStatus.status === 'connected') return 'border-green-200 bg-green-50';
    if (apiStatus.status === 'not_configured') return 'border-cyan-200 bg-cyan-50';
    return 'border-red-200 bg-red-50';
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-[#00D4FF]" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <PageHeader
        title="Stato API"
        subtitle="Verifica la connessione alle API di estrazione"
        action={
          <button
            onClick={checkStatus}
            disabled={checking}
            className="flex items-center gap-2 px-4 py-2.5 bg-[#00D4FF] text-white rounded-lg font-medium hover:bg-[#00A8CC] disabled:opacity-50 transition"
          >
            <RefreshCw size={18} className={checking ? 'animate-spin' : ''} />
            Verifica Connessione
          </button>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className={`rounded-xl border-2 p-6 ${status ? getStatusColor(status.oxylabs) : 'border-gray-200 bg-white'}`}>
          <div className="flex items-start gap-4">
            {status && getStatusIcon(status.oxylabs)}
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-[#0F1D32]">Oxylabs</h3>
              <p className="text-sm text-gray-500 mb-2">Web Scraper API</p>
              {status && (
                <>
                  <p className={`text-sm font-medium ${
                    status.oxylabs.status === 'connected' ? 'text-green-600' :
                    status.oxylabs.status === 'not_configured' ? 'text-cyan-600' : 'text-red-600'
                  }`}>
                    {getStatusText(status.oxylabs)}
                  </p>
                  {status.oxylabs.message && (
                    <p className="mt-2 text-sm text-gray-600">{status.oxylabs.message}</p>
                  )}
                </>
              )}
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-xs text-gray-500">
              Variabili ambiente richieste: <code className="bg-gray-100 px-1 rounded">OXYLABS_USER</code>, <code className="bg-gray-100 px-1 rounded">OXYLABS_PASS</code>
            </p>
          </div>
        </div>

        <div className={`rounded-xl border-2 p-6 ${status ? getStatusColor(status.canopy) : 'border-gray-200 bg-white'}`}>
          <div className="flex items-start gap-4">
            {status && getStatusIcon(status.canopy)}
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-[#0F1D32]">Canopy</h3>
              <p className="text-sm text-gray-500 mb-2">GraphQL API</p>
              {status && (
                <>
                  <p className={`text-sm font-medium ${
                    status.canopy.status === 'connected' ? 'text-green-600' :
                    status.canopy.status === 'not_configured' ? 'text-cyan-600' : 'text-red-600'
                  }`}>
                    {getStatusText(status.canopy)}
                  </p>
                  {status.canopy.message && (
                    <p className="mt-2 text-sm text-gray-600">{status.canopy.message}</p>
                  )}
                </>
              )}
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-xs text-gray-500">
              Variabile ambiente richiesta: <code className="bg-gray-100 px-1 rounded">CANOPY_API_KEY</code>
            </p>
          </div>
        </div>
      </div>

      <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-[#0F1D32] mb-4">Informazioni API</h3>
        <div className="space-y-4 text-sm text-gray-600">
          <div>
            <h4 className="font-medium text-[#0F1D32]">Oxylabs Web Scraper</h4>
            <p>Utilizzato per ricerche Amazon e estrazione dati prodotto. Supporta ricerca paginata e filtri per categoria.</p>
            <a href="https://oxylabs.io/products/scraper-api" target="_blank" rel="noopener noreferrer" className="text-[#00D4FF] hover:underline">
              Documentazione Oxylabs
            </a>
          </div>
          <div>
            <h4 className="font-medium text-[#0F1D32]">Canopy GraphQL API</h4>
            <p>Utilizzato per dettagli prodotto, prodotti correlati e suggerimenti autocomplete.</p>
            <a href="https://www.canopyapi.co/" target="_blank" rel="noopener noreferrer" className="text-[#00D4FF] hover:underline">
              Documentazione Canopy
            </a>
          </div>
        </div>
      </div>
    </Layout>
  );
}
