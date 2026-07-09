import { useState, useEffect } from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import Layout from '../components/Layout';
import PageHeader from '../components/PageHeader';
import api from '../lib/api';

interface ApiLog {
  id: number;
  job_id: string;
  timestamp: string;
  log_type: string;
  endpoint: string;
  source: string;
  status_code: number | null;
  duration_ms: number | null;
}

export default function ExtractorLogs() {
  const [logs, setLogs] = useState<ApiLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const limit = 50;

  useEffect(() => {
    loadLogs();
  }, [page]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/extractor/logs?limit=${limit}&offset=${page * limit}`);
      setLogs(response.data.items);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Failed to load logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const getSourceBadge = (source: string) => {
    if (source === 'oxylabs') {
      return 'bg-purple-100 text-purple-700';
    }
    if (source === 'canopy') {
      return 'bg-blue-100 text-blue-700';
    }
    return 'bg-gray-100 text-gray-700';
  };

  return (
    <Layout>
      <PageHeader
        title="Log API"
        subtitle={`${total} chiamate API registrate`}
      />

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-[#00D4FF]" />
          </div>
        ) : logs.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            <AlertCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>Nessun log API disponibile</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fonte</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tipo</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Endpoint</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Durata</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-600">{formatDate(log.timestamp)}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-1 rounded ${getSourceBadge(log.source)}`}>
                        {log.source}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{log.log_type}</td>
                    <td className="px-4 py-3 text-sm text-gray-600 max-w-xs truncate">{log.endpoint}</td>
                    <td className="px-4 py-3">
                      {log.status_code ? (
                        <span className={`text-xs px-2 py-1 rounded ${
                          log.status_code < 400 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {log.status_code}
                        </span>
                      ) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {log.duration_ms ? `${log.duration_ms}ms` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > limit && (
          <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
            <span className="text-sm text-gray-500">
              Mostrando {page * limit + 1}-{Math.min((page + 1) * limit, total)} di {total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm disabled:opacity-50"
              >
                Precedente
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={(page + 1) * limit >= total}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm disabled:opacity-50"
              >
                Successivo
              </button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
