import { useState, useEffect, useRef, useCallback } from 'react';
import Layout from '../components/Layout';
import { useSelection } from '../context/SelectionContext';
import { RefreshCw, Loader2, AlertCircle, Book, TrendingUp, PlayCircle, ChevronDown, ChevronRight, Clock, CheckCircle2, XCircle, Download, ArrowUp, ArrowDown, Filter, X, Copy, Zap, Settings, Check, Trash2 } from 'lucide-react';
import api from '../lib/api';
import SettingsProfilesManager from '../components/SettingsProfilesManager';

interface Profile {
  profile_id: string;
  country_code: string;
  marketplace: string;
  enabled: boolean;
  cadence: string;
  next_run_at: string | null;
  last_run_at: string | null;
  settings_profile_id: number | null;
}

interface ProfileBook {
  asin: string;
  title: string | null;
  author: string | null;
  image_url: string | null;
  amazon_url: string | null;
  marketplace: string | null;
  price: number | null;
  royalty_net: number | null;
  acos_be: number | null;
  acos_opt: number | null;
  spend: number | null;
  sales: number | null;
  orders: number | null;
  acos_actual: number | null;
}

interface Run {
  id: number;
  profile_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

interface ReportStatus {
  pending: number;
  completed: number;
  failed: number;
  parsed?: number;
  total: number;
}

interface ReportDetail {
  report_id: string;
  ad_product: string;
  type: string;
  period_days: number;
  status: string;
  has_data: boolean;
  created_at: string | null;
  completed_at: string | null;
}

interface ProfileReports {
  profile_id: string;
  marketplace: string;
  reports: ReportDetail[];
  summary: ReportStatus;
}

interface StrJobItem {
  profile_id: string;
  marketplace: string;
  country_code: string;
  report_id: string | null;
  chunk_start: string;
  chunk_end: string;
  status: 'PENDING' | 'SUCCESS' | 'FAILED';
  amazon_status: string | null;
  error?: string;
}

interface StrJob {
  job_id: string;
  status: 'RUNNING' | 'DONE' | 'TIMEOUT';
  items: StrJobItem[];
  total_rows: number | null;
}

interface SyncStatus {
  has_job: boolean;
  job_id?: number;
  status?: string;
  phase?: string;
  progress_pct?: number;
  message?: string;
  total_asins?: number;
  completed_asins?: number;
  total_reports?: number;
  completed_reports?: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

interface PlannedAction {
  id: number;
  profile_id: string;
  ad_product: string;
  keyword_id: string;
  campaign_id: string;
  campaign_name: string;
  ad_group_id: string;
  keyword: string;
  asin: string | null;
  target_type: string;
  current_bid: number | null;
  delta_bid: number;
  new_bid: number | null;
  acos_30d: number | null;
  acos_be: number | null;
  impressions_30d: number | null;
  clicks: number | null;
  purchases_30d: number | null;
  reason: string;
  status: string;
  created_at: string;
  account_name?: string;
  marketplace?: string;
}

interface AutopilotSettings {
  delta_excellent: number;
  delta_good: number;
  delta_above_be: number;
  delta_high: number;
  delta_low_impressions: number;
  low_impressions_threshold: number;
  max_clicks_no_sales: number;
  max_clicks_for_low_impressions: number;
}

const getCountryFlag = (countryCode: string) => {
  const flags: Record<string, string> = {
    IT: '🇮🇹', UK: '🇬🇧', GB: '🇬🇧', US: '🇺🇸', DE: '🇩🇪', FR: '🇫🇷',
    ES: '🇪🇸', CA: '🇨🇦', AU: '🇦🇺', MX: '🇲🇽', BR: '🇧🇷', JP: '🇯🇵',
    IN: '🇮🇳', NL: '🇳🇱', SE: '🇸🇪', PL: '🇵🇱', BE: '🇧🇪', AE: '🇦🇪',
    SA: '🇸🇦', EG: '🇪🇬', TR: '🇹🇷', SG: '🇸🇬',
  };
  return flags[countryCode] || '🌍';
}


export default function Autopilot() {
  const { selectedAccount, setSelectedAccount, selectedProfiles: contextSelectedProfiles } = useSelection();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [allProfiles, setAllProfiles] = useState<Profile[]>([]);
  const selectedContextProfileIds = new Set(contextSelectedProfiles.map(p => p.profileId));
  const profiles = contextSelectedProfiles.length === 0 ? [] : allProfiles.filter(p => selectedContextProfileIds.has(p.profile_id));
  const [booksMap, setBooksMap] = useState<Record<string, ProfileBook[]>>({});
  const [_runs, _setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingProfiles, setLoadingProfiles] = useState(false);
  const [loadingBooksFor, setLoadingBooksFor] = useState<string | null>(null);
  const [_loadingRuns, _setLoadingRuns] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);
  const [error, setErrorRaw] = useState<string | null>(null);
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const setError = useCallback((msg: string | null) => {
    if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
    setErrorRaw(msg);
    if (msg) errorTimerRef.current = setTimeout(() => setErrorRaw(null), 5000);
  }, []);
  const [expandedProfiles, setExpandedProfiles] = useState<Set<string>>(new Set());
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [accountReports, setAccountReports] = useState<ProfileReports[]>([]);
  const [loadingReports, setLoadingReports] = useState(false);
  const [pollingReports, setPollingReports] = useState(false);
  const [showReportsPanel, setShowReportsPanel] = useState(false);
  const [plannedActions, setPlannedActions] = useState<PlannedAction[]>([]);
  const [actionsSummary, setActionsSummary] = useState<{total: number; planned: number; increases: number; decreases: number}>({total: 0, planned: 0, increases: 0, decreases: 0});
  const [loadingActions, setLoadingActions] = useState(false);
  const [pageSize, setPageSize] = useState<number>(50);
  const [currentPage, setCurrentPage] = useState(1);
  const [executingActions, setExecutingActions] = useState(false);
  const [executingAction, setExecutingAction] = useState<number | null>(null);
  const [fetchingAsins, setFetchingAsins] = useState(false);
  const [requestingReports, setRequestingReports] = useState(false);
  const [planningActions, setPlanningActions] = useState(false);
  const [stepResult, setStepResultRaw] = useState<{type: string; message: string} | null>(null);
  const stepResultTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const setStepResult = useCallback((val: {type: string; message: string} | null) => {
    if (stepResultTimerRef.current) clearTimeout(stepResultTimerRef.current);
    setStepResultRaw(val);
    if (val) stepResultTimerRef.current = setTimeout(() => setStepResultRaw(null), 4000);
  }, []);
  const [testingSbApi, setTestingSbApi] = useState(false);
  const [sbTestResult, setSbTestResult] = useState<any>(null);
  const [testingSbReport, setTestingSbReport] = useState(false);
  const [exportPassword, setExportPassword] = useState('');
  const [exportingTokens, setExportingTokens] = useState(false);
  const [exportResult, setExportResult] = useState<any>(null);
  
  const [sortColumn, setSortColumn] = useState<string>('keyword');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [filterCampaign, setFilterCampaign] = useState<string>('');
  const [filterTargetType, setFilterTargetType] = useState<string>('');
  const [filterReason, setFilterReason] = useState<string>('');
  const [filterAdProduct, setFilterAdProduct] = useState<string>('');
  const [allCampaigns, setAllCampaigns] = useState<string[]>([]);
  const [allTargetTypes, setAllTargetTypes] = useState<string[]>([]);
  const [allReasons, setAllReasons] = useState<string[]>([]);
  const [debugLog, setDebugLog] = useState<string[]>([]);
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  const [showSettingsPanel, setShowSettingsPanel] = useState(false);
  const [showSettingsProfilesPanel, setShowSettingsProfilesPanel] = useState(false);
  const [settingsProfilesRefreshKey, setSettingsProfilesRefreshKey] = useState(0);
  const [settings, setSettings] = useState<AutopilotSettings>({
    delta_excellent: 0.05,
    delta_good: 0.02,
    delta_above_be: -0.02,
    delta_high: -0.05,
    delta_low_impressions: 0.01,
    low_impressions_threshold: 100,
    max_clicks_no_sales: 10,
    max_clicks_for_low_impressions: 0
  });
  const [savingSettings, setSavingSettings] = useState(false);
  const [schedulingActions, setSchedulingActions] = useState(false);
  const bigBangDelayMinutes = 15; // Fixed delay
  const [bigBangJob, setBigBangJob] = useState<any>(null);
  const [bigBangRunning, setBigBangRunning] = useState(false);
  const [bigBangAdProduct, setBigBangAdProduct] = useState<string>('SP');
  const [_bigBangRecurringMode, _setBigBangRecurringMode] = useState<string>('recurring_1h');
  const [cancellingBigBang, setCancellingBigBang] = useState(false);
  const [clearingAsinCache, setClearingAsinCache] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [bigBangJobs, setBigBangJobs] = useState<any[]>([]);
  const [loadingBigBangJobs, setLoadingBigBangJobs] = useState(false);
  const [pendingSettingsProfile, setPendingSettingsProfile] = useState<Record<string, number | null>>({});
  const [savingSettingsProfile, setSavingSettingsProfile] = useState<string | null>(null);
  const [showAdvancedTools, setShowAdvancedTools] = useState(false);
  const [strJob, setStrJob] = useState<StrJob | null>(null);
  const [strSubmitting, setStrSubmitting] = useState(false);
  const [strDownloading, setStrDownloading] = useState(false);
  const [strStartDate, setStrStartDate] = useState<string>(() => {
    const d = new Date(); d.setDate(d.getDate() - 30); return d.toISOString().slice(0, 10);
  });
  const [strEndDate, setStrEndDate] = useState<string>(() => {
    const d = new Date(); d.setDate(d.getDate() - 1); return d.toISOString().slice(0, 10);
  });
  const [historySortCol, setHistorySortCol] = useState<string>('id');
  const [historySortDir, setHistorySortDir] = useState<'asc' | 'desc'>('desc');
  const [downloadingExport, setDownloadingExport] = useState<string | null>(null);
  const [historyPageSize, setHistoryPageSize] = useState<number>(5);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccount?.id) {
      loadProfiles(selectedAccount.id);
      loadSyncStatus();
      loadPlannedActions(selectedAccount.id);
      loadActionFilters(selectedAccount.id);
      setPendingSettingsProfile({});
    }
  }, [selectedAccount?.id]);

  useEffect(() => {
    if (syncStatus?.status === 'RUNNING') {
      const interval = setInterval(loadSyncStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [syncStatus?.status]);

  useEffect(() => {
    if (bigBangJob?.status === 'RUNNING' || bigBangJob?.status === 'SCHEDULED' || bigBangJob?.status === 'WAITING') {
      const interval = setInterval(pollBigBangStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [bigBangJob?.status]);

  useEffect(() => {
    if (selectedAccount?.id) {
      checkActiveBigBangJob();
      loadBigBangJobs();
    }
  }, [selectedAccount?.id]);

  useEffect(() => {
    const hasPending = accountReports.some(p => p.summary.pending > 0);
    if (hasPending && selectedAccount?.id && !pollingReports) {
      const interval = setInterval(async () => {
        try {
          await api.post(`/autopilot/accounts/${selectedAccount.id}/poll-reports`);
          await loadAccountReports();
        } catch (err) {
          console.error('Auto-poll reports failed:', err);
        }
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [accountReports, selectedAccount?.id, pollingReports]);

  const checkActiveBigBangJob = async () => {
    if (!selectedAccount?.id) return;
    try {
      const response = await api.get(`/autopilot/big-bang/active/${selectedAccount.id}`);
      if (response.data?.job) {
        const job = response.data.job;
        if (job.status === 'RUNNING' || job.status === 'SCHEDULED' || job.status === 'WAITING') {
          setBigBangJob(job);
        }
      }
    } catch (err) {
      console.error('Failed to check active big bang job:', err);
    }
  };

  const loadBigBangJobs = async () => {
    if (!selectedAccount?.id) return;
    setLoadingBigBangJobs(true);
    try {
      const response = await api.get(`/autopilot/big-bang/history/${selectedAccount.id}`);
      setBigBangJobs(response.data?.jobs || []);
    } catch (err) {
      console.error('Failed to load big bang jobs:', err);
    } finally {
      setLoadingBigBangJobs(false);
    }
  };

  const cancelBigBangJob = async (jobId: number) => {
    try {
      await api.post(`/autopilot/big-bang/${jobId}/cancel`);
      await loadBigBangJobs();
      if (bigBangJob?.id === jobId) {
        setBigBangJob(null);
      }
    } catch (err: any) {
      console.error('Failed to cancel big bang job:', err);
      console.error(err.response?.data?.detail || 'Errore nella cancellazione');
    }
  };

  const handleHistorySort = (col: string) => {
    if (historySortCol === col) {
      setHistorySortDir(historySortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setHistorySortCol(col);
      setHistorySortDir('desc');
    }
  };

  const getSortedJobs = () => {
    const sorted = [...bigBangJobs].sort((a, b) => {
      let valA = a[historySortCol];
      let valB = b[historySortCol];
      if (historySortCol === 'created_at' || historySortCol === 'execute_at') {
        valA = valA ? new Date(valA).getTime() : 0;
        valB = valB ? new Date(valB).getTime() : 0;
      }
      if (typeof valA === 'string') valA = valA.toLowerCase();
      if (typeof valB === 'string') valB = valB.toLowerCase();
      if (valA < valB) return historySortDir === 'asc' ? -1 : 1;
      if (valA > valB) return historySortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return sorted;
  };

  const downloadJobExport = async (jobId: number, exportType: 'PLANNED' | 'EXECUTED') => {
    const key = `${jobId}_${exportType}`;
    setDownloadingExport(key);
    try {
      const response = await api.get(`/autopilot/big-bang-jobs/${jobId}/export-xlsx?export_type=${exportType}`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const disposition = response.headers['content-disposition'];
      const filename = disposition ? disposition.split('filename=')[1] : `job_${jobId}_${exportType}.xlsx`;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('Export failed:', err);
    } finally {
      setDownloadingExport(null);
    }
  };

  const bigBangDismissTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pollBigBangStatus = async () => {
    if (!bigBangJob?.id) return;
    try {
      const response = await api.get(`/autopilot/big-bang/${bigBangJob.id}/status`);
      const prevStatus = bigBangJob?.status;
      setBigBangJob(response.data);
      if (response.data?.status !== prevStatus && 
          (response.data?.status === 'SCHEDULED' || response.data?.status === 'COMPLETED' || response.data?.status === 'FAILED' || response.data?.status === 'CANCELLED')) {
        await loadPlannedActions();
        await loadActionFilters();
        if (response.data?.status === 'COMPLETED' || response.data?.status === 'FAILED' || response.data?.status === 'CANCELLED') {
          if (bigBangDismissTimerRef.current) clearTimeout(bigBangDismissTimerRef.current);
          bigBangDismissTimerRef.current = setTimeout(() => {
            setBigBangJob(null);
            loadBigBangJobs();
          }, 5000);
        }
      }
    } catch (err) {
      console.error('Failed to poll big bang status:', err);
    }
  };

  const getRecurringModeFromProfiles = (): string => {
    const cadenceMap: Record<string, string> = { '3_hours': 'recurring_3h', daily: 'recurring_1d', '3_days': 'recurring_3d', '5_days': 'recurring_5d' };
    const enabledProfiles = profiles.filter(p => p.enabled);
    if (enabledProfiles.length > 0) {
      return cadenceMap[enabledProfiles[0].cadence || 'daily'] || 'recurring_1d';
    }
    return 'recurring_1d';
  };

  const startBigBang = async (adProduct: string = 'SP') => {
    if (!selectedAccount?.id) return;
    try {
      setBigBangRunning(true);
      setBigBangAdProduct(adProduct);
      setStepResult(null);
      const recurringMode = getRecurringModeFromProfiles();
      const response = await api.post(`/autopilot/big-bang/${selectedAccount.id}`, {
        delay_minutes: bigBangDelayMinutes,
        ad_product: adProduct,
        recurring_mode: recurringMode
      });
      const delayDisplay = bigBangDelayMinutes < 60 ? `${bigBangDelayMinutes} min` : `${bigBangDelayMinutes / 60}h`;
      setBigBangJob({ id: response.data.job_id, status: 'RUNNING', current_phase: 1, phase_message: 'Avvio...', ad_product: adProduct, recurring_mode: recurringMode, progress_pct: 0 });
      setStepResult({type: 'success', message: `Nexus ${adProduct} avviato! Esecuzione tra ${delayDisplay}`});
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'avvio Nexus');
    } finally {
      setBigBangRunning(false);
    }
  };

  const startBigBangAll = async () => {
    if (!selectedAccount?.id || bigBangRunning) return;
    const enabledProfiles = profiles.filter(p => p.enabled);
    if (enabledProfiles.length === 0) { setError('Attiva almeno un marketplace'); return; }
    try {
      setBigBangRunning(true);
      setBigBangAdProduct('ALL');
      const recurringMode = getRecurringModeFromProfiles();
      const response = await api.post(`/autopilot/big-bang/${selectedAccount.id}`, {
        delay_minutes: bigBangDelayMinutes,
        ad_product: 'ALL',
        recurring_mode: recurringMode
      });
      setBigBangJob({ id: response.data.job_id, status: 'RUNNING', current_phase: 1, phase_message: 'Avvio...', ad_product: 'ALL', recurring_mode: recurringMode, progress_pct: 0 });
      setStepResult({type: 'success', message: `Sponsored Product + Sponsored Brand avviati!`});
      checkActiveBigBangJob();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'avvio');
    } finally {
      setBigBangRunning(false);
    }
  };

  const cancelBigBang = async () => {
    if (!bigBangJob?.id) return;
    try {
      setCancellingBigBang(true);
      await api.post(`/autopilot/big-bang/${bigBangJob.id}/cancel`);
      setBigBangJob(null);
      setStepResult({type: 'success', message: 'Nexus annullato'});
      loadBigBangJobs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'annullamento');
    } finally {
      setCancellingBigBang(false);
    }
  };

  const loadSyncStatus = async () => {
    if (!selectedAccount?.id) return;
    try {
      const response = await api.get(`/autopilot/sync-status/${selectedAccount.id}`);
      setSyncStatus(response.data);
      if (response.data?.status === 'COMPLETED') {
        loadProfiles(selectedAccount.id);
        profiles.forEach(p => {
          if (expandedProfiles.has(p.profile_id)) {
            loadBooksForProfile(p.profile_id);
          }
        });
      }
    } catch (err) {
      console.error('Failed to load sync status:', err);
    }
  };

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const response = await api.get('/accounts/');
      const accountsList = response.data || [];
      setAccounts(accountsList);
      if (accountsList.length > 0 && !selectedAccount) {
        setSelectedAccount({ id: accountsList[0].id, name: accountsList[0].name || accountsList[0].client_name, has_token: !!accountsList[0].has_token });
      }
    } catch (err: any) {
      console.error('Failed to load accounts:', err);
      setError(err.response?.data?.detail || 'Errore nel caricamento degli account');
    } finally {
      setLoading(false);
    }
  };

  const loadProfiles = async (accountId: number) => {
    try {
      setLoadingProfiles(true);
      const response = await api.get(`/autopilot/profiles/${accountId}`);
      setAllProfiles(response.data?.profiles || []);
    } catch (err: any) {
      console.error('Failed to load profiles:', err);
      setAllProfiles([]);
    } finally {
      setLoadingProfiles(false);
    }
  };

  const loadBooksForProfile = async (profileId: string) => {
    try {
      setLoadingBooksFor(profileId);
      const response = await api.get(`/autopilot/profiles/${profileId}/books`);
      setBooksMap(prev => ({
        ...prev,
        [profileId]: response.data?.books || []
      }));
    } catch (err: any) {
      console.error('Failed to load books:', err);
    } finally {
      setLoadingBooksFor(null);
    }
  };


  const loadAccountReports = async () => {
    if (!selectedAccount?.id) return;
    try {
      setLoadingReports(true);
      const response = await api.get(`/autopilot/accounts/${selectedAccount.id}/reports`);
      setAccountReports(response.data?.profiles || []);
    } catch (err: any) {
      console.error('Failed to load account reports:', err);
    } finally {
      setLoadingReports(false);
    }
  };

  const pollPendingReports = async () => {
    if (!selectedAccount?.id) return;
    try {
      setPollingReports(true);
      const response = await api.post(`/autopilot/accounts/${selectedAccount.id}/poll-reports`);
      console.log('Poll results:', response.data);
      await loadAccountReports();
    } catch (err: any) {
      console.error('Failed to poll reports:', err);
      setError(err.response?.data?.detail || 'Errore nel polling dei report');
    } finally {
      setPollingReports(false);
    }
  };

  const loadPlannedActions = async (accountId?: number, page: number = 1, size: number = pageSize, sort?: string, dir?: string) => {
    const accId = accountId || selectedAccount?.id;
    if (!accId) return;
    try {
      setLoadingActions(true);
      
      const limit = size === -1 ? 100000 : size;
      const offset = size === -1 ? 0 : (page - 1) * size;
      const effectiveSort = sort || sortColumn;
      const effectiveDir = dir || sortDirection;
      
      let url = `/autopilot/actions/account/${accId}?status=PLANNED&limit=${limit}&offset=${offset}&sort_by=${effectiveSort}&sort_dir=${effectiveDir}`;
      if (filterCampaign) url += `&filter_campaign=${encodeURIComponent(filterCampaign)}`;
      if (filterTargetType) url += `&filter_target_type=${encodeURIComponent(filterTargetType)}`;
      if (filterReason) url += `&filter_reason=${encodeURIComponent(filterReason)}`;
      if (filterAdProduct) url += `&filter_ad_product=${encodeURIComponent(filterAdProduct)}`;
      
      const response = await api.get(url);
      const byProfile = response.data?.by_profile || {};
      const newActions: any[] = [];
      Object.values(byProfile).forEach((actions: any) => {
        newActions.push(...actions);
      });
      
      const totalCount = response.data?.total_actions || 0;
      
      setPlannedActions(newActions);
      setCurrentPage(page);
      
      const increases = newActions.filter((a: any) => (a.delta_bid || 0) > 0).length;
      const decreases = newActions.filter((a: any) => (a.delta_bid || 0) < 0).length;
      setActionsSummary({
        total: totalCount,
        planned: newActions.filter((a: any) => a.status === 'PLANNED').length,
        increases,
        decreases
      });
    } catch (err: any) {
      console.error('Failed to load planned actions:', err);
    } finally {
      setLoadingActions(false);
    }
  };
  
  const loadActionFilters = async (accountId?: number) => {
    const accId = accountId || selectedAccount?.id;
    if (!accId) return;
    try {
      const response = await api.get(`/autopilot/actions/account/${accId}/filters?status=PLANNED`);
      const campaigns = response.data?.campaigns || [];
      const targetTypes = response.data?.target_types || [];
      const reasons = response.data?.reasons || [];
      setAllCampaigns(campaigns);
      setAllTargetTypes(targetTypes);
      setAllReasons(reasons);
      if (filterCampaign && !campaigns.includes(filterCampaign)) {
        setFilterCampaign('');
      }
      if (filterTargetType && !targetTypes.includes(filterTargetType)) {
        setFilterTargetType('');
      }
      if (filterReason && !reasons.includes(filterReason)) {
        setFilterReason('');
      }
    } catch (err) {
      console.error('Failed to load action filters:', err);
    }
  };

  const goToPage = (page: number) => {
    if (selectedAccount?.id) {
      loadPlannedActions(selectedAccount.id, page, pageSize);
    }
  };
  
  const changePageSize = (newSize: number) => {
    setPageSize(newSize);
    setCurrentPage(1);
    if (selectedAccount?.id) {
      loadPlannedActions(selectedAccount.id, 1, newSize);
    }
  };
  
  const totalPages = pageSize === -1 ? 1 : Math.ceil(actionsSummary.total / pageSize);

  /* Disabled - executeActions
  const executeActions = async (profileId: string) => {
    try {
      setExecutingActions(true);
      await api.post(`/autopilot/actions/execute/${profileId}`);
      await loadPlannedActions();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'esecuzione delle azioni');
    } finally {
      setExecutingActions(false);
    }
  };
  */

  const executeSingleAction = async (actionId: number) => {
    try {
      setExecutingAction(actionId);
      const action = plannedActions.find(a => a.id === actionId);
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] Esecuzione azione #${actionId}: ${action?.keyword || ''} (${action?.ad_product || 'SP'})`]);
      
      const response = await api.post(`/autopilot/actions/execute-single/${actionId}`);
      
      const amazonResp = response.data?.amazon_response ? JSON.stringify(response.data.amazon_response, null, 2) : 'N/A';
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] Risposta: ${JSON.stringify(response.data)}`]);
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] Amazon Response: ${amazonResp}`]);
      
      if (response.data?.success) {
        setPlannedActions(prev => prev.filter(a => a.id !== actionId));
        setStepResult({type: 'success', message: `Azione eseguita: ${response.data.message || 'OK'}`});
      } else {
        const errorMsg = response.data?.error || 'Errore sconosciuto';
        setError(errorMsg);
        setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ERRORE: ${errorMsg}`]);
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Errore sconosciuto';
      setError(errorMsg);
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ECCEZIONE: ${errorMsg}`]);
    } finally {
      setExecutingAction(null);
    }
  };

  const [clearingActions, setClearingActions] = useState(false);
  const [clearingCache, setClearingCache] = useState(false);
  const [deletingReports, setDeletingReports] = useState(false);
  const [exportingCampaigns, setExportingCampaigns] = useState(false);
  const [exportingTargets, setExportingTargets] = useState(false);
  // Polling STR job
  useEffect(() => {
    if (!strJob || strJob.status !== 'RUNNING' || !selectedAccount?.id) return;
    const interval = setInterval(async () => {
      try {
        const resp = await api.get(`/autopilot/accounts/${selectedAccount.id}/search-term-jobs/${strJob.job_id}`);
        setStrJob(resp.data);
      } catch {}
    }, 6000);
    return () => clearInterval(interval);
  }, [strJob?.job_id, strJob?.status, selectedAccount?.id]);
  
  const clearPlannedActions = async () => {
    if (!selectedAccount?.id) return;
    if (!confirm('Vuoi cancellare tutte le azioni pianificate?')) return;
    
    try {
      setClearingActions(true);
      const response = await api.delete(`/autopilot/actions/account/${selectedAccount.id}`);
      if (response.data?.success) {
        setPlannedActions([]);
        setActionsSummary({ total: 0, planned: 0, increases: 0, decreases: 0 });
        setStepResult({type: 'success', message: response.data.message || 'Azioni cancellate'});
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nella cancellazione delle azioni');
    } finally {
      setClearingActions(false);
    }
  };

  const loadSettings = async () => {
    if (!selectedAccount?.id) return;
    try {
      const response = await api.get(`/autopilot/settings/${selectedAccount.id}`);
      setSettings(response.data);
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  const saveSettings = async () => {
    if (!selectedAccount?.id) return;
    try {
      setSavingSettings(true);
      await api.post(`/autopilot/settings/${selectedAccount.id}`, settings);
      setStepResult({type: 'success', message: 'Impostazioni salvate'});
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nel salvataggio delle impostazioni');
    } finally {
      setSavingSettings(false);
    }
  };

  const saveSettingsProfileAssignment = async (profileId: string) => {
    const settingsProfileId = pendingSettingsProfile[profileId];
    if (settingsProfileId === undefined) return;
    
    try {
      setSavingSettingsProfile(profileId);
      if (settingsProfileId === 0 || settingsProfileId === null) {
        await api.delete(`/autopilot/autopilot-profile/${profileId}/assign-settings`);
        setAllProfiles(prev => prev.map(p => 
          p.profile_id === profileId 
            ? {...p, settings_profile_id: null}
            : p
        ));
      } else {
        await api.post(`/autopilot/autopilot-profile/${profileId}/assign-settings/${settingsProfileId}`);
        setAllProfiles(prev => prev.map(p => 
          p.profile_id === profileId 
            ? {...p, settings_profile_id: settingsProfileId}
            : p
        ));
      }
      setPendingSettingsProfile(prev => {
        const next = {...prev};
        delete next[profileId];
        return next;
      });
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nel salvataggio del profilo settings');
    } finally {
      setSavingSettingsProfile(null);
    }
  };

  const scheduleActions = async (hours: number) => {
    if (!selectedAccount?.id) return;
    try {
      setSchedulingActions(true);
      const response = await api.post(`/autopilot/schedule-actions/${selectedAccount.id}`, { hours });
      setStepResult({type: 'success', message: `${response.data.actions_scheduled} azioni programmate per ${hours}h`});
      await loadPlannedActions();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nella programmazione delle azioni');
    } finally {
      setSchedulingActions(false);
    }
  };

  const clearLiveBidsCache = async () => {
    try {
      setClearingCache(true);
      const response = await api.delete('/autopilot/cache');
      if (response.data?.success) {
        setStepResult({type: 'success', message: response.data.message || 'Cache svuotata'});
        setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] Cache svuotata: ${response.data.cleared_keys} chiavi rimosse`]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nella pulizia della cache');
    } finally {
      setClearingCache(false);
    }
  };

  const clearAsinCache = async () => {
    if (!selectedAccount?.id) return;
    if (!confirm('Vuoi eliminare tutte le informazioni degli ASIN (economics) per questo account?')) return;
    try {
      setClearingAsinCache(true);
      const response = await api.delete(`/autopilot/accounts/${selectedAccount.id}/asin-cache`);
      if (response.data?.success) {
        setStepResult({type: 'success', message: response.data.message || 'Cache ASIN svuotata'});
        setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] Cache ASIN svuotata: ${response.data.deleted_count} record rimossi`]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nella pulizia della cache ASIN');
    } finally {
      setClearingAsinCache(false);
    }
  };

  const deleteReports = async () => {
    if (!selectedAccount?.id) return;
    if (!confirm('Vuoi eliminare tutti i report per questo account?')) return;
    
    try {
      setDeletingReports(true);
      const response = await api.delete(`/autopilot/accounts/${selectedAccount.id}/reports`);
      if (response.data?.success) {
        setStepResult({type: 'success', message: response.data.message || 'Report eliminati'});
        setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] Report eliminati: ${response.data.deleted_count}`]);
        loadAccountReports();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nella cancellazione dei report');
    } finally {
      setDeletingReports(false);
    }
  };

  const exportCampaigns = async () => {
    if (!selectedAccount?.id) return;
    
    try {
      setExportingCampaigns(true);
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] Esportazione campagne in corso...`]);
      
      const response = await api.get(`/autopilot/accounts/${selectedAccount.id}/export-campaigns`, {
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `campaigns_account_${selectedAccount.id}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      setStepResult({type: 'success', message: 'JSON campagne scaricato'});
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] JSON campagne esportato`]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'esportazione delle campagne');
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ERRORE export: ${err.message}`]);
    } finally {
      setExportingCampaigns(false);
    }
  };

  const exportTargets = async () => {
    if (!selectedAccount?.id) return;
    
    try {
      setExportingTargets(true);
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] Esportazione targets in corso...`]);
      
      const response = await api.get(`/autopilot/accounts/${selectedAccount.id}/export-targets`, {
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `targets_account_${selectedAccount.id}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      setStepResult({type: 'success', message: 'JSON targets scaricato'});
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] JSON targets esportato`]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'esportazione dei targets');
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ERRORE export targets: ${err.message}`]);
    } finally {
      setExportingTargets(false);
    }
  };

  const submitStrJob = async () => {
    if (!selectedAccount?.id || profiles.length === 0) return;
    try {
      setStrSubmitting(true);
      setStrJob(null);
      const profileIds = profiles.map(p => p.profile_id);
      const resp = await api.post(`/autopilot/accounts/${selectedAccount.id}/search-term-jobs`, {
        profile_ids: profileIds,
        start_date: strStartDate,
        end_date: strEndDate,
      });
      setStrJob(resp.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore avvio job Search Term');
    } finally {
      setStrSubmitting(false);
    }
  };

  const downloadStrReport = async () => {
    if (!strJob || !selectedAccount?.id) return;
    try {
      setStrDownloading(true);
      const resp = await api.get(
        `/autopilot/accounts/${selectedAccount.id}/search-term-jobs/${strJob.job_id}/download`,
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([resp.data], { type: 'application/json' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `search_term_${selectedAccount.id}_${strJob.job_id.slice(0, 8)}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError('Errore download report');
    } finally {
      setStrDownloading(false);
    }
  };

  const [exportingActionsXlsx, setExportingActionsXlsx] = useState(false);
  
  const exportActionsXlsx = async (status?: string) => {
    if (!selectedAccount?.id) return;
    
    try {
      setExportingActionsXlsx(true);
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] Esportazione azioni ${status || 'tutte'} in XLSX...`]);
      
      const url = status 
        ? `/autopilot/actions/account/${selectedAccount.id}/export-xlsx?status=${status}`
        : `/autopilot/actions/account/${selectedAccount.id}/export-xlsx`;
      
      const response = await api.get(url, { responseType: 'blob' });
      
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      const statusSuffix = status ? `_${status}` : '';
      a.download = `azioni_account_${selectedAccount.id}${statusSuffix}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
      document.body.removeChild(a);
      
      setStepResult({type: 'success', message: `XLSX azioni ${status || 'tutte'} scaricato`});
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] XLSX azioni esportato`]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'esportazione delle azioni');
      setDebugLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ERRORE export azioni: ${err.message}`]);
    } finally {
      setExportingActionsXlsx(false);
    }
  };


  const handleSort = (column: string) => {
    const backendColumnMap: Record<string, string> = {
      'campaign': 'campaign_name',
    };
    const backendCol = backendColumnMap[column] || column;
    
    let newDir: 'asc' | 'desc';
    if (sortColumn === backendCol) {
      newDir = sortDirection === 'asc' ? 'desc' : 'asc';
      setSortDirection(newDir);
    } else {
      setSortColumn(backendCol);
      newDir = 'asc';
      setSortDirection(newDir);
    }
    loadPlannedActions(undefined, 1, pageSize, backendCol, newDir);
  };

  useEffect(() => {
    if (selectedAccount?.id) {
      loadPlannedActions(selectedAccount.id, 1, pageSize);
    }
  }, [filterCampaign, filterTargetType, filterReason, filterAdProduct]);

  const toggleAutopilot = async (profile: Profile) => {
    if (!selectedAccount?.id) return;
    try {
      setToggling(profile.profile_id);
      await api.post(`/autopilot/profiles/${selectedAccount?.id}`, {
        profile_ids: [profile.profile_id],
        enabled: !profile.enabled,
        cadence: profile.cadence || 'daily'
      });
      await loadProfiles(selectedAccount?.id);
      if (!profile.enabled) {
        try {
          const cadenceMap: Record<string, string> = { '3_hours': 'recurring_3h', daily: 'recurring_1d', '3_days': 'recurring_3d', '5_days': 'recurring_5d' };
          const recurringMode = cadenceMap[profile.cadence || 'daily'] || 'recurring_1d';
          const activeCheck = await api.get(`/autopilot/big-bang/active/${selectedAccount.id}`);
          if (!activeCheck.data?.job) {
            const response = await api.post(`/autopilot/big-bang/${selectedAccount.id}`, {
              ad_product: 'ALL',
              recurring_mode: recurringMode
            });
            setBigBangJob({ id: response.data.job_id, status: 'RUNNING', current_phase: 1, phase_message: 'Avvio automatico...', ad_product: 'ALL', recurring_mode: recurringMode, progress_pct: 0 });
            pollBigBangStatus();
          }
        } catch (bigBangErr: any) {
          console.error('Auto Nexus failed:', bigBangErr);
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to toggle autopilot');
    } finally {
      setToggling(null);
    }
  };

  const stepFetchAsins = async () => {
    if (!selectedAccount?.id) return;
    try {
      setFetchingAsins(true);
      setStepResult(null);
      const response = await api.post(`/autopilot/step/fetch-asins/${selectedAccount.id}`);
      const data = response.data;
      setStepResult({
        type: 'success',
        message: `Trovati ${data.total_asins} ASIN in ${data.profiles?.length || 0} profili`
      });
      await loadProfiles(selectedAccount.id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nel recupero ASIN');
    } finally {
      setFetchingAsins(false);
    }
  };

  const testSbApi = async () => {
    if (!selectedAccount?.id) return;
    const enabledProfile = profiles.find(p => p.enabled);
    if (!enabledProfile) {
      setError('Nessun profilo abilitato. Abilita almeno un profilo.');
      return;
    }
    try {
      setTestingSbApi(true);
      setSbTestResult(null);
      const response = await api.get(`/autopilot/test-sb-targets/${selectedAccount.id}/${enabledProfile.profile_id}`);
      setSbTestResult(response.data);
    } catch (err: any) {
      setSbTestResult({ error: err.response?.data?.detail || err.message });
    } finally {
      setTestingSbApi(false);
    }
  };

  const testSbReport = async () => {
    if (!selectedAccount?.id) return;
    const enabledProfile = profiles.find(p => p.enabled);
    if (!enabledProfile) {
      setError('Nessun profilo abilitato. Abilita almeno un profilo.');
      return;
    }
    try {
      setTestingSbReport(true);
      setSbTestResult(null);
      const response = await api.post(`/autopilot/test-sb-report/${selectedAccount.id}/${enabledProfile.profile_id}`);
      setSbTestResult(response.data);
    } catch (err: any) {
      setSbTestResult({ error: err.response?.data?.detail || err.message });
    } finally {
      setTestingSbReport(false);
    }
  };

  const exportTokens = async () => {
    if (!exportPassword) {
      setError('Inserisci la password');
      return;
    }
    try {
      setExportingTokens(true);
      setExportResult(null);
      const response = await api.post('/autopilot/export-tokens', { password: exportPassword });
      setExportResult(response.data);
      setExportPassword('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Password non valida');
    } finally {
      setExportingTokens(false);
    }
  };

  const stepRequestReports = async () => {
    if (!selectedAccount?.id) return;
    try {
      setRequestingReports(true);
      setStepResult(null);
      const response = await api.post(`/autopilot/step/request-reports/${selectedAccount.id}`);
      const data = response.data;
      setStepResult({
        type: 'success',
        message: `Richiesti ${data.reports_requested} report per ${data.profiles?.length || 0} profili`
      });
      await loadAccountReports();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nella richiesta report');
    } finally {
      setRequestingReports(false);
    }
  };

  const stepPlanActions = async (targetScope?: string) => {
    if (!selectedAccount?.id) return;
    try {
      setPlanningActions(true);
      setStepResult(null);
      
      let endpoint = `/autopilot/step/plan-actions/${selectedAccount.id}`;
      if (targetScope === 'AUTO') {
        endpoint = `/autopilot/step/plan-auto/${selectedAccount.id}`;
      } else if (targetScope === 'SP_MANUAL') {
        endpoint = `/autopilot/step/plan-sp-manual/${selectedAccount.id}`;
      } else if (targetScope === 'SB') {
        endpoint = `/autopilot/step/plan-sb/${selectedAccount.id}`;
      }
      
      const response = await api.post(endpoint);
      const data = response.data;
      const scopeLabel = targetScope ? ` (${targetScope})` : '';
      setStepResult({
        type: 'success',
        message: `Pianificate ${data.total_actions} azioni${scopeLabel} per ${data.profiles?.length || 0} profili`
      });
      await loadPlannedActions();
      await loadActionFilters();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nella pianificazione azioni');
    } finally {
      setPlanningActions(false);
    }
  };

  const stepExecuteActions = async () => {
    if (!selectedAccount?.id) return;
    try {
      setExecutingActions(true);
      setStepResult(null);
      const response = await api.post(`/autopilot/step/execute-actions/${selectedAccount.id}`);
      const data = response.data;
      setStepResult({
        type: data.executed > 0 ? 'success' : 'info',
        message: `Eseguite ${data.executed} azioni${data.failed > 0 ? `, ${data.failed} fallite` : ''}`
      });
      await loadPlannedActions();
      await loadActionFilters();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nell\'esecuzione azioni');
    } finally {
      setExecutingActions(false);
    }
  };

  const toggleProfileExpanded = (profileId: string) => {
    const newExpanded = new Set(expandedProfiles);
    if (newExpanded.has(profileId)) {
      newExpanded.delete(profileId);
    } else {
      newExpanded.add(profileId);
      if (!booksMap[profileId]) {
        loadBooksForProfile(profileId);
      }
    }
    setExpandedProfiles(newExpanded);
  };

  if (loading) {
    return (
      <Layout>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
            <span className="text-sm text-gray-500">Caricamento...</span>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-5">

          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Autopilot</h1>
              <p className="text-sm text-gray-500 mt-0.5">Ottimizzazione automatica dei bid</p>
            </div>
            <select
              value={selectedAccount?.id || ''}
              onChange={(e) => {
                const acc = accounts.find(a => a.id === Number(e.target.value));
                if (acc) {
                  setFilterCampaign('');
                  setFilterTargetType('');
                  setFilterReason('');
                  setFilterAdProduct('');
                  setSelectedAccount({ id: acc.id, name: acc.name || acc.client_name, has_token: !!acc.has_token });
                }
              }}
              className="px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm font-medium text-gray-900 shadow-sm focus:ring-2 focus:ring-cyan-200 focus:border-cyan-400 focus:outline-none"
            >
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name || account.client_name || `Account ${account.id}`}
                </option>
              ))}
            </select>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-400 to-cyan-500 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-white" />
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Pipeline</div>
                  <div className="text-xs text-gray-400">{profiles.filter(p => p.enabled).length} marketplace attivi</div>
                </div>
              </div>
              <button
                onClick={() => setShowSettingsProfilesPanel(!showSettingsProfilesPanel)}
                className={`flex items-center gap-1.5 px-3.5 py-2.5 rounded-lg text-sm border font-medium transition-colors ${showSettingsProfilesPanel ? 'bg-purple-50 border-purple-200 text-purple-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
              >
                <Settings className="w-4 h-4" />
                Profili Settings
              </button>
            </div>

            {bigBangJob && (
              <div className={`mx-5 mb-4 p-3 rounded-lg border ${bigBangJob.status === 'RUNNING' || bigBangJob.status === 'EXECUTING' ? 'bg-cyan-50 border-cyan-200' : bigBangJob.status === 'SCHEDULED' ? 'bg-cyan-50 border-cyan-200' : bigBangJob.status === 'WAITING' ? 'bg-blue-50 border-blue-200' : bigBangJob.status === 'FAILED' ? 'bg-red-100 border-red-300' : bigBangJob.status === 'CANCELLED' ? 'bg-gray-50 border-gray-300' : 'bg-green-50 border-green-200'}`}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    {(bigBangJob.status === 'RUNNING' || bigBangJob.status === 'EXECUTING') && <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-600" />}
                    {bigBangJob.status === 'SCHEDULED' && <Clock className="w-3.5 h-3.5 text-cyan-600" />}
                    {bigBangJob.status === 'WAITING' && <Clock className="w-3.5 h-3.5 text-blue-600" />}
                    {bigBangJob.status === 'COMPLETED' && <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />}
                    {bigBangJob.status === 'FAILED' && <XCircle className="w-3.5 h-3.5 text-red-600" />}
                    {bigBangJob.status === 'CANCELLED' && <XCircle className="w-3.5 h-3.5 text-gray-500" />}
                    <span className="text-xs text-gray-600">
                      {bigBangJob.phase_message || 'In corso...'}
                    </span>
                    <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${bigBangJob.status === 'RUNNING' || bigBangJob.status === 'EXECUTING' ? 'bg-cyan-100 text-cyan-700' : bigBangJob.status === 'SCHEDULED' ? 'bg-cyan-100 text-cyan-700' : bigBangJob.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : bigBangJob.status === 'FAILED' ? 'bg-red-200 text-red-800' : 'bg-gray-100 text-gray-600'}`}>
                      {bigBangJob.status === 'COMPLETED' ? '100%' : `${bigBangJob.progress_pct || 0}%`}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {(bigBangJob.status === 'RUNNING' || bigBangJob.status === 'EXECUTING' || bigBangJob.status === 'SCHEDULED' || bigBangJob.status === 'WAITING') && (
                      <button
                        onClick={cancelBigBang}
                        disabled={cancellingBigBang}
                        className="flex items-center gap-1 px-2 py-0.5 bg-red-500 text-white rounded text-[10px] hover:bg-red-600 disabled:opacity-50"
                      >
                        {cancellingBigBang ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <XCircle className="w-2.5 h-2.5" />}
                        Annulla
                      </button>
                    )}
                    <button onClick={() => setBigBangJob(null)} className="text-gray-400 hover:text-gray-600">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full transition-all duration-500 ${bigBangJob.status === 'COMPLETED' ? 'bg-green-500' : bigBangJob.status === 'FAILED' ? 'bg-red-500' : bigBangJob.status === 'CANCELLED' ? 'bg-gray-400' : 'bg-cyan-500'}`}
                    style={{ width: `${bigBangJob.status === 'COMPLETED' ? 100 : bigBangJob.progress_pct || 0}%` }}
                  ></div>
                </div>
                {bigBangJob.execute_at && bigBangJob.status === 'SCHEDULED' && (() => {
                  const executeAtStr = bigBangJob.execute_at.endsWith('Z') ? bigBangJob.execute_at : bigBangJob.execute_at + 'Z';
                  const executeAt = new Date(executeAtStr);
                  const now = currentTime;
                  const diffRaw = Math.floor((executeAt.getTime() - now.getTime()) / 1000);
                  const isPast = diffRaw <= 0;
                  const diff = Math.abs(diffRaw);
                  const hours = Math.floor(diff / 3600);
                  const minutes = Math.floor((diff % 3600) / 60);
                  const seconds = diff % 60;
                  const countdown = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
                  const dateStr = executeAt.toLocaleDateString('it-IT', {day: '2-digit', month: '2-digit', year: 'numeric'});
                  const timeStr = executeAt.toLocaleTimeString('it-IT', {hour: '2-digit', minute: '2-digit'});
                  return (
                    <p className="text-[10px] text-cyan-700 mt-1 font-mono">
                      Esecuzione: {dateStr} {timeStr} ({tz}) 
                      {isPast ? (
                        <span className="ml-1 bg-green-100 text-green-800 px-1.5 py-0.5 rounded">In attesa worker...</span>
                      ) : (
                        <span className="ml-1 bg-cyan-100 px-1.5 py-0.5 rounded">-{countdown}</span>
                      )}
                    </p>
                  );
                })()}
                {bigBangJob.error_message && (
                  <p className="text-[10px] text-red-600 mt-1">{bigBangJob.error_message}</p>
                )}
              </div>
            )}
          </div>

        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-md" style={{ pointerEvents: 'none' }}>
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 shadow-lg animate-in" style={{ pointerEvents: 'auto' }}>
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm">{error}</span>
              <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">
                &times;
              </button>
            </div>
          )}

          {stepResult && (
            <div className={`p-3 rounded-lg flex items-center gap-2 shadow-lg animate-in ${stepResult.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-cyan-50 border-2 border-[#00D4FF] text-[#00A8CC]'}`} style={{ pointerEvents: 'auto' }}>
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm">{stepResult.message}</span>
              <button onClick={() => setStepResult(null)} className="ml-auto hover:opacity-70">
                &times;
              </button>
            </div>
          )}

          {syncStatus?.has_job && syncStatus.status === 'COMPLETED' && (
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-green-700 shadow-lg animate-in" style={{ pointerEvents: 'auto' }}>
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm">{syncStatus.message}</span>
            </div>
          )}

          {syncStatus?.has_job && syncStatus.status === 'FAILED' && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 shadow-lg animate-in" style={{ pointerEvents: 'auto' }}>
              <XCircle className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm">Sync fallito: {syncStatus.error || syncStatus.message}</span>
            </div>
          )}
        </div>

        {syncStatus?.has_job && (syncStatus.status === 'RUNNING' || syncStatus.status === 'STARTING') && (
          <div className="sticky top-0 z-30 p-4 bg-cyan-50 border-2 border-[#00D4FF] rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-[#00D4FF]" />
                <span className="font-medium text-[#0F1D32]">{syncStatus.message}</span>
              </div>
              <span className="text-sm text-[#00A8CC]">{syncStatus.progress_pct || 0}%</span>
            </div>
            <div className="w-full bg-blue-200 rounded-full h-2.5">
              <div 
                className="bg-[#00D4FF] h-2.5 rounded-full transition-all duration-300" 
                style={{ width: `${syncStatus.progress_pct || 0}%` }}
              ></div>
            </div>
            <div className="mt-2 flex gap-4 text-sm text-[#00A8CC]">
              {syncStatus.total_asins ? (
                <span>ASIN: {syncStatus.completed_asins || 0}/{syncStatus.total_asins}</span>
              ) : null}
              {syncStatus.total_reports ? (
                <span>Reports: {syncStatus.completed_reports || 0}/{syncStatus.total_reports}</span>
              ) : null}
            </div>
          </div>
        )}



        {(showReportsPanel || showSettingsProfilesPanel || showDebugPanel) && (
          <div className="fixed inset-0 z-40 flex justify-end">
            <div className="absolute inset-0 bg-black/30 transition-opacity" onClick={() => { setShowReportsPanel(false); setShowSettingsProfilesPanel(false); setShowDebugPanel(false); }} />
            <div className="relative w-full max-w-lg bg-white shadow-2xl flex flex-col animate-slide-in-right">

              {showReportsPanel && (
                <>
                  <div className="p-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                    <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                      <Clock className="w-5 h-5 text-purple-600" />
                      Report Status per Profile
                    </h3>
                    <div className="flex items-center gap-2">
                      <button onClick={loadAccountReports} disabled={loadingReports} className="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200">
                        {loadingReports ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                        Aggiorna
                      </button>
                      <button onClick={pollPendingReports} disabled={pollingReports || accountReports.every(p => p.summary.pending === 0)} className="flex items-center gap-1 px-3 py-1.5 text-sm bg-yellow-100 text-yellow-700 rounded-lg hover:bg-yellow-200 disabled:opacity-50">
                        {pollingReports ? <Loader2 className="w-3 h-3 animate-spin" /> : <PlayCircle className="w-3 h-3" />}
                        Poll Pending
                      </button>
                      <button onClick={() => setShowReportsPanel(false)} className="text-gray-400 hover:text-gray-600 p-1"><X className="w-5 h-5" /></button>
                    </div>
                  </div>
                  <div className="p-4 overflow-y-auto flex-1">
                    {loadingReports ? (
                      <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-purple-600" /></div>
                    ) : accountReports.length === 0 ? (
                      <p className="text-gray-500 text-sm">Nessun report trovato. Esegui un Refresh per generare i report.</p>
                    ) : (
                      <div className="space-y-4">
                        {accountReports.map((profile) => (
                          <div key={profile.profile_id} className="border border-gray-200 rounded-lg p-3">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-lg">{getCountryFlag(profile.marketplace)}</span>
                                <span className="font-medium text-gray-900">{profile.marketplace}</span>
                                <span className="text-xs text-gray-400 font-mono">{profile.profile_id}</span>
                              </div>
                              <div className="flex items-center gap-2 text-xs">
                                {(profile.summary.parsed || 0) > 0 && (<span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full">{profile.summary.parsed} parsed</span>)}
                                {profile.summary.completed > 0 && (<span className="px-2 py-0.5 bg-cyan-50 text-[#00A8CC] rounded-full">{profile.summary.completed} completed</span>)}
                                {profile.summary.pending > 0 && (<span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full">{profile.summary.pending} pending</span>)}
                                {profile.summary.failed > 0 && (<span className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full">{profile.summary.failed} failed</span>)}
                              </div>
                            </div>
                            {profile.reports.length > 0 && (
                              <div className="mt-2 space-y-1">
                                {profile.reports.slice(0, 6).map((report) => (
                                  <div key={report.report_id} className="flex items-center justify-between text-xs bg-gray-50 rounded px-2 py-1">
                                    <div className="flex items-center gap-2">
                                      <span className={`w-2 h-2 rounded-full ${report.status === 'PARSED' ? 'bg-green-500' : report.status === 'COMPLETED' ? 'bg-[#00D4FF]' : report.status === 'PENDING' ? 'bg-yellow-500' : 'bg-red-500'}`}></span>
                                      <button onClick={() => { navigator.clipboard.writeText(report.report_id); }} className="font-mono text-gray-600 hover:text-[#00D4FF] hover:bg-cyan-50 px-1 rounded cursor-pointer transition-colors" title="Clicca per copiare l'ID completo">
                                        <span className={`font-bold ${report.ad_product === 'SB' ? 'text-purple-600' : 'text-[#00D4FF]'}`}>{report.ad_product || 'SP'}</span>_{report.report_id.slice(0, 10)}...
                                      </button>
                                      <span className="text-gray-400">({report.period_days}D)</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-gray-500">
                                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${report.status === 'PARSED' ? 'bg-green-100 text-green-700' : report.status === 'COMPLETED' ? 'bg-cyan-50 text-[#00A8CC]' : report.status === 'PENDING' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}`}>{report.status}</span>
                                      {report.created_at && (<span className="text-[10px]">{new Date(report.created_at).toLocaleString('it-IT', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>)}
                                      {report.has_data && selectedAccount && (
                                        <button onClick={() => { window.open(`/api/autopilot/accounts/${selectedAccount.id}/reports/${report.report_id}/download`, '_blank'); }} className="p-1 text-[#00D4FF] hover:text-[#0F1D32] hover:bg-cyan-50 rounded transition-colors" title="Scarica report JSON">
                                          <Download className="w-3 h-3" />
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                ))}
                                {profile.reports.length > 6 && (<p className="text-xs text-gray-400 pl-2">...e altri {profile.reports.length - 6} report</p>)}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}

              {showSettingsProfilesPanel && selectedAccount && (
                <>
                  <div className="p-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                    <h3 className="text-lg font-semibold text-gray-900">Profili Impostazioni</h3>
                    <button onClick={() => setShowSettingsProfilesPanel(false)} className="text-gray-400 hover:text-gray-600 p-1"><X className="w-5 h-5" /></button>
                  </div>
                  <div className="p-4 overflow-y-auto flex-1">
                    <SettingsProfilesManager
                      accountId={selectedAccount.id}
                      onProfilesChanged={() => setSettingsProfilesRefreshKey(k => k + 1)}
                    />
                  </div>
                </>
              )}

              {showDebugPanel && (
                <>
                  <div className="p-4 border-b border-red-100 flex items-center justify-between flex-shrink-0">
                    <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                      <AlertCircle className="w-5 h-5 text-red-600" />
                      Debug Log API
                    </h2>
                    <div className="flex items-center gap-2">
                      <button onClick={() => setDebugLog([])} className="px-3 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200">Cancella</button>
                      <button onClick={() => setShowDebugPanel(false)} className="text-gray-400 hover:text-gray-600 p-1"><X className="w-5 h-5" /></button>
                    </div>
                  </div>
                  <div className="p-4 overflow-y-auto flex-1 bg-gray-900">
                    {debugLog.length === 0 ? (
                      <p className="text-gray-400 text-sm font-mono">Nessun log. Esegui un'azione per vedere i dettagli API.</p>
                    ) : (
                      <div className="space-y-1">
                        {debugLog.map((log, idx) => (
                          <pre key={idx} className="text-xs font-mono text-green-400 whitespace-pre-wrap break-all">{log}</pre>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}

            </div>
          </div>
        )}

        {showSettingsPanel && (
          <div className="fixed inset-0 z-40 flex justify-end">
            <div className="absolute inset-0 bg-black/30 transition-opacity" onClick={() => setShowSettingsPanel(false)} />
            <div className="relative w-full max-w-lg bg-white shadow-2xl flex flex-col animate-slide-in-right">
              <div className="p-4 border-b border-indigo-100 flex items-center justify-between flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">Impostazioni Bid Delta</h2>
                <button onClick={() => setShowSettingsPanel(false)} className="text-gray-400 hover:text-gray-600 p-1"><X className="w-5 h-5" /></button>
              </div>
              <div className="p-4 overflow-y-auto flex-1">
              <p className="text-sm text-gray-600 mb-4">
                Configura i delta di modifica bid per ogni fascia ACOS. Solo i target con ACOS calcolato e libro associato riceveranno azioni.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Eccellente (ACOS &lt; BE/3)
                  </label>
                  <div className="flex items-center gap-2">
                    <span className="text-green-600 text-sm">+$</span>
                    <input
                      type="number"
                      step="0.01"
                      value={settings.delta_excellent}
                      onChange={(e) => setSettings({...settings, delta_excellent: parseFloat(e.target.value) || 0})}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Buono (BE/3 &lt; ACOS &lt; BE/1.5)
                  </label>
                  <div className="flex items-center gap-2">
                    <span className="text-green-600 text-sm">+$</span>
                    <input
                      type="number"
                      step="0.01"
                      value={settings.delta_good}
                      onChange={(e) => setSettings({...settings, delta_good: parseFloat(e.target.value) || 0})}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Sopra BE (BE &lt; ACOS &lt; BE/0.75)
                  </label>
                  <div className="flex items-center gap-2">
                    <span className="text-red-600 text-sm">$</span>
                    <input
                      type="number"
                      step="0.01"
                      value={settings.delta_above_be}
                      onChange={(e) => setSettings({...settings, delta_above_be: parseFloat(e.target.value) || 0})}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Alto (ACOS &gt; BE/0.75)
                  </label>
                  <div className="flex items-center gap-2">
                    <span className="text-red-600 text-sm">$</span>
                    <input
                      type="number"
                      step="0.01"
                      value={settings.delta_high}
                      onChange={(e) => setSettings({...settings, delta_high: parseFloat(e.target.value) || 0})}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                    />
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-gray-200">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Soglia Impressions Basse
                  </label>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500 text-sm">&lt;</span>
                    <input
                      type="number"
                      step="10"
                      value={settings.low_impressions_threshold}
                      onChange={(e) => setSettings({...settings, low_impressions_threshold: parseInt(e.target.value) || 0})}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                    />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">Se impressioni 30d &lt; soglia</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Delta Impressions Basse
                  </label>
                  <div className="flex items-center gap-2">
                    <span className="text-green-600 text-sm">+$</span>
                    <input
                      type="number"
                      step="0.01"
                      value={settings.delta_low_impressions}
                      onChange={(e) => setSettings({...settings, delta_low_impressions: parseFloat(e.target.value) || 0})}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                    />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">Aumenta bid per ottenere visibilita</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Max Clicks Low Impressions
                  </label>
                  <div className="flex items-center gap-2">
                    <span className="text-blue-500 text-sm">&lt;</span>
                    <input
                      type="number"
                      step="1"
                      min="0"
                      value={settings.max_clicks_for_low_impressions}
                      onChange={(e) => setSettings({...settings, max_clicks_for_low_impressions: parseInt(e.target.value) || 0})}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                    />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">Incremento solo se clicks &lt; soglia (0 = disattivato)</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Max Clicks No Sales
                  </label>
                  <div className="flex items-center gap-2">
                    <span className="text-red-500 text-sm">&#x23F8;</span>
                    <input
                      type="number"
                      step="1"
                      min="0"
                      value={settings.max_clicks_no_sales}
                      onChange={(e) => setSettings({...settings, max_clicks_no_sales: parseInt(e.target.value) || 0})}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                    />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">PAUSA se clicks &ge; soglia e 0 vendite (0 = disattivato)</p>
                </div>
              </div>
              <div className="mt-4 flex justify-end">
                <button
                  onClick={saveSettings}
                  disabled={savingSettings}
                  className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                >
                  {savingSettings ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  Salva Impostazioni
                </button>
              </div>
              </div>
            </div>
          </div>
        )}

        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-5 py-3.5 border-b border-gray-100 flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-cyan-400"></div>
            <h2 className="text-sm font-semibold text-gray-900">Marketplace</h2>
            <span className="text-xs text-gray-400 font-medium">{profiles.filter(p => p.enabled).length} attivi su {profiles.length}</span>
            {loadingProfiles && <Loader2 className="w-4 h-4 animate-spin text-gray-400 ml-auto" />}
          </div>
          
          {loadingProfiles ? (
            <div className="p-8 flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-[#00D4FF]" />
            </div>
          ) : profiles.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No profiles found. Connect an Amazon Ads account first.
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {profiles.map((profile) => (
                <div key={profile.profile_id} className="hover:bg-gray-50">
                  <div className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => toggleProfileExpanded(profile.profile_id)}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        {expandedProfiles.has(profile.profile_id) ? (
                          <ChevronDown className="w-5 h-5" />
                        ) : (
                          <ChevronRight className="w-5 h-5" />
                        )}
                      </button>
                      <span className="text-xl">{getCountryFlag(profile.country_code)}</span>
                      <div>
                        <div className="font-medium text-gray-900">
                          {profile.marketplace || profile.country_code}
                        </div>
                        <div className="text-sm text-gray-500">
                          {({'3_hours': 'Ogni 3 ore', 'daily': 'Ogni giorno', '3_days': 'Ogni 3 giorni', '5_days': 'Ogni 5 giorni'} as Record<string, string>)[profile.cadence] || profile.cadence}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      {selectedAccount && (
                        <div className="flex items-center gap-2">
                          <select
                            value={profile.cadence || 'daily'}
                            onChange={async (e) => {
                              const newCadence = e.target.value;
                              setToggling(profile.profile_id);
                              try {
                                await api.post(`/autopilot/profiles/${selectedAccount.id}`, {
                                  profile_ids: [profile.profile_id],
                                  enabled: profile.enabled,
                                  cadence: newCadence
                                });
                                await loadProfiles(selectedAccount.id);
                              } catch (err: any) {
                                console.error('Failed to update cadence:', err);
                              } finally {
                                setToggling(null);
                              }
                            }}
                            disabled={toggling === profile.profile_id}
                            className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-gray-50 text-gray-700 font-medium focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:border-cyan-400"
                          >
                            <option value="3_hours">Ogni 3 ore</option>
                            <option value="daily">Ogni giorno</option>
                            <option value="3_days">Ogni 3 giorni</option>
                            <option value="5_days">Ogni 5 giorni</option>
                          </select>
                          <SettingsProfilesManager 
                            accountId={selectedAccount.id}
                            compact={true}
                            refreshKey={settingsProfilesRefreshKey}
                            selectedProfileId={
                              pendingSettingsProfile[profile.profile_id] !== undefined 
                                ? (pendingSettingsProfile[profile.profile_id] || undefined)
                                : (profile.settings_profile_id || undefined)
                            }
                            onProfileSelect={(profileId) => {
                              setPendingSettingsProfile(prev => ({
                                ...prev,
                                [profile.profile_id]: profileId === 0 ? null : profileId
                              }));
                            }}
                          />
                          <button
                            onClick={() => saveSettingsProfileAssignment(profile.profile_id)}
                            disabled={savingSettingsProfile === profile.profile_id || pendingSettingsProfile[profile.profile_id] === undefined}
                            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${pendingSettingsProfile[profile.profile_id] !== undefined ? 'bg-[#00D4FF] text-white hover:bg-[#00b8d9] opacity-100' : 'opacity-0 pointer-events-none'}`}
                            style={{ minWidth: '80px' }}
                          >
                            {savingSettingsProfile === profile.profile_id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Check className="w-4 h-4" />
                            )}
                            Salva
                          </button>
                        </div>
                      )}
                      {profile.enabled && profile.next_run_at && (
                            <div className="text-sm text-gray-500 flex items-center gap-1">
                              <Clock className="w-4 h-4" />
                              Next: {new Date(profile.next_run_at).toLocaleDateString()}
                            </div>
                          )}
                          <button
                            onClick={() => toggleAutopilot(profile)}
                            disabled={toggling === profile.profile_id}
                            className="flex items-center gap-2"
                          >
                            <div className={`w-9 h-5 rounded-full transition-colors duration-200 relative ${profile.enabled ? 'bg-cyan-500' : 'bg-gray-300'} ${toggling === profile.profile_id ? 'opacity-50' : ''}`}>
                              <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${profile.enabled ? 'translate-x-[14px]' : 'translate-x-0.5'}`} />
                            </div>
                          </button>
                        </div>
                      </div>
                      
                      {expandedProfiles.has(profile.profile_id) && (
                        <div className="px-4 pb-4 pl-12">
                          <div className="bg-gray-50 rounded-lg p-4">
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="font-medium text-gray-700 flex items-center gap-2">
                                <Book className="w-4 h-4" />
                                Books in this profile
                              </h4>
                              <button
                                onClick={() => loadBooksForProfile(profile.profile_id)}
                                className="text-sm text-[#00D4FF] hover:text-[#0F1D32]"
                              >
                                <RefreshCw className={`w-4 h-4 ${loadingBooksFor === profile.profile_id ? 'animate-spin' : ''}`} />
                              </button>
                            </div>
                            {loadingBooksFor === profile.profile_id ? (
                              <div className="text-center py-4">
                                <Loader2 className="w-5 h-5 animate-spin text-[#00D4FF] mx-auto" />
                              </div>
                            ) : (booksMap[profile.profile_id]?.length || 0) === 0 ? (
                              <p className="text-sm text-gray-500">
                                No books tracked yet. Books will be automatically detected from your campaigns.
                              </p>
                            ) : (
                              <div className="space-y-3">
                                {(booksMap[profile.profile_id] || []).slice(0, 10).map((book: ProfileBook) => (
                                  <div key={book.asin} className="bg-white rounded-lg p-3 border border-gray-200">
                                    <div className="flex gap-3">
                                      {book.image_url ? (
                                        <a href={book.amazon_url || '#'} target="_blank" rel="noopener noreferrer" className="flex-shrink-0">
                                          <img src={book.image_url} alt={book.title || book.asin} className="h-24 w-auto object-contain rounded shadow-sm" />
                                        </a>
                                      ) : (
                                        <div className="w-16 h-24 bg-gray-100 rounded flex items-center justify-center flex-shrink-0">
                                          <Book className="w-6 h-6 text-gray-400" />
                                        </div>
                                      )}
                                      <div className="flex-1 min-w-0">
                                        <div className="mb-1">
                                          {book.title ? (
                                            <a href={book.amazon_url || '#'} target="_blank" rel="noopener noreferrer" className="font-medium text-gray-900 hover:text-[#00D4FF] line-clamp-2 text-sm">
                                              {book.title}
                                            </a>
                                          ) : (
                                            <a href={book.amazon_url || '#'} target="_blank" rel="noopener noreferrer" className="font-mono text-gray-900 hover:text-[#00D4FF] text-sm">
                                              {book.asin}
                                            </a>
                                          )}
                                        </div>
                                        {book.author && (
                                          <p className="text-xs text-gray-500 mb-1">by {book.author}</p>
                                        )}
                                        <div className="flex items-center gap-2 text-xs text-gray-400">
                                          <span className="font-mono">{book.asin}</span>
                                          <span className="text-gray-300">|</span>
                                          <span>{book.marketplace || 'US'}</span>
                                        </div>
                                      </div>
                                    </div>
                                    <div className="grid grid-cols-4 gap-2 text-xs mt-3 pt-3 border-t border-gray-100">
                                      <div className="text-center">
                                        <div className="text-gray-500">Prezzo</div>
                                        <div className="font-medium">{book.price ? `$${book.price.toFixed(2)}` : '-'}</div>
                                      </div>
                                      <div className="text-center">
                                        <div className="text-gray-500">Royalty</div>
                                        <div className="font-medium text-green-600">{book.royalty_net ? `$${book.royalty_net.toFixed(2)}` : '-'}</div>
                                      </div>
                                      <div className="text-center">
                                        <div className="text-gray-500">ACOS BE</div>
                                        <div className="font-medium text-[#00D4FF]">{book.acos_be ? `${book.acos_be.toFixed(1)}%` : '-'}</div>
                                      </div>
                                      <div className="text-center">
                                        <div className="text-gray-500">ACOS Opt</div>
                                        <div className="font-medium text-purple-600">{book.acos_opt ? `${book.acos_opt.toFixed(1)}%` : '-'}</div>
                                      </div>
                                    </div>
                                    {book.acos_actual && (
                                      <div className="mt-2 pt-2 border-t border-gray-100">
                                        <span className={`text-xs px-2 py-0.5 rounded ${book.acos_be && book.acos_actual > book.acos_be ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                                          ACOS Attuale: {book.acos_actual.toFixed(1)}%
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                ))}
                                {(booksMap[profile.profile_id]?.length || 0) > 10 && (
                                  <p className="text-sm text-gray-500 text-center">
                                    +{(booksMap[profile.profile_id]?.length || 0) - 10} altri libri
                                  </p>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            )}
          </div>

        {/* Actions Panel - Always Visible */}
        <div className="bg-white rounded-xl shadow-sm border border-cyan-200 mb-6">
            <div className="p-4 border-b border-cyan-100 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-cyan-600" />
                Azioni Pianificate ({actionsSummary.total})
                {actionsSummary.total > 0 && (
                  <span className="ml-2 text-sm font-normal text-gray-500">
                    ({actionsSummary.increases} aumenti, {actionsSummary.decreases} diminuzioni)
                  </span>
                )}
              </h2>
              <div className="flex items-center gap-2">
                <button onClick={() => { loadPlannedActions(); loadActionFilters(); }} disabled={loadingActions} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-cyan-600 hover:bg-cyan-50 rounded-lg border border-gray-200">
                  {loadingActions ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  Refresh
                </button>
                <button onClick={clearPlannedActions} disabled={clearingActions || actionsSummary.total === 0} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg border border-red-200 disabled:opacity-50">
                  {clearingActions ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                  Svuota
                </button>
              </div>
            </div>
            <div className="p-4">
              {loadingActions ? (
                <div className="flex justify-center py-4">
                  <Loader2 className="w-5 h-5 animate-spin text-cyan-600" />
                </div>
              ) : plannedActions.length === 0 ? (
                <p className="text-gray-500 text-sm">Nessuna azione pianificata. Esegui un Refresh per analizzare i dati e generare le azioni.</p>
              ) : (
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-3 mb-4">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => { loadPlannedActions(); loadActionFilters(); }}
                        className="p-1 text-gray-400 hover:text-cyan-600 hover:bg-cyan-50 rounded"
                        title="Ricarica azioni e filtri"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                      <Filter className="w-4 h-4 text-gray-400" />
                      <select
                        value={filterAdProduct}
                        onChange={(e) => setFilterAdProduct(e.target.value)}
                        className="text-xs border border-cyan-300 rounded px-2 py-1 bg-cyan-50 font-medium"
                      >
                        <option value="">SP/SB</option>
                        <option value="SP">SP</option>
                        <option value="SB">SB</option>
                      </select>
                      <select
                        value={filterCampaign}
                        onChange={(e) => setFilterCampaign(e.target.value)}
                        className="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
                      >
                        <option value="">Tutte le campagne</option>
                        {allCampaigns.map(c => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                      <select
                        value={filterTargetType}
                        onChange={(e) => setFilterTargetType(e.target.value)}
                        className="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
                      >
                        <option value="">Tutti i tipi</option>
                        {allTargetTypes.map(t => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                      <select
                        value={filterReason}
                        onChange={(e) => setFilterReason(e.target.value)}
                        className="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
                      >
                        <option value="">Tutti i motivi</option>
                        {allReasons.map(r => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                      {(filterCampaign || filterTargetType || filterReason || filterAdProduct) && (
                        <button
                          onClick={() => { setFilterCampaign(''); setFilterTargetType(''); setFilterReason(''); setFilterAdProduct(''); }}
                          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
                        >
                          <X className="w-3 h-3" /> Reset
                        </button>
                      )}
                    </div>
                    {/* Bottone Esegui temporaneamente disattivato
                    <div className="ml-auto">
                      <button
                        onClick={() => {
                          const profileId = plannedActions[0]?.profile_id;
                          if (profileId) executeActions(profileId);
                        }}
                        disabled={executingActions || plannedActions.length === 0}
                        className="px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 disabled:opacity-50 flex items-center gap-2 text-sm"
                      >
                        {executingActions ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
                        Esegui {plannedActions.length} azioni
                      </button>
                    </div>
                    */}
                  </div>
                  <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                    <table className="w-full text-xs table-fixed">
                      <thead className="bg-gray-50 text-gray-600 text-xs sticky top-0">
                        <tr>
                          <th className="w-[40px] px-1.5 py-1.5 text-center cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('ad_product')}>
                            <div className="flex items-center justify-center gap-0.5">
                              Tipo
                              {sortColumn === 'ad_product' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[70px] px-1.5 py-1.5 text-left">Account</th>
                          <th className="w-[30px] px-1 py-1.5 text-center">Mkt</th>
                          <th className="px-1.5 py-1.5 text-left cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('keyword')}>
                            <div className="flex items-center gap-0.5">
                              Keyword/Target
                              {sortColumn === 'keyword' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[130px] px-1.5 py-1.5 text-left cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('campaign')}>
                            <div className="flex items-center gap-0.5">
                              Campagna
                              {sortColumn === 'campaign_name' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[55px] px-1 py-1.5 text-right cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('current_bid')}>
                            <div className="flex items-center justify-end gap-0.5">
                              Bid
                              {sortColumn === 'current_bid' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[48px] px-1 py-1.5 text-right cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('delta_bid')}>
                            <div className="flex items-center justify-end gap-0.5">
                              Delta
                              {sortColumn === 'delta_bid' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[55px] px-1 py-1.5 text-right cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('new_bid')}>
                            <div className="flex items-center justify-end gap-0.5">
                              Nuovo
                              {sortColumn === 'new_bid' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[50px] px-1 py-1.5 text-right cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('acos_30d')}>
                            <div className="flex items-center justify-end gap-0.5">
                              ACOS
                              {sortColumn === 'acos_30d' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[45px] px-1 py-1.5 text-right cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('impressions_30d')}>
                            <div className="flex items-center justify-end gap-0.5">
                              Impr
                              {sortColumn === 'impressions_30d' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[40px] px-1 py-1.5 text-right cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('clicks')}>
                            <div className="flex items-center justify-end gap-0.5">
                              Click
                              {sortColumn === 'clicks' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[38px] px-1 py-1.5 text-right cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('purchases_30d')}>
                            <div className="flex items-center justify-end gap-0.5">
                              Ord
                              {sortColumn === 'purchases_30d' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[90px] px-1.5 py-1.5 text-left cursor-pointer hover:bg-gray-100 select-none" onClick={() => handleSort('reason')}>
                            <div className="flex items-center gap-0.5">
                              Motivo
                              {sortColumn === 'reason' && (sortDirection === 'asc' ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />)}
                            </div>
                          </th>
                          <th className="w-[36px] px-1 py-1.5 text-center">Test</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {plannedActions.map((action) => (
                          <tr key={action.id} className="hover:bg-gray-50">
                            <td className="px-1.5 py-1 text-center">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${action.ad_product === 'SB' ? 'bg-purple-100 text-purple-700' : 'bg-cyan-50 text-[#00A8CC]'}`}>
                                {action.ad_product || 'SP'}
                              </span>
                            </td>
                            <td className="px-1.5 py-1 text-gray-600 text-[11px] truncate" title={action.account_name || ''}>
                              {action.account_name || '-'}
                            </td>
                            <td className="px-1 py-1 text-center">
                              <span className="text-sm">{getCountryFlag(action.marketplace || '')}</span>
                            </td>
                            <td className="px-1.5 py-1">
                              <div className="font-medium text-gray-900 truncate text-[11px]" title={action.keyword}>
                                {action.keyword || action.keyword_id}
                              </div>
                              {action.asin && (
                                <div className="text-[10px] text-gray-400 truncate">{action.asin}</div>
                              )}
                            </td>
                            <td className="px-1.5 py-1 text-gray-600 truncate text-[11px]" title={action.campaign_name}>
                              {action.campaign_name || '-'}
                            </td>
                            <td className="px-1 py-1 text-right font-mono text-gray-700 text-[11px]">
                              {action.current_bid != null ? `€${action.current_bid.toFixed(2)}` : '-'}
                            </td>
                            <td className={`px-1 py-1 text-right font-mono font-semibold text-[11px] ${action.delta_bid > 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {action.delta_bid > 0 ? '+' : ''}{action.delta_bid.toFixed(2)}
                            </td>
                            <td className="px-1 py-1 text-right font-mono text-gray-900 font-semibold text-[11px]">
                              {action.new_bid != null ? `€${action.new_bid.toFixed(2)}` : '-'}
                            </td>
                            <td className="px-1 py-1 text-right text-[11px]">
                              {action.acos_30d != null ? (
                                <span className={`${action.acos_30d > 0.5 ? 'text-red-600' : action.acos_30d < 0.2 ? 'text-green-600' : 'text-gray-700'}`}>
                                  {(action.acos_30d * 100).toFixed(1)}%
                                </span>
                              ) : '-'}
                            </td>
                            <td className="px-1 py-1 text-right text-gray-600 text-[11px]">
                              {action.impressions_30d != null ? action.impressions_30d.toLocaleString() : '-'}
                            </td>
                            <td className="px-1 py-1 text-right text-gray-600 text-[11px]">
                              {action.clicks != null ? action.clicks.toLocaleString() : '-'}
                            </td>
                            <td className="px-1 py-1 text-right text-gray-600 font-medium text-[11px]">
                              {action.purchases_30d != null && action.purchases_30d > 0 ? action.purchases_30d : '-'}
                            </td>
                            <td className="px-1.5 py-1 text-[10px] text-gray-500 truncate" title={action.reason}>
                              {action.reason?.substring(0, 30) || '-'}
                            </td>
                            <td className="px-1 py-1 text-center">
                              <button
                                onClick={() => executeSingleAction(action.id)}
                                disabled={executingAction === action.id}
                                className="px-1.5 py-0.5 text-[10px] bg-cyan-50 text-[#00A8CC] rounded hover:bg-blue-200 disabled:opacity-50"
                              >
                                {executingAction === action.id ? '...' : 'Test'}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600">Righe per pagina:</span>
                        <select
                          value={pageSize}
                          onChange={(e) => changePageSize(parseInt(e.target.value))}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value={100}>100</option>
                          <option value={200}>200</option>
                          <option value={500}>500</option>
                          <option value={-1}>Tutti</option>
                        </select>
                      </div>
                      
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => goToPage(1)}
                          disabled={currentPage === 1 || loadingActions}
                          className="px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          «
                        </button>
                        <button
                          onClick={() => goToPage(currentPage - 1)}
                          disabled={currentPage === 1 || loadingActions}
                          className="px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          ‹
                        </button>
                        
                        {pageSize !== -1 && totalPages > 0 && (
                          <>
                            {[...Array(Math.min(5, totalPages))].map((_, i) => {
                              let pageNum: number;
                              if (totalPages <= 5) {
                                pageNum = i + 1;
                              } else if (currentPage <= 3) {
                                pageNum = i + 1;
                              } else if (currentPage >= totalPages - 2) {
                                pageNum = totalPages - 4 + i;
                              } else {
                                pageNum = currentPage - 2 + i;
                              }
                              return (
                                <button
                                  key={pageNum}
                                  onClick={() => goToPage(pageNum)}
                                  disabled={loadingActions}
                                  className={`px-3 py-1 text-sm rounded ${
                                    currentPage === pageNum
                                      ? 'bg-indigo-600 text-white'
                                      : 'bg-gray-100 hover:bg-gray-200'
                                  } disabled:opacity-50`}
                                >
                                  {pageNum}
                                </button>
                              );
                            })}
                          </>
                        )}
                        
                        <button
                          onClick={() => goToPage(currentPage + 1)}
                          disabled={currentPage >= totalPages || pageSize === -1 || loadingActions}
                          className="px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          ›
                        </button>
                        <button
                          onClick={() => goToPage(totalPages)}
                          disabled={currentPage >= totalPages || pageSize === -1 || loadingActions}
                          className="px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          »
                        </button>
                      </div>
                      
                      <p className="text-sm text-gray-500">
                        {pageSize === -1 
                          ? `${actionsSummary.total} azioni totali`
                          : `Pagina ${currentPage} di ${totalPages} (${actionsSummary.total} totali)`
                        }
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

        {bigBangJobs.length > 0 && (() => {
          const sortedJobs = getSortedJobs();
          const displayJobs = historyPageSize === -1 ? sortedJobs : sortedJobs.slice(0, historyPageSize);
          const SortIcon = ({ col }: { col: string }) => historySortCol === col ? (historySortDir === 'asc' ? <ArrowUp className="w-2.5 h-2.5 inline ml-0.5" /> : <ArrowDown className="w-2.5 h-2.5 inline ml-0.5" />) : null;
          return (
          <div className="mb-6 bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Clock className="w-5 h-5 text-gray-600" />
                Storico Job ({bigBangJobs.length})
              </h3>
              <div className="flex items-center gap-3">
                <select
                  value={historyPageSize}
                  onChange={(e) => setHistoryPageSize(parseInt(e.target.value))}
                  className="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
                >
                  <option value={5}>5</option>
                  <option value={100}>100</option>
                  <option value={-1}>TUTTI</option>
                </select>
                <button
                  onClick={loadBigBangJobs}
                  disabled={loadingBigBangJobs}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded transition-colors"
                >
                  {loadingBigBangJobs ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
            <div className="p-4">
              <div className={`overflow-x-auto ${historyPageSize === -1 || historyPageSize > 5 ? 'max-h-[400px] overflow-y-auto' : ''}`}>
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-white">
                    <tr className="bg-gray-100">
                      <th className="px-2 py-1.5 text-left cursor-pointer hover:bg-gray-200 select-none" onClick={() => handleHistorySort('id')}>ID<SortIcon col="id" /></th>
                      <th className="px-2 py-1.5 text-left cursor-pointer hover:bg-gray-200 select-none" onClick={() => handleHistorySort('ad_product')}>Tipo<SortIcon col="ad_product" /></th>
                      <th className="px-2 py-1.5 text-left cursor-pointer hover:bg-gray-200 select-none" onClick={() => handleHistorySort('status')}>Stato<SortIcon col="status" /></th>
                      <th className="px-2 py-1.5 text-left cursor-pointer hover:bg-gray-200 select-none" onClick={() => handleHistorySort('execute_at')}>Esecuzione<SortIcon col="execute_at" /></th>
                      <th className="px-2 py-1.5 text-left cursor-pointer hover:bg-gray-200 select-none" onClick={() => handleHistorySort('created_at')}>Creato<SortIcon col="created_at" /></th>
                      <th className="px-2 py-1.5 text-center">Pianificate</th>
                      <th className="px-2 py-1.5 text-center">Eseguite</th>
                      <th className="px-2 py-1.5 text-left">Azioni</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayJobs.map((job: any) => (
                      <tr key={job.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="px-2 py-1.5 font-mono">{job.id}</td>
                        <td className="px-2 py-1.5">
                          <span className={`px-1.5 py-0.5 rounded text-xs ${job.ad_product === 'SP' ? 'bg-red-100 text-red-700' : job.ad_product === 'SB' ? 'bg-pink-100 text-pink-700' : 'bg-gray-100 text-gray-700'}`}>
                            {job.ad_product || 'ALL'}
                          </span>
                        </td>
                        <td className="px-2 py-1.5">
                          <span className={`px-1.5 py-0.5 rounded text-xs ${
                            job.status === 'RUNNING' ? 'bg-cyan-100 text-cyan-700' :
                            job.status === 'SCHEDULED' ? 'bg-blue-100 text-blue-700' :
                            job.status === 'COMPLETED' ? 'bg-green-100 text-green-700' :
                            job.status === 'CANCELLED' ? 'bg-gray-100 text-gray-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {job.status}
                          </span>
                        </td>
                        <td className="px-2 py-1.5">
                          {job.execute_at ? new Date(job.execute_at + 'Z').toLocaleString('it-IT', {hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit'}) : '-'}
                        </td>
                        <td className="px-2 py-1.5">
                          {job.created_at ? new Date(job.created_at + 'Z').toLocaleString('it-IT', {hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit'}) : '-'}
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <button
                            onClick={() => downloadJobExport(job.id, 'PLANNED')}
                            disabled={downloadingExport === `${job.id}_PLANNED`}
                            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-cyan-50 text-cyan-700 border border-cyan-200 rounded text-[10px] hover:bg-cyan-100 disabled:opacity-40 transition-colors"
                            title="Scarica XLSX azioni pianificate"
                          >
                            {downloadingExport === `${job.id}_PLANNED` ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Download className="w-2.5 h-2.5" />}
                            XLSX
                          </button>
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <button
                            onClick={() => downloadJobExport(job.id, 'EXECUTED')}
                            disabled={downloadingExport === `${job.id}_EXECUTED`}
                            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-purple-50 text-purple-700 border border-purple-200 rounded text-[10px] hover:bg-purple-100 disabled:opacity-40 transition-colors"
                            title="Scarica XLSX azioni eseguite"
                          >
                            {downloadingExport === `${job.id}_EXECUTED` ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Download className="w-2.5 h-2.5" />}
                            XLSX
                          </button>
                        </td>
                        <td className="px-2 py-1.5">
                          {(job.status === 'RUNNING' || job.status === 'SCHEDULED') && (
                            <button
                              onClick={() => cancelBigBangJob(job.id)}
                              className="text-red-600 hover:text-red-800 text-xs"
                            >
                              Annulla
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          );
        })()}

        {/* ── Search Term Report ─────────────────────────────────────────── */}
        <div className="mt-6 p-5 bg-white border border-gray-200 rounded-xl shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-semibold text-gray-900">Search Term Report</h3>
              <p className="text-xs text-gray-500 mt-0.5">SP — solo i marketplace selezionati</p>
            </div>
            {strJob?.status === 'DONE' && (
              <span className="text-xs font-medium px-2 py-1 bg-green-100 text-green-700 rounded-full">
                ✓ {strJob.total_rows?.toLocaleString()} righe pronte
              </span>
            )}
            {strJob?.status === 'RUNNING' && (
              <span className="flex items-center gap-1.5 text-xs font-medium px-2 py-1 bg-blue-100 text-blue-700 rounded-full">
                <Loader2 className="w-3 h-3 animate-spin" /> Generazione in corso...
              </span>
            )}
            {strJob?.status === 'TIMEOUT' && (
              <span className="text-xs font-medium px-2 py-1 bg-red-100 text-red-700 rounded-full">
                ✗ Timeout — riprova
              </span>
            )}
          </div>

          {/* Controlli */}
          <div className="flex items-center gap-3 flex-wrap mb-4">
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500 font-medium">Da</label>
              <input type="date" value={strStartDate} onChange={e => setStrStartDate(e.target.value)}
                className="px-2 py-1.5 border border-gray-300 rounded-lg text-xs w-34" />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500 font-medium">A</label>
              <input type="date" value={strEndDate} onChange={e => setStrEndDate(e.target.value)}
                className="px-2 py-1.5 border border-gray-300 rounded-lg text-xs w-34" />
            </div>
            <button
              onClick={submitStrJob}
              disabled={strSubmitting || strJob?.status === 'RUNNING' || profiles.length === 0 || !selectedAccount?.id}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {strSubmitting ? <Loader2 className="w-3 h-3 animate-spin" /> : <PlayCircle className="w-3 h-3" />}
              {strSubmitting ? 'Avvio...' : 'Avvia Report'}
            </button>
            {strJob?.status === 'DONE' && (
              <button
                onClick={downloadStrReport}
                disabled={strDownloading}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-green-600 text-white rounded-lg text-xs font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                {strDownloading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                Scarica JSON
              </button>
            )}
            {strJob && (
              <button onClick={() => setStrJob(null)} className="text-gray-400 hover:text-gray-600 transition-colors" title="Reset">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Profili selezionati */}
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <span className="text-xs text-gray-500 font-medium">Marketplace:</span>
            {profiles.length === 0 ? (
              <span className="text-xs text-amber-600">Nessun marketplace selezionato — seleziona profili dalla sidebar</span>
            ) : profiles.map(p => (
              <span key={p.profile_id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-700 rounded-full text-xs font-medium">
                {getCountryFlag(p.country_code)} {p.marketplace || p.country_code}
              </span>
            ))}
          </div>

          {/* Tabella report sottomessi */}
          {strJob && strJob.items.length > 0 && (
            <div className="mt-3 border border-gray-200 rounded-lg overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium">Marketplace</th>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium">Periodo</th>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium">Amazon Report ID</th>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium">Stato</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {strJob.items.map((item, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium text-gray-800">
                        {getCountryFlag(item.country_code)} {item.marketplace || item.country_code}
                      </td>
                      <td className="px-3 py-2 text-gray-600">
                        {item.chunk_start} → {item.chunk_end}
                      </td>
                      <td className="px-3 py-2 font-mono text-gray-500">
                        {item.report_id ? (
                          <span className="flex items-center gap-1">
                            <span className="truncate max-w-[200px]" title={item.report_id}>{item.report_id}</span>
                            <button onClick={() => navigator.clipboard.writeText(item.report_id!)}
                              className="text-gray-400 hover:text-gray-600 flex-shrink-0" title="Copia ID">
                              <Copy className="w-3 h-3" />
                            </button>
                          </span>
                        ) : <span className="text-red-400">—</span>}
                      </td>
                      <td className="px-3 py-2">
                        {item.status === 'PENDING' && (
                          <span className="flex items-center gap-1 text-blue-600">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            {item.amazon_status === 'IN_PROGRESS' ? 'In elaborazione...' : item.amazon_status === 'PENDING' ? 'In coda...' : item.amazon_status || 'In attesa'}
                          </span>
                        )}
                        {item.status === 'SUCCESS' && (
                          <span className="flex items-center gap-1 text-green-600">
                            <CheckCircle2 className="w-3 h-3" /> Completato
                          </span>
                        )}
                        {item.status === 'FAILED' && (
                          <span className="flex items-center gap-1 text-red-600" title={item.error}>
                            <XCircle className="w-3 h-3" /> Fallito
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="mt-6">
          <button
            onClick={() => setShowAdvancedTools(!showAdvancedTools)}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors border border-gray-300"
          >
            {showAdvancedTools ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            Strumenti Avanzati
          </button>
          {showAdvancedTools && (
            <div className="mt-3 p-4 bg-gray-50 border border-gray-200 rounded-lg shadow-sm space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-500 w-24 font-medium">NEXUS:</span>
                <button
                  onClick={() => startBigBang('SP')}
                  disabled={bigBangRunning || bigBangJob?.status === 'RUNNING'}
                  className="flex items-center gap-1.5 bg-red-500 text-white font-medium text-xs px-3 py-1.5 rounded-lg hover:bg-red-600 transition-colors disabled:opacity-40"
                >
                  {bigBangRunning && bigBangAdProduct === 'SP' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                  SP
                </button>
                <button
                  onClick={() => startBigBang('SB')}
                  disabled={bigBangRunning || bigBangJob?.status === 'RUNNING'}
                  className="flex items-center gap-1.5 bg-pink-500 text-white font-medium text-xs px-3 py-1.5 rounded-lg hover:bg-pink-600 transition-colors disabled:opacity-40"
                >
                  {bigBangRunning && bigBangAdProduct === 'SB' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                  SB
                </button>
                <button
                  onClick={startBigBangAll}
                  disabled={bigBangRunning || bigBangJob?.status === 'RUNNING'}
                  className="flex items-center gap-1.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-medium text-xs px-3 py-1.5 rounded-lg hover:from-blue-600 hover:to-blue-700 transition-all disabled:opacity-40 shadow-sm"
                >
                  {bigBangRunning && bigBangAdProduct === 'ALL' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                  SP + SB
                </button>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-500 w-24 font-medium">Pipeline:</span>
                <button
                  onClick={stepFetchAsins}
                  disabled={fetchingAsins}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500 text-white rounded-lg text-xs hover:bg-purple-600 disabled:opacity-50 font-medium transition-colors"
                >
                  {fetchingAsins ? <Loader2 className="w-3 h-3 animate-spin" /> : <Book className="w-3 h-3" />}
                  1. ASIN
                </button>
                <button
                  onClick={stepRequestReports}
                  disabled={requestingReports}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-500 text-white rounded-lg text-xs hover:bg-cyan-600 disabled:opacity-50 font-medium transition-colors"
                >
                  {requestingReports ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                  2. Report
                </button>
                <span className="text-gray-300">|</span>
                <button
                  onClick={() => { setShowReportsPanel(!showReportsPanel); if (!showReportsPanel) loadAccountReports(); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border font-medium transition-colors ${showReportsPanel ? 'bg-purple-50 border-purple-200 text-purple-700' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'}`}
                >
                  <Clock className="w-3 h-3" />
                  Reports
                </button>
                <span className="text-gray-300">|</span>
                <button
                  onClick={clearPlannedActions}
                  disabled={clearingActions || actionsSummary.total === 0}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-600 border border-red-200 rounded-lg text-xs hover:bg-red-100 disabled:opacity-40 font-medium transition-colors"
                >
                  {clearingActions ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                  Svuota Azioni
                </button>
                <button
                  onClick={deleteReports}
                  disabled={deletingReports}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-600 border border-red-200 rounded-lg text-xs hover:bg-red-100 disabled:opacity-40 font-medium transition-colors"
                >
                  {deletingReports ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                  Elimina Report
                </button>
                <span className="text-gray-300">|</span>
                <button
                  onClick={() => exportActionsXlsx('PLANNED')}
                  disabled={exportingActionsXlsx}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-50 text-cyan-700 border border-cyan-200 rounded-lg text-xs hover:bg-cyan-100 disabled:opacity-40 font-medium transition-colors"
                >
                  {exportingActionsXlsx ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                  Pianificate XLSX
                </button>
                <button
                  onClick={() => exportActionsXlsx('EXECUTED')}
                  disabled={exportingActionsXlsx}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-50 text-purple-700 border border-purple-200 rounded-lg text-xs hover:bg-purple-100 disabled:opacity-40 font-medium transition-colors"
                >
                  {exportingActionsXlsx ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                  Eseguite XLSX
                </button>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-500 w-24 font-medium">Pianificazione:</span>
                <button
                  onClick={() => stepPlanActions('AUTO')}
                  disabled={planningActions}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-600 text-white rounded-lg text-xs hover:bg-cyan-700 disabled:opacity-50 font-medium"
                >
                  {planningActions ? <Loader2 className="w-3 h-3 animate-spin" /> : <TrendingUp className="w-3 h-3" />}
                  3. Auto
                </button>
                <button
                  onClick={() => stepPlanActions('SP_MANUAL')}
                  disabled={planningActions}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-600 text-white rounded-lg text-xs hover:bg-cyan-700 disabled:opacity-50 font-medium"
                >
                  {planningActions ? <Loader2 className="w-3 h-3 animate-spin" /> : <TrendingUp className="w-3 h-3" />}
                  4. SP Man
                </button>
                <button
                  onClick={() => stepPlanActions('SB')}
                  disabled={planningActions}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-pink-600 text-white rounded-lg text-xs hover:bg-pink-700 disabled:opacity-50 font-medium"
                >
                  {planningActions ? <Loader2 className="w-3 h-3 animate-spin" /> : <TrendingUp className="w-3 h-3" />}
                  5. SB
                </button>
                <span className="text-gray-300">|</span>
                <button
                  onClick={() => scheduleActions(1)}
                  disabled={schedulingActions || actionsSummary.total === 0}
                  className="flex items-center gap-1.5 px-2 py-1.5 bg-[#00D4FF] text-white rounded-lg text-xs hover:bg-[#00A8CC] disabled:opacity-50 font-medium"
                >
                  {schedulingActions ? <Loader2 className="w-3 h-3 animate-spin" /> : <Clock className="w-3 h-3" />}
                  1h
                </button>
                <button
                  onClick={() => scheduleActions(2)}
                  disabled={schedulingActions || actionsSummary.total === 0}
                  className="flex items-center gap-1.5 px-2 py-1.5 bg-[#00D4FF] text-white rounded-lg text-xs hover:bg-[#00A8CC] disabled:opacity-50 font-medium"
                >
                  2h
                </button>
                <button
                  onClick={() => scheduleActions(3)}
                  disabled={schedulingActions || actionsSummary.total === 0}
                  className="flex items-center gap-1.5 px-2 py-1.5 bg-blue-700 text-white rounded-lg text-xs hover:bg-blue-800 disabled:opacity-50 font-medium"
                >
                  3h
                </button>
                <span className="text-gray-300">|</span>
                <button
                  onClick={stepExecuteActions}
                  disabled={executingActions || actionsSummary.total === 0}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs hover:bg-green-700 disabled:opacity-50 font-medium"
                >
                  {executingActions ? <Loader2 className="w-3 h-3 animate-spin" /> : <PlayCircle className="w-3 h-3" />}
                  6. Esegui
                </button>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-500 w-24 font-medium">Pannelli:</span>
                <button
                  onClick={() => setShowDebugPanel(!showDebugPanel)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border font-medium ${showDebugPanel ? 'bg-red-100 border-red-300 text-red-700' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'}`}
                >
                  <AlertCircle className="w-3 h-3" />
                  Debug ({debugLog.length})
                </button>
                <button
                  onClick={() => { setShowSettingsPanel(!showSettingsPanel); if (!showSettingsPanel) loadSettings(); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border font-medium ${showSettingsPanel ? 'bg-indigo-100 border-indigo-300 text-indigo-700' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'}`}
                >
                  Settings
                </button>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-500 w-24 font-medium">Cache:</span>
                <button
                  onClick={clearLiveBidsCache}
                  disabled={clearingCache}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-600 text-white rounded-lg text-xs hover:bg-yellow-700 disabled:opacity-50 font-medium"
                >
                  {clearingCache ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                  Clear Bid Live
                </button>
                <button
                  onClick={clearAsinCache}
                  disabled={clearingAsinCache}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-600 text-white rounded-lg text-xs hover:bg-cyan-700 disabled:opacity-50 font-medium"
                >
                  {clearingAsinCache ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                  Clear ASIN
                </button>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-500 w-24 font-medium">Export/Test:</span>
                <button
                  onClick={exportCampaigns}
                  disabled={exportingCampaigns}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs hover:bg-green-700 disabled:opacity-50 font-medium"
                >
                  {exportingCampaigns ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                  Campagne JSON
                </button>
                <button
                  onClick={exportTargets}
                  disabled={exportingTargets}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 text-white rounded-lg text-xs hover:bg-teal-700 disabled:opacity-50 font-medium"
                >
                  {exportingTargets ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                  Targets JSON
                </button>
                <span className="text-gray-300">|</span>
                <button
                  onClick={testSbApi}
                  disabled={testingSbApi}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-500 text-white rounded-lg text-xs hover:bg-gray-600 disabled:opacity-50 font-medium"
                >
                  {testingSbApi ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                  Test SB API
                </button>
                <button
                  onClick={testSbReport}
                  disabled={testingSbReport}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-500 text-white rounded-lg text-xs hover:bg-gray-600 disabled:opacity-50 font-medium"
                >
                  {testingSbReport ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                  Test SB Report
                </button>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-500 w-24 font-medium">Tokens:</span>
                <input
                  type="password"
                  value={exportPassword}
                  onChange={(e) => setExportPassword(e.target.value)}
                  placeholder="Password"
                  className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm w-40"
                />
                <button
                  onClick={exportTokens}
                  disabled={exportingTokens || !exportPassword}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 text-white rounded-lg text-xs hover:bg-purple-700 disabled:opacity-50 font-medium"
                >
                  {exportingTokens ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                  Export Tokens
                </button>
                {exportResult && (
                  <button
                    onClick={() => setExportResult(null)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              {exportResult && (
                <div className="mt-2 p-3 bg-white rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">Risultato ({exportResult.total} account)</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(JSON.stringify(exportResult, null, 2))}
                      className="text-xs text-purple-600 hover:text-purple-800"
                    >
                      Copia JSON
                    </button>
                  </div>
                  <pre className="text-xs bg-gray-50 p-3 rounded border overflow-auto max-h-64">
                    {JSON.stringify(exportResult, null, 2)}
                  </pre>
                </div>
              )}
              {sbTestResult && (
                <div className="mt-2 p-3 bg-white rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">SB API Test Result</span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => navigator.clipboard.writeText(JSON.stringify(sbTestResult, null, 2))}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                        title="Copia JSON"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button onClick={() => setSbTestResult(null)} className="text-gray-400 hover:text-gray-600">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <pre className="text-xs bg-gray-50 p-3 rounded border overflow-auto max-h-48">
                    {JSON.stringify(sbTestResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>

        </div>
      </div>
      
      
    </Layout>
  );
}
