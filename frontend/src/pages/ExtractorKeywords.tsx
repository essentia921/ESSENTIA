import { useState, useEffect } from 'react';
import { Download, Search, Loader2, Copy, FileSpreadsheet, ChevronUp, ChevronDown } from 'lucide-react';
import Layout from '../components/Layout';
import PageHeader from '../components/PageHeader';
import api from '../lib/api';

interface Keyword {
  id: number;
  keyword: string;
  source: string;
  source_asin: string | null;
  category: string | null;
  relevance_score: number | null;
  is_seed: boolean;
  extracted_at: string;
}

interface Job {
  id: string;
  extraction_type: string;
  status: string;
  keywords_found: number;
}

type SortField = 'keyword' | 'score' | 'extracted_at';
type SortDirection = 'asc' | 'desc';

export default function ExtractorKeywords() {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [page, setPage] = useState(0);
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [lastJobId, setLastJobId] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const limit = 20;

  useEffect(() => {
    loadLastJobId();
  }, []);

  useEffect(() => {
    if (lastJobId !== null) {
      loadKeywords();
    }
  }, [page, lastJobId]);

  const loadLastJobId = async () => {
    try {
      const response = await api.get('/extractor/jobs?limit=20&offset=0');
      const jobs: Job[] = response.data.items;
      const lastCompleted = jobs.find(
        (j: Job) => j.status === 'completed' && (j.extraction_type === 'keywords' || j.keywords_found > 0)
      );
      if (lastCompleted) {
        setLastJobId(lastCompleted.id);
      } else {
        setLastJobId('');
        setLoading(false);
      }
    } catch (error) {
      console.error('Failed to load jobs:', error);
      setLastJobId('');
      setLoading(false);
    }
  };

  const loadKeywords = async () => {
    setLoading(true);
    try {
      const jobParam = lastJobId ? `&job_id=${lastJobId}` : '';
      const response = await api.get(`/extractor/keywords?limit=${limit}&offset=${page * limit}${jobParam}`);
      setKeywords(response.data.items);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Failed to load keywords:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAllKeywords = async (): Promise<Keyword[]> => {
    const jobParam = lastJobId ? `&job_id=${lastJobId}` : '';
    const response = await api.get(`/extractor/keywords?limit=100000&offset=0${jobParam}`);
    const all: Keyword[] = response.data.items;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return all.filter(k => k.keyword.toLowerCase().includes(q));
    }
    return all;
  };

  const copyAllKeywords = async () => {
    try {
      setCopyStatus('loading');
      setIsExporting(true);
      const allKws = await fetchAllKeywords();
      const kwList = allKws.map((k: Keyword) => k.keyword).join('\n');
      await navigator.clipboard.writeText(kwList);
      setCopyStatus('done');
      setTimeout(() => setCopyStatus(null), 2000);
    } catch (error) {
      console.error('Failed to copy all keywords:', error);
      setCopyStatus(null);
    } finally {
      setIsExporting(false);
    }
  };

  const copyKeyword = (keyword: string) => {
    navigator.clipboard.writeText(keyword);
  };

  const formatScore = (kw: Keyword) => {
    if (kw.is_seed) {
      return <span className="text-lg">🎯</span>;
    }
    const score = kw.relevance_score || 0;
    const formattedScore = Math.round(score);
    const isHighScore = score >= 8.0;
    return (
      <span className={`font-medium ${isHighScore ? 'text-green-600' : 'text-green-600/70'}`}>
        {formattedScore}/10
      </span>
    );
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('it-IT', {
      day: 'numeric',
      month: 'numeric',
      year: 'numeric'
    });
  };

  const exportCSV = async () => {
    try {
      setIsExporting(true);
      const allKws = await fetchAllKeywords();
      const headers = ['Keyword', 'Score', 'Data'];
      const rows = allKws.map(k => [
        `"${k.keyword.replace(/"/g, '""')}"`,
        k.is_seed ? 'seed' : `${Math.round(k.relevance_score || 0)}/10`,
        formatDate(k.extracted_at)
      ]);
      const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `keywords_export_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export CSV:', error);
    } finally {
      setIsExporting(false);
    }
  };

  const exportXLSX = async () => {
    try {
      setIsExporting(true);
      const allKws = await fetchAllKeywords();
      const headers = ['Keyword', 'Score', 'Data'];
      const rows = allKws.map(k => [
        k.keyword,
        k.is_seed ? 'seed' : `${Math.round(k.relevance_score || 0)}/10`,
        formatDate(k.extracted_at)
      ]);
      const escapeXml = (s: string) =>
        s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
      xml += '<?mso-application progid="Excel.Sheet"?>\n';
      xml += '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n';
      xml += '<Worksheet ss:Name="Keywords"><Table>\n';
      xml += '<Row>' + headers.map(h => `<Cell><Data ss:Type="String">${escapeXml(h)}</Data></Cell>`).join('') + '</Row>\n';
      for (const row of rows) {
        xml += '<Row>' + row.map(c => `<Cell><Data ss:Type="String">${escapeXml(c)}</Data></Cell>`).join('') + '</Row>\n';
      }
      xml += '</Table></Worksheet></Workbook>';
      const blob = new Blob([xml], { type: 'application/vnd.ms-excel' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `keywords_export_${new Date().toISOString().split('T')[0]}.xls`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export XLSX:', error);
    } finally {
      setIsExporting(false);
    }
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredKeywords.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredKeywords.map(k => k.id)));
    }
  };

  const toggleSelect = (id: number) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection(field === 'score' ? 'desc' : 'asc');
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ChevronUp size={14} className="text-gray-300" />;
    return sortDirection === 'asc' 
      ? <ChevronUp size={14} className="text-[#00D4FF]" />
      : <ChevronDown size={14} className="text-[#00D4FF]" />;
  };

  const filteredKeywords = keywords
    .filter(k => k.keyword.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort((a, b) => {
      if (sortField === 'score') {
        if (a.is_seed && !b.is_seed) return -1;
        if (!a.is_seed && b.is_seed) return 1;
        if (a.is_seed && b.is_seed) return 0;
        
        const aScore = a.relevance_score || 0;
        const bScore = b.relevance_score || 0;
        return sortDirection === 'desc' ? bScore - aScore : aScore - bScore;
      }
      
      if (sortField === 'keyword') {
        return sortDirection === 'asc' 
          ? a.keyword.localeCompare(b.keyword) 
          : b.keyword.localeCompare(a.keyword);
      }
      
      if (sortField === 'extracted_at') {
        const aDate = new Date(a.extracted_at).getTime();
        const bDate = new Date(b.extracted_at).getTime();
        return sortDirection === 'asc' ? aDate - bDate : bDate - aDate;
      }
      
      return 0;
    });

  return (
    <Layout>
      <PageHeader
        title="Keywords"
        subtitle="Browse and export all extracted keywords from product titles"
      />

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cerca keywords..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none text-sm"
            />
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={copyAllKeywords}
              disabled={isExporting}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition text-sm disabled:opacity-50"
            >
              {copyStatus === 'loading' ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Copy size={16} />
              )}
              {copyStatus === 'done' ? 'Copiati!' : 'Copia Tutti'}
            </button>
            <button
              onClick={exportCSV}
              disabled={isExporting}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition text-sm disabled:opacity-50"
            >
              {isExporting ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
              CSV
            </button>
            <button
              onClick={exportXLSX}
              disabled={isExporting}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition text-sm disabled:opacity-50"
            >
              {isExporting ? <Loader2 size={16} className="animate-spin" /> : <FileSpreadsheet size={16} />}
              XLSX
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-[#00D4FF]" />
          </div>
        ) : filteredKeywords.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            Nessuna keyword trovata
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
                <tr>
                  <th className="px-4 py-3 text-left w-10">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === filteredKeywords.length && filteredKeywords.length > 0}
                      onChange={toggleSelectAll}
                      className="w-4 h-4 rounded border-gray-300 text-[#00D4FF] focus:ring-[#00D4FF]"
                    />
                  </th>
                  <th 
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                    onClick={() => handleSort('keyword')}
                  >
                    <div className="flex items-center gap-1">
                      Keyword <SortIcon field="keyword" />
                    </div>
                  </th>
                  <th 
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                    onClick={() => handleSort('score')}
                  >
                    <div className="flex items-center gap-1">
                      Score <SortIcon field="score" />
                    </div>
                  </th>
                  <th 
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                    onClick={() => handleSort('extracted_at')}
                  >
                    <div className="flex items-center gap-1">
                      Estratto <SortIcon field="extracted_at" />
                    </div>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredKeywords.map((kw) => (
                  <tr key={kw.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(kw.id)}
                        onChange={() => toggleSelect(kw.id)}
                        className="w-4 h-4 rounded border-gray-300 text-[#00D4FF] focus:ring-[#00D4FF]"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-[#0F1D32]">
                        {kw.keyword}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {formatScore(kw)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-500">
                        {formatDate(kw.extracted_at)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => copyKeyword(kw.keyword)}
                        className="p-2 text-gray-400 hover:text-[#00D4FF] hover:bg-gray-100 rounded transition"
                        title="Copia keyword"
                      >
                        <Copy size={16} />
                      </button>
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
              Mostrando {page * limit + 1}-{Math.min((page + 1) * limit, total)} di {total.toLocaleString()}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm disabled:opacity-50 hover:bg-gray-50"
              >
                Precedente
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={(page + 1) * limit >= total}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm disabled:opacity-50 hover:bg-gray-50"
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
