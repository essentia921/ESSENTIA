import { useState, useEffect } from 'react';
import { Download, Search, Loader2, ExternalLink, Copy, ChevronUp, ChevronDown, FileSpreadsheet } from 'lucide-react';
import Layout from '../components/Layout';
import PageHeader from '../components/PageHeader';
import api from '../lib/api';

interface Asin {
  id: number;
  asin: string;
  title: string;
  brand: string | null;
  price: string | null;
  rating: number | null;
  ratings_total: number | null;
  bsr: number | null;
  image_url: string | null;
  format: string | null;
  source: string;
  seed_keyword: string;
  extracted_at: string;
}

type SortField = 'asin' | 'title' | 'price' | 'rating' | 'ratings_total';
type SortDirection = 'asc' | 'desc';

export default function ExtractorAsins() {
  const [asins, setAsins] = useState<Asin[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [page, setPage] = useState(0);
  const [sortField, setSortField] = useState<SortField>('asin');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [lastJobId, setLastJobId] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const limit = 20;

  useEffect(() => {
    loadLastJob();
  }, []);

  useEffect(() => {
    if (lastJobId !== null) {
      loadAsins();
    }
  }, [page, lastJobId]);

  const loadLastJob = async () => {
    try {
      const response = await api.get('/extractor/jobs?limit=1&offset=0');
      const jobs = response.data.items;
      const completedJob = jobs.find((j: any) => j.status === 'completed' && (j.extraction_type === 'asins' || j.extraction_type === 'both'));
      if (completedJob) {
        setLastJobId(completedJob.id);
      } else {
        if (jobs.length > 0 && jobs[0].status === 'completed') {
          setLastJobId(jobs[0].id);
        } else {
          const allJobsResp = await api.get('/extractor/jobs?limit=50&offset=0');
          const allJobs = allJobsResp.data.items;
          const found = allJobs.find((j: any) => j.status === 'completed');
          if (found) {
            setLastJobId(found.id);
          } else {
            setLastJobId('');
            setLoading(false);
          }
        }
      }
    } catch (error) {
      console.error('Failed to load last job:', error);
      setLastJobId('');
      setLoading(false);
    }
  };

  const loadAsins = async () => {
    setLoading(true);
    try {
      const jobParam = lastJobId ? `&job_id=${lastJobId}` : '';
      const response = await api.get(`/extractor/asins?limit=${limit}&offset=${page * limit}${jobParam}`);
      setAsins(response.data.items);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Failed to load ASINs:', error);
    } finally {
      setLoading(false);
    }
  };

  const copyAllAsins = async () => {
    try {
      setCopyStatus('loading');
      const jobParam = lastJobId ? `&job_id=${lastJobId}` : '';
      const response = await api.get(`/extractor/asins?limit=100000&offset=0${jobParam}`);
      const allItems: Asin[] = response.data.items;
      const asinList = allItems.map(a => a.asin).join('\n');
      await navigator.clipboard.writeText(asinList);
      setCopyStatus('done');
      setTimeout(() => setCopyStatus(null), 2000);
    } catch (error) {
      console.error('Failed to copy all ASINs:', error);
      setCopyStatus(null);
    }
  };

  const copyAsin = (asin: string) => {
    navigator.clipboard.writeText(asin);
  };

  const formatPrice = (price: string | null): string => {
    if (!price) return '-';
    const num = parseFloat(price.replace(/[^0-9.]/g, ''));
    if (isNaN(num)) return price;
    return `$${num.toFixed(2)}`;
  };

  const exportCSV = async () => {
    try {
      const jobParam = lastJobId ? `&job_id=${lastJobId}` : '';
      const response = await api.get(`/extractor/asins?limit=100000&offset=0${jobParam}`);
      const allItems: Asin[] = response.data.items;

      const headers = ['ASIN', 'Titolo', 'Prezzo', 'Rating', 'Recensioni', 'BSR', 'Brand', 'Formato'];
      const rows = allItems.map(a => [
        a.asin,
        `"${(a.title || '').replace(/"/g, '""')}"`,
        formatPrice(a.price),
        a.rating?.toString() || '',
        a.ratings_total?.toString() || '',
        a.bsr?.toString() || '',
        a.brand || '',
        a.format || ''
      ]);

      const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `asins_export_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
    } catch (error) {
      console.error('Failed to export CSV:', error);
    }
  };

  const exportXLSX = async () => {
    try {
      const jobParam = lastJobId ? `&job_id=${lastJobId}` : '';
      const response = await api.get(`/extractor/asins?limit=100000&offset=0${jobParam}`);
      const allItems: Asin[] = response.data.items;

      const headers = ['ASIN', 'Titolo', 'Prezzo', 'Rating', 'Recensioni', 'BSR', 'Brand', 'Formato'];
      const rows = allItems.map(a => [
        a.asin,
        a.title || '',
        formatPrice(a.price),
        a.rating?.toString() || '',
        a.ratings_total?.toString() || '',
        a.bsr?.toString() || '',
        a.brand || '',
        a.format || ''
      ]);

      const escapeXml = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
      xml += '<?mso-application progid="Excel.Sheet"?>\n';
      xml += '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n';
      xml += '<Worksheet ss:Name="ASINs"><Table>\n';
      xml += '<Row>' + headers.map(h => `<Cell><Data ss:Type="String">${escapeXml(h)}</Data></Cell>`).join('') + '</Row>\n';
      for (const row of rows) {
        xml += '<Row>' + row.map(c => `<Cell><Data ss:Type="String">${escapeXml(c)}</Data></Cell>`).join('') + '</Row>\n';
      }
      xml += '</Table></Worksheet></Workbook>';

      const blob = new Blob([xml], { type: 'application/vnd.ms-excel' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `asins_export_${new Date().toISOString().split('T')[0]}.xls`;
      a.click();
    } catch (error) {
      console.error('Failed to export XLSX:', error);
    }
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredAsins.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredAsins.map(a => a.id)));
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
      setSortDirection('asc');
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ChevronUp size={14} className="text-gray-300" />;
    return sortDirection === 'asc' 
      ? <ChevronUp size={14} className="text-[#00D4FF]" />
      : <ChevronDown size={14} className="text-[#00D4FF]" />;
  };

  const filteredAsins = asins
    .filter(a =>
      a.asin.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (a.brand && a.brand.toLowerCase().includes(searchQuery.toLowerCase()))
    )
    .sort((a, b) => {
      let aVal: any, bVal: any;
      switch (sortField) {
        case 'asin': aVal = a.asin; bVal = b.asin; break;
        case 'title': aVal = a.title; bVal = b.title; break;
        case 'price': 
          aVal = parseFloat((a.price || '0').replace(/[^0-9.,]/g, '').replace(',', '.')) || 0;
          bVal = parseFloat((b.price || '0').replace(/[^0-9.,]/g, '').replace(',', '.')) || 0;
          break;
        case 'rating': aVal = a.rating || 0; bVal = b.rating || 0; break;
        case 'ratings_total': aVal = a.ratings_total || 0; bVal = b.ratings_total || 0; break;
      }
      if (typeof aVal === 'string') {
        return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
    });

  return (
    <Layout>
      <PageHeader
        title="ASINs Estratti"
        subtitle={`${total.toLocaleString()} prodotti trovati nell'ultima ricerca`}
      />

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cerca ASINs, titoli, brand..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none text-sm"
            />
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={copyAllAsins}
              disabled={copyStatus === 'loading'}
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
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition text-sm"
            >
              <Download size={16} />
              CSV
            </button>
            <button
              onClick={exportXLSX}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition text-sm"
            >
              <FileSpreadsheet size={16} />
              XLSX
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-[#00D4FF]" />
          </div>
        ) : filteredAsins.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            Nessun ASIN trovato
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[700px] overflow-y-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
                <tr>
                  <th className="px-4 py-3 text-left w-10">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === filteredAsins.length && filteredAsins.length > 0}
                      onChange={toggleSelectAll}
                      className="w-4 h-4 rounded border-gray-300 text-[#00D4FF] focus:ring-[#00D4FF]"
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase w-16">
                    Immagine
                  </th>
                  <th 
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                    onClick={() => handleSort('asin')}
                  >
                    <div className="flex items-center gap-1">
                      ASIN <SortIcon field="asin" />
                    </div>
                  </th>
                  <th 
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                    onClick={() => handleSort('title')}
                  >
                    <div className="flex items-center gap-1">
                      Titolo <SortIcon field="title" />
                    </div>
                  </th>
                  <th 
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                    onClick={() => handleSort('price')}
                  >
                    <div className="flex items-center gap-1">
                      Prezzo <SortIcon field="price" />
                    </div>
                  </th>
                  <th 
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                    onClick={() => handleSort('rating')}
                  >
                    <div className="flex items-center gap-1">
                      Rating <SortIcon field="rating" />
                    </div>
                  </th>
                  <th 
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                    onClick={() => handleSort('ratings_total')}
                  >
                    <div className="flex items-center gap-1">
                      Recensioni <SortIcon field="ratings_total" />
                    </div>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredAsins.map((asin) => (
                  <tr key={asin.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(asin.id)}
                        onChange={() => toggleSelect(asin.id)}
                        className="w-4 h-4 rounded border-gray-300 text-[#00D4FF] focus:ring-[#00D4FF]"
                      />
                    </td>
                    <td className="px-4 py-3">
                      {asin.image_url ? (
                        <img 
                          src={asin.image_url} 
                          alt="" 
                          className="w-12 h-12 object-contain rounded border border-gray-200"
                        />
                      ) : (
                        <div className="w-12 h-12 bg-gray-100 rounded border border-gray-200 flex items-center justify-center">
                          <span className="text-gray-400 text-xs">N/A</span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-sm font-medium text-[#0F1D32]">
                        {asin.asin}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-gray-700 max-w-md line-clamp-2">
                        {asin.title}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-sm font-medium ${asin.price ? 'text-green-600' : 'text-gray-400'}`}>
                        {formatPrice(asin.price)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-600">
                        {asin.rating || '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-600">
                        {asin.ratings_total?.toLocaleString() || '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => copyAsin(asin.asin)}
                          className="p-2 text-gray-400 hover:text-[#00D4FF] hover:bg-gray-100 rounded transition"
                          title="Copia ASIN"
                        >
                          <Copy size={16} />
                        </button>
                        <a
                          href={`https://www.amazon.com/dp/${asin.asin}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 text-gray-400 hover:text-[#00D4FF] hover:bg-gray-100 rounded transition"
                          title="Apri su Amazon"
                        >
                          <ExternalLink size={16} />
                        </a>
                      </div>
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
