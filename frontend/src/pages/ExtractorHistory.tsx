import { useState, useEffect } from 'react';
import { Loader2, CheckCircle, XCircle, Clock, AlertCircle, FileText, Package, Search, Download, Eye, X, Check, Copy } from 'lucide-react';
import Layout from '../components/Layout';
import PageHeader from '../components/PageHeader';
import api from '../lib/api';
import * as XLSX from 'xlsx';

interface Job {
  id: string;
  seed_keywords: string[];
  extraction_type: string;
  category_mode: string;
  status: string;
  progress: number;
  asins_found: number;
  keywords_found: number;
  started_at: string;
  completed_at: string | null;
  error: string | null;
}

interface JobAsin {
  asin: string;
  title: string;
}

interface JobKeyword {
  keyword: string;
}

export default function ExtractorHistory() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailsModal, setDetailsModal] = useState<{ job: Job; type: 'asins' | 'keywords' } | null>(null);
  const [detailsData, setDetailsData] = useState<JobAsin[] | JobKeyword[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      const response = await api.get('/extractor/jobs?limit=50');
      setJobs(response.data.items);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const calculateDuration = (start: string, end: string | null) => {
    if (!end) return '-';
    const startDate = new Date(start);
    const endDate = new Date(end);
    const diffMs = endDate.getTime() - startDate.getTime();
    const minutes = Math.floor(diffMs / 60000);
    const seconds = Math.floor((diffMs % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
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
            Running
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium">
            <XCircle size={12} />
            Failed
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

  const openDetails = async (job: Job, type: 'asins' | 'keywords') => {
    setDetailsModal({ job, type });
    setDetailsLoading(true);
    try {
      const endpoint = type === 'asins' ? `/extractor/asins?job_id=${job.id}&limit=1000` : `/extractor/keywords?job_id=${job.id}&limit=1000`;
      const response = await api.get(endpoint);
      setDetailsData(response.data.items);
    } catch (error) {
      console.error('Failed to load details:', error);
      setDetailsData([]);
    } finally {
      setDetailsLoading(false);
    }
  };

  const closeDetails = () => {
    setDetailsModal(null);
    setDetailsData([]);
    setCopied(false);
  };

  const downloadXLSX = (job: Job, type: 'asins' | 'keywords') => {
    const seedName = job.seed_keywords[0]?.replace(/\s+/g, '_') || 'export';
    const date = new Date().toISOString().split('T')[0];
    const filename = `${type}_${seedName}_${date}.xlsx`;

    let data: (string | number)[][] = [];
    if (type === 'asins') {
      data = [['ASIN', 'TITOLO'], ...(detailsData as JobAsin[]).map(a => [a.asin, a.title || ''])];
    } else {
      data = [['KWS'], ...(detailsData as JobKeyword[]).map(k => [k.keyword])];
    }

    const ws = XLSX.utils.aoa_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, type === 'asins' ? 'ASINs' : 'Keywords');
    XLSX.writeFile(wb, filename);
  };

  const downloadJobData = async (job: Job, type: 'asins' | 'keywords') => {
    try {
      const endpoint = type === 'asins' ? `/extractor/asins?job_id=${job.id}&limit=10000` : `/extractor/keywords?job_id=${job.id}&limit=10000`;
      const response = await api.get(endpoint);
      const data = response.data.items;

      const seedName = job.seed_keywords[0]?.replace(/\s+/g, '_') || 'export';
      const date = new Date().toISOString().split('T')[0];
      const filename = `${type}_${seedName}_${date}.csv`;

      let csv = '';
      if (type === 'asins') {
        csv = 'ASIN,TITOLO\n' + data.map((a: any) => `${a.asin},"${(a.title || '').replace(/"/g, '""')}"`).join('\n');
      } else {
        csv = 'KWS\n' + data.map((k: any) => `"${k.keyword.replace(/"/g, '""')}"`).join('\n');
      }

      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
    } catch (error) {
      console.error('Failed to download:', error);
    }
  };

  const copyAll = async () => {
    try {
      let text = '';
      if (detailsModal?.type === 'asins') {
        text = (detailsData as JobAsin[]).map(a => a.asin).join('\n');
      } else {
        text = (detailsData as JobKeyword[]).map(k => k.keyword).join('\n');
      }
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  return (
    <Layout>
      <PageHeader
        title="Storico Estrazioni"
        subtitle="Visualizza e scarica i risultati delle estrazioni passate"
      />

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-[#00D4FF]" />
        </div>
      ) : jobs.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 py-12 text-center text-gray-500">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p>Nessuna estrazione eseguita</p>
        </div>
      ) : (
        <div className="space-y-4">
          {jobs.map((job) => (
            <div key={job.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-[#00D4FF]/10 rounded-xl flex items-center justify-center flex-shrink-0">
                  <FileText className="w-6 h-6 text-[#00D4FF]" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="font-medium text-[#0F1D32]">
                        {job.seed_keywords.slice(0, 3).join(', ')}
                      </h3>
                      {job.seed_keywords.length > 3 && (
                        <span className="inline-block mt-1 px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
                          +{job.seed_keywords.length - 3} altre
                        </span>
                      )}
                      <p className="text-sm text-gray-500 mt-1">
                        Iniziato {formatDateTime(job.started_at)}
                      </p>
                      {job.error && (
                        <p className="text-sm text-red-600 mt-1">{job.error}</p>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-6 text-sm">
                      <div className="flex items-center gap-1.5 text-gray-600">
                        <Package size={16} className="text-gray-400" />
                        <span className="font-medium text-[#00D4FF]">{job.asins_found.toLocaleString()}</span>
                        <span className="text-gray-400">ASINs</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-gray-600">
                        <Search size={16} className="text-gray-400" />
                        <span className="font-medium text-purple-600">{job.keywords_found.toLocaleString()}</span>
                        <span className="text-gray-400">Keywords</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-gray-600">
                        <Clock size={16} className="text-gray-400" />
                        <span>{calculateDuration(job.started_at, job.completed_at)}</span>
                      </div>
                      {getStatusBadge(job.status)}
                    </div>
                  </div>
                  
                  {job.status === 'processing' && (
                    <div className="mt-3">
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 mt-1">{job.progress}%</span>
                    </div>
                  )}
                  
                  {job.status === 'completed' && (job.asins_found > 0 || job.keywords_found > 0) && (
                    <div className="mt-4 flex items-center gap-3">
                      {job.asins_found > 0 && (
                        <>
                          <button
                            onClick={() => openDetails(job, 'asins')}
                            className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition"
                          >
                            <Eye size={14} />
                            Vedi ASINs ({job.asins_found.toLocaleString()})
                          </button>
                          <button
                            onClick={() => downloadJobData(job, 'asins')}
                            className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition"
                          >
                            <Download size={14} />
                            Scarica ASINs
                          </button>
                        </>
                      )}
                      {job.keywords_found > 0 && (
                        <>
                          <button
                            onClick={() => openDetails(job, 'keywords')}
                            className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition"
                          >
                            <Eye size={14} />
                            Vedi Keywords ({job.keywords_found.toLocaleString()})
                          </button>
                          <button
                            onClick={() => downloadJobData(job, 'keywords')}
                            className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition"
                          >
                            <Download size={14} />
                            Scarica Keywords
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {detailsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[80vh] flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-lg text-[#0F1D32]">
                  {detailsModal.type === 'asins' ? 'ASINs' : 'Keywords'}
                </h3>
                <p className="text-sm text-gray-500">
                  {detailsModal.job.seed_keywords.slice(0, 3).join(', ')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={copyAll}
                  className={`px-3 py-1.5 border rounded-lg text-sm transition flex items-center gap-1.5 ${
                    copied 
                      ? 'border-green-500 text-green-600 bg-green-50' 
                      : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  {copied ? 'Copiato!' : 'Copia Tutto'}
                </button>
                <button
                  onClick={() => downloadXLSX(detailsModal.job, detailsModal.type)}
                  className="px-3 py-1.5 bg-[#00D4FF] text-white rounded-lg text-sm hover:bg-[#00A8CC] transition"
                >
                  Scarica XLSX
                </button>
                <button
                  onClick={closeDetails}
                  className="p-2 text-gray-400 hover:text-gray-600 transition"
                >
                  <X size={20} />
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-auto p-4">
              {detailsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-[#00D4FF]" />
                </div>
              ) : detailsModal.type === 'asins' ? (
                <table className="w-full">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ASIN</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Titolo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {(detailsData as JobAsin[]).map((item, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-mono text-sm">{item.asin}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{item.title}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <table className="w-full">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">KWS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {(detailsData as JobKeyword[]).map((item, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm">{item.keyword}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
