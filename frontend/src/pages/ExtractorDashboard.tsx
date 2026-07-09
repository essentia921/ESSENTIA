import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, Search, TrendingUp, Clock, ArrowRight, Sparkles, Loader2, CheckCircle, XCircle } from 'lucide-react';
import Layout from '../components/Layout';
import PageHeader from '../components/PageHeader';
import api from '../lib/api';

interface RecentAsin {
  asin: string;
  title: string;
}

interface RecentJob {
  id: string;
  seed_keywords: string[];
  started_at: string;
  status: string;
  asins_found: number;
  keywords_found: number;
}

interface DashboardData {
  total_asins: number;
  total_keywords: number;
  total_jobs: number;
  latest_job: {
    id: string;
    status: string;
    started_at: string;
    completed_at: string | null;
  } | null;
  recent_asins: RecentAsin[];
  recent_keywords: string[];
  recent_jobs: RecentJob[];
}

interface CurrentJob {
  id: string;
  seed_keywords: string[];
  status: string;
  progress: number;
  asins_found: number;
  keywords_found: number;
}

export default function ExtractorDashboard() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [currentJob, setCurrentJob] = useState<CurrentJob | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [dashboardRes, currentRes] = await Promise.all([
        api.get('/extractor/dashboard'),
        api.get('/extractor/current')
      ]);
      setDashboard(dashboardRes.data);
      setCurrentJob(currentRes.data);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  };

  const formatDateTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium">
            <CheckCircle size={12} />
            Completed
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
            <Loader2 size={12} className="animate-spin" />
            In Progress
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium">
            <XCircle size={12} />
            Error
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 bg-gray-100 text-gray-700 rounded-full text-xs font-medium">
            {status}
          </span>
        );
    }
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
        title="Dashboard"
        subtitle="Panoramica delle tue attività di estrazione dati Amazon"
        action={
          <button
            onClick={() => navigate('/extractor/new')}
            className="flex items-center gap-2 px-4 py-2.5 bg-[#00D4FF] text-white rounded-lg font-medium hover:bg-[#00A8CC] transition"
          >
            <Sparkles size={18} />
            Nuova Estrazione
          </button>
        }
      />

      {currentJob && currentJob.status === 'processing' && (
        <div className="bg-cyan-50 border-2 border-[#00D4FF] rounded-xl p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-[#00D4FF]" />
              <span className="font-medium text-[#0F1D32]">Estrazione in corso...</span>
            </div>
            <span className="text-sm text-gray-600">{currentJob.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-[#00D4FF] h-2 rounded-full transition-all duration-500"
              style={{ width: `${currentJob.progress}%` }}
            />
          </div>
          <div className="mt-3 flex items-center gap-4 text-sm text-gray-600">
            <span>ASINs: {currentJob.asins_found}</span>
            <span>Keywords: {currentJob.keywords_found}</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Totale ASINs</p>
              <p className="text-3xl font-bold text-[#0F1D32] mt-1">
                {dashboard?.total_asins?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-gray-400 mt-1">Prodotti estratti</p>
            </div>
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
              <Database className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Totale Keywords</p>
              <p className="text-3xl font-bold text-[#0F1D32] mt-1">
                {dashboard?.total_keywords?.toLocaleString() || 0}
              </p>
              <p className="text-xs text-gray-400 mt-1">Termini unici</p>
            </div>
            <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
              <Search className="w-6 h-6 text-purple-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Estrazioni</p>
              <p className="text-3xl font-bold text-[#0F1D32] mt-1">
                {dashboard?.total_jobs || 0}
              </p>
              <p className="text-xs text-gray-400 mt-1">Job eseguiti</p>
            </div>
            <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Ultima Esecuzione</p>
              <p className="text-2xl font-bold text-[#0F1D32] mt-1">
                {dashboard?.latest_job ? formatDate(dashboard.latest_job.completed_at || dashboard.latest_job.started_at) : '-'}
              </p>
              <p className="text-xs text-gray-400 mt-1">Estrazione più recente</p>
            </div>
            <div className="w-12 h-12 bg-cyan-100 rounded-xl flex items-center justify-center">
              <Clock className="w-6 h-6 text-cyan-600" />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[#0F1D32]">ASINs Recenti</h2>
              <p className="text-sm text-gray-500">Ultimi identificatori prodotto estratti</p>
            </div>
            <button
              onClick={() => navigate('/extractor/asins')}
              className="text-[#00D4FF] hover:text-[#00A8CC] text-sm font-medium flex items-center gap-1"
            >
              Vedi Tutti <ArrowRight size={14} />
            </button>
          </div>
          <div className="p-4 space-y-3">
            {dashboard?.recent_asins && dashboard.recent_asins.length > 0 ? (
              dashboard.recent_asins.slice(0, 5).map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-sm font-medium text-[#0F1D32]">{item.asin}</p>
                    <p className="text-xs text-gray-500 truncate">{item.title}</p>
                  </div>
                  <a
                    href={`https://www.amazon.com/dp/${item.asin}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-2 px-3 py-1.5 text-xs text-gray-600 hover:text-[#00D4FF] border border-gray-200 rounded-lg hover:border-[#00D4FF] transition flex items-center gap-1"
                  >
                    search
                  </a>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-sm text-center py-4">Nessun ASIN estratto</p>
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[#0F1D32]">Keywords Recenti</h2>
              <p className="text-sm text-gray-500">Ultimi termini di ricerca estratti</p>
            </div>
            <button
              onClick={() => navigate('/extractor/keywords')}
              className="text-[#00D4FF] hover:text-[#00A8CC] text-sm font-medium flex items-center gap-1"
            >
              Vedi Tutti <ArrowRight size={14} />
            </button>
          </div>
          <div className="p-4">
            {dashboard?.recent_keywords && dashboard.recent_keywords.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {dashboard.recent_keywords.slice(0, 15).map((kw, idx) => (
                  <span
                    key={idx}
                    className="px-3 py-1.5 bg-cyan-50 border border-[#00D4FF]/20 text-[#0F1D32] rounded-lg text-sm"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm text-center py-4">Nessuna keyword estratta</p>
            )}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-[#0F1D32]">Job Recenti</h2>
            <p className="text-sm text-gray-500">Il tuo storico estrazioni</p>
          </div>
          <button
            onClick={() => navigate('/extractor/history')}
            className="text-[#00D4FF] hover:text-[#00A8CC] text-sm font-medium flex items-center gap-1"
          >
            Vedi Tutti <ArrowRight size={14} />
          </button>
        </div>
        <div className="divide-y divide-gray-100">
          {dashboard?.recent_jobs && dashboard.recent_jobs.length > 0 ? (
            dashboard.recent_jobs.slice(0, 5).map((job) => (
              <div key={job.id} className="p-4 flex items-center justify-between hover:bg-gray-50">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                    <Database size={18} className="text-gray-500" />
                  </div>
                  <div>
                    <p className="font-medium text-[#0F1D32]">
                      {job.seed_keywords.slice(0, 3).join(', ')}
                      {job.seed_keywords.length > 3 && ` +${job.seed_keywords.length - 3} altri`}
                    </p>
                    <p className="text-xs text-gray-500">{formatDateTime(job.started_at)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right text-sm">
                    <span className="text-[#00D4FF] font-medium">{job.asins_found}</span>
                    <span className="text-gray-400"> ASINs</span>
                    <span className="mx-2 text-gray-300">·</span>
                    <span className="text-purple-600 font-medium">{job.keywords_found}</span>
                    <span className="text-gray-400"> KWs</span>
                  </div>
                  {getStatusBadge(job.status)}
                </div>
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-sm text-center py-8">Nessun job eseguito</p>
          )}
        </div>
      </div>
    </Layout>
  );
}
