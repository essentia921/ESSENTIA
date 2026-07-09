import { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { Zap, Target, Loader2, AlertCircle, Package, FileText, Download, Eye, X, RefreshCw, Copy, Check, ChevronDown, ChevronRight, Play, Bug, Trash2, Bot } from 'lucide-react';
import api from '../lib/api';

interface Profile {
  accountId: number;
  accountName: string;
  profileId: string;
  countryCode: string;
  marketplace: string;
  region: string;
}

interface Campaign {
  campaignId: string;
  campaignName: string;
  state: string;
  budget: number | null;
  asin: string | null;
}

interface Report {
  id: number;
  report_id: string;
  report_type: string;
  profile_id: string;
  start_date: string;
  end_date: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

interface PlannedAction {
  id: number;
  profile_id: string;
  account_id: number;
  account_name: string;
  country_code: string;
  campaign_id: string;
  campaign_name: string;
  keyword_id: string;
  asin: string | null;
  target: string;
  current_bid: number | null;
  delta_bid: number;
  tipo_azione: string;
  created_at: string;
  acos_14d: number | null;
  acos_30d: number | null;
  source?: string;
}

const ALLOWED_COUNTRIES = ['US', 'CA', 'MX', 'BR', 'UK', 'GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'SE', 'PL', 'BE', 'AE', 'SA', 'EG', 'TR', 'IN', 'JP', 'AU', 'SG'];

const getCountryFlag = (countryCode: string) => {
  const flags: Record<string, string> = {
    IT: '🇮🇹', UK: '🇬🇧', GB: '🇬🇧', US: '🇺🇸', DE: '🇩🇪', FR: '🇫🇷',
    ES: '🇪🇸', CA: '🇨🇦', AU: '🇦🇺', MX: '🇲🇽', BR: '🇧🇷', JP: '🇯🇵',
    IN: '🇮🇳', NL: '🇳🇱', SE: '🇸🇪', PL: '🇵🇱', BE: '🇧🇪', AE: '🇦🇪',
    SA: '🇸🇦', EG: '🇪🇬', TR: '🇹🇷', SG: '🇸🇬',
  };
  return flags[countryCode] || '🌍';
};

const getCurrencySymbol = (countryCode: string) => {
  switch (countryCode) {
    case 'US': 
    case 'CA':
    case 'MX':
    case 'AU':
      return '$';
    case 'UK':
    case 'GB':
      return '£';
    case 'JP':
      return '¥';
    default:
      return '€';
  }
};

export default function FlashAgent() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState(true);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  const [loadingReports, setLoadingReports] = useState(false);
  const [generatingReport, setGeneratingReport] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportContent, setReportContent] = useState<any>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [copiedReportId, setCopiedReportId] = useState<string | null>(null);
  const [expandedAccounts, setExpandedAccounts] = useState<Set<string>>(new Set());
  const [showCampaigns, setShowCampaigns] = useState(false);
  const [stateFilter, setStateFilter] = useState<string>('enabled');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [plannedActions, setPlannedActions] = useState<PlannedAction[]>([]);
  const [loadingActions, setLoadingActions] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [showActions, setShowActions] = useState(false);
  const [expandedCampaigns, setExpandedCampaigns] = useState<Set<string>>(new Set());
  const [selectedActionIds, setSelectedActionIds] = useState<Set<number>>(new Set());
  const [executing, setExecuting] = useState(false);
  const [executedActions, setExecutedActions] = useState<PlannedAction[]>([]);
  const [showExecutedHistory, setShowExecutedHistory] = useState(false);
  const [lastExecutionResult, setLastExecutionResult] = useState<any>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionFilterAccount, setActionFilterAccount] = useState<string>('');
  const [actionFilterCountry, setActionFilterCountry] = useState<string>('');
  const [actionFilterAsin, setActionFilterAsin] = useState<string>('');
  const [expandedActionAccounts, setExpandedActionAccounts] = useState<Set<string>>(new Set());
  const [expandedActionProfiles, setExpandedActionProfiles] = useState<Set<string>>(new Set());
  const [analyzingAll, setAnalyzingAll] = useState(false);
  const [generatingAllReports, setGeneratingAllReports] = useState(false);
  const [profilesWithoutReports, setProfilesWithoutReports] = useState<{profile_id: string; account_name: string; country_code: string}[]>([]);
  const [showProfilesWithoutReports, setShowProfilesWithoutReports] = useState(false);
  const [selectedReportIds, setSelectedReportIds] = useState<Set<number>>(new Set());
  const [deletingReports, setDeletingReports] = useState(false);
  const [autopilotStatus, setAutopilotStatus] = useState<{[key: string]: {enabled: boolean; last_run: string | null; next_run: string | null; mode?: string; is_running?: boolean}}>({});
  const [loadingAutopilot, setLoadingAutopilot] = useState(false);
  const [togglingAutopilot, setTogglingAutopilot] = useState<string | null>(null);
  const [runningAutopilot, setRunningAutopilot] = useState(false);
  const [showAutopilotPanel, setShowAutopilotPanel] = useState(false);
  const [autopilotMode, setAutopilotMode] = useState<string>('3d');

  const groupActionsByCampaign = (actions: PlannedAction[]) => {
    const grouped: { [key: string]: { name: string; id: string; asin: string | null; actions: PlannedAction[] } } = {};
    for (const action of actions) {
      if (!grouped[action.campaign_id]) {
        grouped[action.campaign_id] = {
          id: action.campaign_id,
          name: action.campaign_name || action.campaign_id,
          asin: action.asin,
          actions: []
        };
      }
      grouped[action.campaign_id].actions.push(action);
    }
    return Object.values(grouped);
  };

  interface GroupedHierarchy {
    accountId: number;
    accountName: string;
    profiles: {
      profileId: string;
      countryCode: string;
      campaigns: {
        campaignId: string;
        campaignName: string;
        asin: string | null;
        actions: PlannedAction[];
      }[];
    }[];
  }

  const groupActionsHierarchically = (actions: PlannedAction[]): GroupedHierarchy[] => {
    const accountMap: { [key: number]: GroupedHierarchy } = {};
    
    for (const action of actions) {
      const accId = action.account_id || 0;
      if (!accountMap[accId]) {
        accountMap[accId] = {
          accountId: accId,
          accountName: action.account_name || `Account ${accId}`,
          profiles: []
        };
      }
      
      let profile = accountMap[accId].profiles.find(p => p.profileId === action.profile_id);
      if (!profile) {
        profile = {
          profileId: action.profile_id,
          countryCode: action.country_code || '',
          campaigns: []
        };
        accountMap[accId].profiles.push(profile);
      }
      
      let campaign = profile.campaigns.find(c => c.campaignId === action.campaign_id);
      if (!campaign) {
        campaign = {
          campaignId: action.campaign_id,
          campaignName: action.campaign_name || action.campaign_id,
          asin: action.asin,
          actions: []
        };
        profile.campaigns.push(campaign);
      }
      
      campaign.actions.push(action);
    }
    
    return Object.values(accountMap);
  };

  const getFilteredActions = () => {
    return plannedActions.filter(action => {
      if (actionFilterAccount && String(action.account_id) !== actionFilterAccount) return false;
      if (actionFilterCountry && action.country_code !== actionFilterCountry) return false;
      if (actionFilterAsin && action.asin !== actionFilterAsin) return false;
      return true;
    });
  };

  const getUniqueAccounts = () => {
    const unique = new Map<number, string>();
    plannedActions.forEach(a => {
      if (a.account_id && !unique.has(a.account_id)) {
        unique.set(a.account_id, a.account_name || `Account ${a.account_id}`);
      }
    });
    return Array.from(unique.entries()).map(([id, name]) => ({ id, name }));
  };

  const getUniqueCountries = () => {
    const unique = new Set<string>();
    plannedActions.forEach(a => {
      if (a.country_code) unique.add(a.country_code);
    });
    return Array.from(unique);
  };

  const getUniqueAsins = () => {
    const unique = new Set<string>();
    plannedActions.forEach(a => {
      if (a.asin) unique.add(a.asin);
    });
    return Array.from(unique);
  };

  const toggleCampaignExpand = (campaignId: string) => {
    setExpandedCampaigns(prev => {
      const next = new Set(prev);
      if (next.has(campaignId)) {
        next.delete(campaignId);
      } else {
        next.add(campaignId);
      }
      return next;
    });
  };

  const toggleAccountExpand = (accountId: string) => {
    setExpandedActionAccounts(prev => {
      const next = new Set(prev);
      if (next.has(accountId)) {
        next.delete(accountId);
      } else {
        next.add(accountId);
      }
      return next;
    });
  };

  const toggleProfileExpand = (profileId: string) => {
    setExpandedActionProfiles(prev => {
      const next = new Set(prev);
      if (next.has(profileId)) {
        next.delete(profileId);
      } else {
        next.add(profileId);
      }
      return next;
    });
  };

  const selectCampaignActions = (campaignId: string) => {
    const filteredActions = getFilteredActions();
    const campaignActionIds = filteredActions
      .filter(a => a.campaign_id === campaignId)
      .map(a => a.id);
    setSelectedActionIds(prev => {
      const next = new Set(prev);
      campaignActionIds.forEach(id => next.add(id));
      return next;
    });
  };

  const deselectCampaignActions = (campaignId: string) => {
    const filteredActions = getFilteredActions();
    const campaignActionIds = new Set(
      filteredActions.filter(a => a.campaign_id === campaignId).map(a => a.id)
    );
    setSelectedActionIds(prev => {
      const next = new Set(prev);
      campaignActionIds.forEach(id => next.delete(id));
      return next;
    });
  };

  const isCampaignFullySelected = (campaignId: string) => {
    const filteredActions = getFilteredActions();
    const campaignActions = filteredActions.filter(a => a.campaign_id === campaignId);
    return campaignActions.length > 0 && campaignActions.every(a => selectedActionIds.has(a.id));
  };

  const selectAccountActions = (accountId: number) => {
    const filteredActions = getFilteredActions();
    const accountActionIds = filteredActions
      .filter(a => a.account_id === accountId)
      .map(a => a.id);
    setSelectedActionIds(prev => {
      const next = new Set(prev);
      accountActionIds.forEach(id => next.add(id));
      return next;
    });
  };

  const deselectAccountActions = (accountId: number) => {
    const filteredActions = getFilteredActions();
    const accountActionIds = new Set(
      filteredActions.filter(a => a.account_id === accountId).map(a => a.id)
    );
    setSelectedActionIds(prev => {
      const next = new Set(prev);
      accountActionIds.forEach(id => next.delete(id));
      return next;
    });
  };

  const isAccountFullySelected = (accountId: number) => {
    const filteredActions = getFilteredActions();
    const accountActions = filteredActions.filter(a => a.account_id === accountId);
    return accountActions.length > 0 && accountActions.every(a => selectedActionIds.has(a.id));
  };

  const selectProfileActions = (profileId: string) => {
    const filteredActions = getFilteredActions();
    const profileActionIds = filteredActions
      .filter(a => a.profile_id === profileId)
      .map(a => a.id);
    setSelectedActionIds(prev => {
      const next = new Set(prev);
      profileActionIds.forEach(id => next.add(id));
      return next;
    });
  };

  const deselectProfileActions = (profileId: string) => {
    const filteredActions = getFilteredActions();
    const profileActionIds = new Set(
      filteredActions.filter(a => a.profile_id === profileId).map(a => a.id)
    );
    setSelectedActionIds(prev => {
      const next = new Set(prev);
      profileActionIds.forEach(id => next.delete(id));
      return next;
    });
  };

  const isProfileFullySelected = (profileId: string) => {
    const filteredActions = getFilteredActions();
    const profileActions = filteredActions.filter(a => a.profile_id === profileId);
    return profileActions.length > 0 && profileActions.every(a => selectedActionIds.has(a.id));
  };

  const isAllExpanded = () => {
    const hierarchy = groupActionsHierarchically(getFilteredActions());
    if (hierarchy.length === 0) return false;
    for (const account of hierarchy) {
      if (!expandedActionAccounts.has(String(account.accountId))) return false;
      for (const profile of account.profiles) {
        if (!expandedActionProfiles.has(profile.profileId)) return false;
        for (const campaign of profile.campaigns) {
          if (!expandedCampaigns.has(campaign.campaignId)) return false;
        }
      }
    }
    return true;
  };

  const toggleExpandAll = () => {
    const hierarchy = groupActionsHierarchically(getFilteredActions());
    if (isAllExpanded()) {
      setExpandedActionAccounts(new Set());
      setExpandedActionProfiles(new Set());
      setExpandedCampaigns(new Set());
    } else {
      const allAccounts = new Set<string>();
      const allProfiles = new Set<string>();
      const allCampaigns = new Set<string>();
      for (const account of hierarchy) {
        allAccounts.add(String(account.accountId));
        for (const profile of account.profiles) {
          allProfiles.add(profile.profileId);
          for (const campaign of profile.campaigns) {
            allCampaigns.add(campaign.campaignId);
          }
        }
      }
      setExpandedActionAccounts(allAccounts);
      setExpandedActionProfiles(allProfiles);
      setExpandedCampaigns(allCampaigns);
    }
  };

  const deleteSelectedActions = async () => {
    if (selectedActionIds.size === 0) {
      alert('Seleziona almeno un\'azione da eliminare');
      return;
    }
    
    if (!confirm(`Eliminare ${selectedActionIds.size} azioni selezionate?`)) {
      return;
    }
    
    try {
      setDeleting(true);
      await api.delete('/flash-agent/planned-actions', {
        data: { action_ids: Array.from(selectedActionIds) }
      });
      setSelectedActionIds(new Set());
      loadPlannedActions();
    } catch (err: any) {
      console.error('Error deleting actions:', err);
      alert('Errore durante l\'eliminazione: ' + (err.response?.data?.detail || err.message));
    } finally {
      setDeleting(false);
    }
  };

  const loadPlannedActions = async (profileId?: string) => {
    try {
      setLoadingActions(true);
      const params = profileId ? { profile_id: profileId } : {};
      const response = await api.get('/flash-agent/planned-actions', { params });
      setPlannedActions(response.data);
      setSelectedActionIds(new Set());
    } catch (err: any) {
      console.error('Error loading planned actions:', err);
    } finally {
      setLoadingActions(false);
    }
  };

  const loadExecutedActions = async () => {
    try {
      const response = await api.get('/flash-agent/executed-actions');
      setExecutedActions(response.data);
    } catch (err: any) {
      console.error('Error loading executed actions:', err);
    }
  };

  const toggleActionSelection = (actionId: number) => {
    setSelectedActionIds(prev => {
      const next = new Set(prev);
      if (next.has(actionId)) {
        next.delete(actionId);
      } else {
        next.add(actionId);
      }
      return next;
    });
  };

  const selectAllActions = () => {
    const filteredActions = getFilteredActions();
    const allIds = filteredActions.map(a => a.id);
    setSelectedActionIds(new Set(allIds));
  };

  const deselectAllActions = () => {
    setSelectedActionIds(new Set());
  };

  const executeSelectedActions = async () => {
    if (selectedActionIds.size === 0) {
      alert('Seleziona almeno un\'azione da eseguire');
      return;
    }
    
    const selectedActions = plannedActions.filter(a => selectedActionIds.has(a.id));
    if (selectedActions.length === 0) return;
    
    const uniqueProfiles = new Set(selectedActions.map(a => a.profile_id));
    const confirmMsg = uniqueProfiles.size > 1 
      ? `Eseguire ${selectedActions.length} azioni su ${uniqueProfiles.size} profili diversi?`
      : `Eseguire ${selectedActions.length} azioni?`;
    
    if (!confirm(confirmMsg)) return;
    
    try {
      setExecuting(true);
      setLastExecutionResult(null);
      const response = await api.post('/flash-agent/execute-actions', {
        action_ids: Array.from(selectedActionIds)
      });
      
      setLastExecutionResult(response.data);
      setShowDebug(true);
      
      if (response.data.executed_count > 0) {
        const profilesInfo = response.data.profiles_processed > 1 
          ? ` su ${response.data.profiles_processed} profili` 
          : '';
        alert(`Eseguito: ${response.data.executed_count} bid modificati${profilesInfo}${response.data.failed_count > 0 ? `, ${response.data.failed_count} falliti` : ''}`);
        loadPlannedActions();
        loadExecutedActions();
        setShowExecutedHistory(true);
      } else if (response.data.failed_count > 0) {
        alert(`Esecuzione fallita: ${response.data.failed_count} bid non modificati. Vedi sezione Debug per dettagli.`);
        loadPlannedActions();
      }
    } catch (err: any) {
      console.error('Error executing actions:', err);
      setLastExecutionResult({ error: err.response?.data?.detail || err.message });
      setShowDebug(true);
      alert('Errore durante l\'esecuzione: ' + (err.response?.data?.detail || err.message));
    } finally {
      setExecuting(false);
    }
  };

  const runAnalysis = async () => {
    if (!selectedProfile) return;
    
    try {
      setAnalyzing(true);
      setError(null);
      await api.post('/flash-agent/analyze-reports', {
        profile_id: selectedProfile.profileId,
        account_id: selectedProfile.accountId
      });
      await loadPlannedActions(selectedProfile.profileId);
      setShowActions(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore durante l\'analisi');
    } finally {
      setAnalyzing(false);
    }
  };

  const runAnalysisForAll = async () => {
    try {
      setAnalyzingAll(true);
      setError(null);
      const response = await api.post('/flash-agent/analyze-all');
      await loadPlannedActions();
      await loadProfilesWithoutReports();
      setShowActions(true);
      alert(`Analisi completata: ${response.data.total_actions} azioni create da ${response.data.profiles_analyzed} profili`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore durante l\'analisi globale');
    } finally {
      setAnalyzingAll(false);
    }
  };

  const generateReportsForAll = async () => {
    if (!confirm('Cancellare tutti i report esistenti e generare nuovi report 14 e 30 giorni per US, UK e IT? Questa operazione potrebbe richiedere alcuni minuti.')) {
      return;
    }
    
    try {
      setGeneratingAllReports(true);
      setError(null);
      
      await api.delete('/flash-agent/reports');
      
      const response = await api.post('/flash-agent/reports/generate-all');
      await loadAllReports();
      await loadProfilesWithoutReports();
      alert(`Report generati: ${response.data.total_reports_created} report creati per ${response.data.total_profiles} profili (US, UK, IT)`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore durante la generazione dei report');
    } finally {
      setGeneratingAllReports(false);
    }
  };

  const loadProfilesWithoutReports = async () => {
    try {
      const response = await api.get('/flash-agent/profiles-without-reports');
      setProfilesWithoutReports(response.data);
    } catch (err: any) {
      console.error('Error loading profiles without reports:', err);
    }
  };

  const deleteAllReports = async () => {
    if (!confirm('Cancellare TUTTI i report? Questa azione non può essere annullata.')) {
      return;
    }
    
    try {
      setDeletingReports(true);
      const response = await api.delete('/flash-agent/reports');
      await loadAllReports();
      setSelectedReportIds(new Set());
      alert(`${response.data.deleted_count} report cancellati`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore durante la cancellazione');
    } finally {
      setDeletingReports(false);
    }
  };

  const deleteSelectedReports = async () => {
    if (selectedReportIds.size === 0) {
      alert('Seleziona almeno un report da cancellare');
      return;
    }
    
    if (!confirm(`Cancellare ${selectedReportIds.size} report selezionati?`)) {
      return;
    }
    
    try {
      setDeletingReports(true);
      const response = await api.post('/flash-agent/reports/delete-selected', {
        report_ids: Array.from(selectedReportIds)
      });
      await loadAllReports();
      setSelectedReportIds(new Set());
      alert(`${response.data.deleted_count} report cancellati`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore durante la cancellazione');
    } finally {
      setDeletingReports(false);
    }
  };

  const toggleReportSelection = (reportId: number) => {
    const newSet = new Set(selectedReportIds);
    if (newSet.has(reportId)) {
      newSet.delete(reportId);
    } else {
      newSet.add(reportId);
    }
    setSelectedReportIds(newSet);
  };

  const selectAllReports = () => {
    if (selectedReportIds.size === reports.length) {
      setSelectedReportIds(new Set());
    } else {
      setSelectedReportIds(new Set(reports.map(r => r.id)));
    }
  };

  const loadAutopilotStatus = async () => {
    try {
      setLoadingAutopilot(true);
      const response = await api.get('/flash-agent/autopilot/status');
      const statusMap: {[key: string]: {enabled: boolean; last_run: string | null; next_run: string | null; mode?: string; is_running?: boolean}} = {};
      for (const item of response.data) {
        statusMap[item.profile_id] = {
          enabled: item.enabled,
          last_run: item.last_run,
          next_run: item.next_run,
          mode: item.mode || '3d',
          is_running: item.is_running || false
        };
      }
      setAutopilotStatus(statusMap);
    } catch (err: any) {
      console.error('Error loading autopilot status:', err);
    } finally {
      setLoadingAutopilot(false);
    }
  };

  const toggleAutopilot = async (profileId: string, enable: boolean, accountId?: number) => {
    try {
      setTogglingAutopilot(profileId || `account_${accountId}`);
      await api.post('/flash-agent/autopilot/toggle', {
        profile_id: profileId || undefined,
        account_id: accountId || undefined,
        enabled: enable,
        mode: autopilotMode
      });
      await loadAutopilotStatus();
    } catch (err: any) {
      console.error('Error toggling autopilot:', err);
      alert('Errore durante l\'attivazione/disattivazione autopilot: ' + (err.response?.data?.detail || err.message));
    } finally {
      setTogglingAutopilot(null);
    }
  };

  const toggleAccountAutopilot = async (accountId: number, enable: boolean) => {
    try {
      setTogglingAutopilot(`account_${accountId}`);
      await api.post('/flash-agent/autopilot/toggle', {
        account_id: accountId,
        enabled: enable,
        mode: autopilotMode
      });
      await loadAutopilotStatus();
    } catch (err: any) {
      console.error('Error toggling account autopilot:', err);
      alert('Errore durante l\'attivazione/disattivazione autopilot account: ' + (err.response?.data?.detail || err.message));
    } finally {
      setTogglingAutopilot(null);
    }
  };

  const runAutopilot = async (profileId?: string) => {
    try {
      setRunningAutopilot(true);
      const params = profileId ? `?profile_id=${profileId}` : '';
      const response = await api.post(`/flash-agent/autopilot/run${params}`);
      await loadPlannedActions();
      await loadAutopilotStatus();
      
      if (response.data.success) {
        const totalActions = response.data.results?.reduce((sum: number, r: any) => sum + (r.actions_planned || 0), 0) || 0;
        alert(`Autopilot completato: ${totalActions} azioni pianificate per ${response.data.profiles_processed} profili`);
      } else {
        alert(response.data.message || 'Nessun profilo con autopilot attivo');
      }
    } catch (err: any) {
      console.error('Error running autopilot:', err);
      alert('Errore durante l\'esecuzione autopilot: ' + (err.response?.data?.detail || err.message));
    } finally {
      setRunningAutopilot(false);
    }
  };

  useEffect(() => {
    loadProfiles();
    loadAllReports();
    loadPlannedActions();
    loadExecutedActions();
    loadProfilesWithoutReports();
    loadAutopilotStatus();
  }, []);

  const loadProfiles = async () => {
    try {
      setLoadingProfiles(true);
      setError(null);
      const response = await api.get('/flash-agent/profiles');
      setProfiles(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nel caricamento dei profili');
    } finally {
      setLoadingProfiles(false);
    }
  };

  const loadCampaigns = async (profile: Profile) => {
    try {
      setLoadingCampaigns(true);
      setError(null);
      setSelectedProfile(profile);
      setCampaigns([]);
      setShowCampaigns(false);
      
      const response = await api.get('/flash-agent/campaigns', {
        params: {
          account_id: profile.accountId,
          profile_id: profile.profileId
        }
      });
      setCampaigns(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nel caricamento delle campagne');
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const loadAllReports = async () => {
    try {
      setLoadingReports(true);
      const response = await api.get('/flash-agent/reports');
      setReports(response.data);
    } catch (err: any) {
      console.error('Error loading reports:', err);
    } finally {
      setLoadingReports(false);
    }
  };

  const generateReport = async (reportType: '14D' | '30D') => {
    if (!selectedProfile) return;
    
    try {
      setGeneratingReport(reportType);
      setError(null);
      
      await api.post('/flash-agent/reports/generate', {
        account_id: selectedProfile.accountId,
        profile_id: selectedProfile.profileId,
        report_type: reportType
      });
      
      await loadAllReports();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nella generazione del report');
    } finally {
      setGeneratingReport(null);
    }
  };

  const generateBothReports = async () => {
    if (!selectedProfile) return;
    
    try {
      setGeneratingReport('BOTH');
      setError(null);
      
      await Promise.all([
        api.post('/flash-agent/reports/generate', {
          account_id: selectedProfile.accountId,
          profile_id: selectedProfile.profileId,
          report_type: '14D'
        }),
        api.post('/flash-agent/reports/generate', {
          account_id: selectedProfile.accountId,
          profile_id: selectedProfile.profileId,
          report_type: '30D'
        })
      ]);
      
      await loadAllReports();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nella generazione dei report');
    } finally {
      setGeneratingReport(null);
    }
  };

  const viewReportContent = async (reportId: string) => {
    try {
      setLoadingContent(true);
      setShowReportModal(true);
      
      const response = await api.get(`/flash-agent/reports/${reportId}/content`);
      setReportContent(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nel caricamento del report');
      setShowReportModal(false);
    } finally {
      setLoadingContent(false);
    }
  };

  const downloadReport = async (reportId: string, reportType: string) => {
    try {
      const response = await api.get(`/flash-agent/reports/${reportId}/content`);
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${reportType}_${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Errore nel download del report');
    }
  };

  const getStateColor = (state: string) => {
    switch (state.toLowerCase()) {
      case 'enabled':
        return 'bg-green-100 text-green-800';
      case 'paused':
        return 'bg-yellow-100 text-yellow-800';
      case 'archived':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getReportStatusColor = (status: string) => {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
        return 'bg-green-100 text-green-800';
      case 'PENDING':
        return 'bg-yellow-100 text-yellow-800';
      case 'FAILED':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const toggleAccount = (accountKey: string) => {
    setExpandedAccounts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(accountKey)) {
        newSet.delete(accountKey);
      } else {
        newSet.add(accountKey);
      }
      return newSet;
    });
  };

  const filteredProfiles = profiles.filter(p => ALLOWED_COUNTRIES.includes(p.countryCode));

  const groupedProfiles = filteredProfiles.reduce((acc, profile) => {
    const key = `${profile.accountId}-${profile.accountName}`;
    if (!acc[key]) {
      acc[key] = {
        accountId: profile.accountId,
        accountName: profile.accountName,
        profiles: []
      };
    }
    acc[key].profiles.push(profile);
    return acc;
  }, {} as Record<string, { accountId: number; accountName: string; profiles: Profile[] }>);

  const groupedByAccount = Object.values(groupedProfiles);

  const getProfileLabel = (profileId: string) => {
    const profile = profiles.find(p => p.profileId === profileId);
    if (!profile) return profileId.substring(0, 8) + '...';
    return `${getCountryFlag(profile.countryCode)} ${profile.countryCode} - ${profile.accountName}`;
  };

  const groupedReports = reports.reduce((acc, report) => {
    if (!acc[report.profile_id]) {
      acc[report.profile_id] = [];
    }
    acc[report.profile_id].push(report);
    return acc;
  }, {} as Record<string, Report[]>);

  const stateOrder = ['enabled', 'paused', 'archived'];
  
  const filteredCampaigns = campaigns
    .filter(c => stateFilter === 'all' || c.state.toLowerCase() === stateFilter)
    .sort((a, b) => {
      const aIndex = stateOrder.indexOf(a.state.toLowerCase());
      const bIndex = stateOrder.indexOf(b.state.toLowerCase());
      return sortOrder === 'asc' ? aIndex - bIndex : bIndex - aIndex;
    });

  return (
    <Layout>
      <div className="p-8">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 bg-gradient-to-br from-cyan-500 to-red-600 rounded-xl flex items-center justify-center shadow-lg">
              <Zap size={24} className="text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-slate-800">Autopilot</h1>
              <p className="text-gray-500">Ottimizzazione automatica delle campagne</p>
            </div>
          </div>
        </div>

        {/* Autopilot Panel */}
        <div className="mb-6 bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
          <button
            onClick={() => setShowAutopilotPanel(!showAutopilotPanel)}
            className="w-full p-4 bg-gradient-to-r from-purple-50 to-indigo-50 flex items-center justify-between hover:from-purple-100 hover:to-indigo-100 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-lg flex items-center justify-center">
                <Zap size={20} className="text-white" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-slate-800">Autopilot Mode</h3>
                <p className="text-sm text-gray-500">
                  {Object.values(autopilotStatus).filter(s => s.enabled).length} profili attivi
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  runAutopilot();
                }}
                disabled={runningAutopilot || Object.values(autopilotStatus).filter(s => s.enabled).length === 0}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
              >
                {runningAutopilot ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                Esegui Autopilot
              </button>
              {showAutopilotPanel ? (
                <ChevronDown size={20} className="text-slate-400" />
              ) : (
                <ChevronRight size={20} className="text-slate-400" />
              )}
            </div>
          </button>
          
          {showAutopilotPanel && (
            <div className="p-4 border-t border-slate-100">
              <div className="mb-4 p-3 bg-cyan-50 rounded-lg text-sm text-[#00A8CC]">
                L'autopilot genera automaticamente report, analizza i dati ACOS e applica le modifiche ai bid. Seleziona la frequenza di esecuzione.
              </div>
              
              <div className="mb-4 flex items-center gap-4">
                <label className="text-sm font-medium text-gray-600">Modalita:</label>
                <select
                  value={autopilotMode}
                  onChange={(e) => setAutopilotMode(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
                >
                  <option value="test">TEST (ogni 2 ore)</option>
                  <option value="3d">Standard (ogni 3 giorni)</option>
                  <option value="5d">Conservativo (ogni 5 giorni)</option>
                </select>
              </div>
              
              {loadingAutopilot ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 size={24} className="animate-spin text-purple-500" />
                </div>
              ) : (
                <div className="space-y-4">
                  {groupedByAccount.map(account => {
                    const accountProfiles = account.profiles || [];
                    const enabledCount = accountProfiles.filter(p => autopilotStatus[p.profileId]?.enabled).length;
                    const allEnabled = enabledCount === accountProfiles.length && accountProfiles.length > 0;
                    const someEnabled = enabledCount > 0 && enabledCount < accountProfiles.length;
                    const isTogglingAccount = togglingAutopilot === `account_${account.accountId}`;
                    
                    return (
                      <div key={account.accountId} className="border border-gray-200 rounded-lg overflow-hidden">
                        <div className="p-3 bg-gray-100 flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-800">{account.accountName}</span>
                            <span className="text-xs bg-slate-200 px-2 py-0.5 rounded-full text-gray-600">
                              {enabledCount}/{accountProfiles.length} attivi
                            </span>
                          </div>
                          <button
                            onClick={() => toggleAccountAutopilot(account.accountId, !allEnabled)}
                            disabled={isTogglingAccount}
                            className={`relative w-12 h-6 rounded-full transition-colors ${
                              allEnabled ? 'bg-purple-600' : someEnabled ? 'bg-purple-400' : 'bg-slate-300'
                            } ${isTogglingAccount ? 'opacity-50' : ''}`}
                          >
                            <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                              allEnabled || someEnabled ? 'left-7' : 'left-1'
                            }`} />
                          </button>
                        </div>
                        
                        <div className="divide-y divide-slate-100">
                          {accountProfiles.map(profile => {
                            const status = autopilotStatus[profile.profileId];
                            const isEnabled = status?.enabled || false;
                            const isToggling = togglingAutopilot === profile.profileId;
                            const modeLabel = status?.mode === 'test' ? 'TEST' : status?.mode === '5d' ? '5gg' : '3gg';
                            
                            return (
                              <div 
                                key={profile.profileId}
                                className={`p-3 ${isEnabled ? 'bg-purple-50' : 'bg-white'} flex items-center justify-between`}
                              >
                                <div className="flex items-center gap-3">
                                  <span className="text-xl">{getCountryFlag(profile.countryCode)}</span>
                                  <div>
                                    <div className="font-medium text-slate-800">{profile.countryCode}</div>
                                    <div className="text-xs text-gray-500">{profile.marketplace}</div>
                                  </div>
                                  {isEnabled && (
                                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                                      status?.mode === 'test' ? 'bg-cyan-100 text-cyan-700' : 'bg-purple-100 text-purple-700'
                                    }`}>
                                      {modeLabel}
                                    </span>
                                  )}
                                  {status?.is_running && (
                                    <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 flex items-center gap-1">
                                      <Loader2 size={10} className="animate-spin" /> In esecuzione
                                    </span>
                                  )}
                                </div>
                                
                                <div className="flex items-center gap-4">
                                  {status?.last_run && (
                                    <div className="text-xs text-gray-500">
                                      Ultimo: {new Date(status.last_run).toLocaleDateString('it-IT', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'})}
                                    </div>
                                  )}
                                  {status?.next_run && isEnabled && (
                                    <div className="text-xs text-purple-600 font-medium">
                                      Prossimo: {new Date(status.next_run).toLocaleDateString('it-IT', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'})}
                                    </div>
                                  )}
                                  <button
                                    onClick={() => toggleAutopilot(profile.profileId, !isEnabled)}
                                    disabled={isToggling}
                                    className={`relative w-12 h-6 rounded-full transition-colors ${
                                      isEnabled ? 'bg-purple-600' : 'bg-slate-300'
                                    } ${isToggling ? 'opacity-50' : ''}`}
                                  >
                                    <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                                      isEnabled ? 'left-7' : 'left-1'
                                    }`} />
                                  </button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                  
                  {groupedByAccount.length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      Nessun account disponibile
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3 text-red-700">
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="p-4 border-b border-slate-100 bg-gray-50">
                <h2 className="font-semibold text-slate-700">Profili per Account</h2>
              </div>
              
              {loadingProfiles ? (
                <div className="p-8 flex items-center justify-center">
                  <Loader2 size={32} className="animate-spin text-[#00D4FF]" />
                </div>
              ) : filteredProfiles.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  Nessun profilo trovato
                </div>
              ) : (
                <div className="max-h-[600px] overflow-y-auto">
                  {Object.entries(groupedProfiles).map(([key, group]) => (
                    <div key={key} className="border-b border-slate-100 last:border-b-0">
                      <button
                        onClick={() => toggleAccount(key)}
                        className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                      >
                        <span className="font-medium text-slate-700">{group.accountName}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs bg-slate-200 px-2 py-0.5 rounded-full text-gray-600">
                            {group.profiles.length}
                          </span>
                          {expandedAccounts.has(key) ? (
                            <ChevronDown size={18} className="text-slate-400" />
                          ) : (
                            <ChevronRight size={18} className="text-slate-400" />
                          )}
                        </div>
                      </button>
                      
                      {expandedAccounts.has(key) && (
                        <div className="px-4 pb-4 space-y-2">
                          {group.profiles.map((profile) => (
                            <button
                              key={profile.profileId}
                              onClick={() => loadCampaigns(profile)}
                              className={`w-full text-left p-3 rounded-xl border transition-all ${
                                selectedProfile?.profileId === profile.profileId
                                  ? 'bg-white border-[#00D4FF] ring-2 ring-blue-200'
                                  : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                              }`}
                            >
                              <span className="font-medium text-gray-600">
                                {profile.countryCode}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
              <button
                onClick={() => setShowCampaigns(!showCampaigns)}
                disabled={!selectedProfile || loadingCampaigns}
                className="w-full p-4 border-b border-slate-100 bg-gray-50 flex items-center justify-between hover:bg-gray-100 transition-colors disabled:hover:bg-gray-50"
              >
                <h2 className="font-semibold text-slate-700 flex items-center gap-2">
                  <Target size={18} className="text-cyan-500" />
                  Campagne
                  {selectedProfile && (
                    <span className="ml-2 text-sm font-normal text-gray-500">
                      ({selectedProfile.countryCode} - {selectedProfile.accountName})
                    </span>
                  )}
                  {campaigns.length > 0 && (
                    <span className="text-xs bg-cyan-100 px-2 py-0.5 rounded-full text-cyan-600">
                      {campaigns.length}
                    </span>
                  )}
                </h2>
                {selectedProfile && !loadingCampaigns && campaigns.length > 0 && (
                  showCampaigns ? (
                    <ChevronDown size={18} className="text-slate-400" />
                  ) : (
                    <ChevronRight size={18} className="text-slate-400" />
                  )
                )}
              </button>

              {!selectedProfile ? (
                <div className="p-12 text-center text-gray-500">
                  <Target size={48} className="mx-auto mb-4 text-slate-300" />
                  <p>Seleziona un profilo per visualizzare le campagne</p>
                </div>
              ) : loadingCampaigns ? (
                <div className="p-12 flex flex-col items-center justify-center">
                  <Loader2 size={40} className="animate-spin text-cyan-500 mb-4" />
                  <p className="text-gray-500">Caricamento campagne e prodotti...</p>
                </div>
              ) : campaigns.length === 0 ? (
                <div className="p-12 text-center text-gray-500">
                  <Target size={48} className="mx-auto mb-4 text-slate-300" />
                  <p>Nessuna campagna trovata per questo profilo</p>
                </div>
              ) : showCampaigns ? (
                <div>
                  <div className="p-4 border-b border-slate-100 flex items-center gap-4 flex-wrap">
                    <div className="flex items-center gap-2">
                      <label className="text-sm text-gray-600">Stato:</label>
                      <select
                        value={stateFilter}
                        onChange={(e) => setStateFilter(e.target.value)}
                        className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-200"
                      >
                        <option value="all">Tutti</option>
                        <option value="enabled">Attive</option>
                        <option value="paused">In pausa</option>
                        <option value="archived">Archiviate</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="text-sm text-gray-600">Ordina:</label>
                      <button
                        onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                        className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white hover:bg-gray-50 flex items-center gap-1"
                      >
                        {sortOrder === 'asc' ? 'Attive prima' : 'Archiviate prima'}
                        <ChevronDown size={14} className={`transition-transform ${sortOrder === 'desc' ? 'rotate-180' : ''}`} />
                      </button>
                    </div>
                    <span className="text-sm text-gray-500 ml-auto">
                      {filteredCampaigns.length} di {campaigns.length} campagne
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                          <th className="text-left p-4 font-semibold text-gray-600">Nome Campagna</th>
                          <th className="text-left p-4 font-semibold text-gray-600">ID</th>
                          <th className="text-left p-4 font-semibold text-gray-600">ASIN</th>
                          <th className="text-left p-4 font-semibold text-gray-600">Stato</th>
                          <th className="text-right p-4 font-semibold text-gray-600">Budget</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {filteredCampaigns.map((campaign) => (
                          <tr key={campaign.campaignId} className="hover:bg-gray-50">
                            <td className="p-4">
                              <span className="font-medium text-slate-800">
                                {campaign.campaignName}
                              </span>
                            </td>
                            <td className="p-4">
                              <code className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-600">
                                {campaign.campaignId}
                              </code>
                            </td>
                            <td className="p-4">
                              {campaign.asin ? (
                                <div className="flex items-center gap-2">
                                  <Package size={16} className="text-cyan-500" />
                                  <a
                                    href={`https://www.amazon.it/dp/${campaign.asin}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[#00D4FF] hover:underline font-mono text-sm"
                                  >
                                    {campaign.asin}
                                  </a>
                                </div>
                              ) : (
                                <span className="text-slate-400 text-sm">-</span>
                              )}
                            </td>
                            <td className="p-4">
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStateColor(campaign.state)}`}>
                                {campaign.state}
                              </span>
                            </td>
                            <td className="p-4 text-right">
                              {campaign.budget !== null ? (
                                <span className="font-medium text-slate-700">
                                  €{campaign.budget.toFixed(2)}
                                </span>
                              ) : (
                                <span className="text-slate-400">-</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="p-6 text-center text-gray-500">
                  <p className="text-sm">Clicca per espandere e visualizzare le {campaigns.length} campagne</p>
                </div>
              )}
            </div>

            {selectedProfile && (
              <div className="flex gap-2 justify-end flex-wrap">
                <button
                  onClick={() => generateReport('14D')}
                  disabled={generatingReport !== null}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {generatingReport === '14D' ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Download size={16} />
                  )}
                  Genera Report 14 giorni
                </button>
                <button
                  onClick={() => generateReport('30D')}
                  disabled={generatingReport !== null}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {generatingReport === '30D' ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Download size={16} />
                  )}
                  Genera Report 30 giorni
                </button>
                <button
                  onClick={generateBothReports}
                  disabled={generatingReport !== null}
                  className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg text-sm font-medium hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {generatingReport === 'BOTH' ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Download size={16} />
                  )}
                  Genera Entrambi
                </button>
                <button
                  onClick={runAnalysis}
                  disabled={analyzing}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {analyzing ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Zap size={16} />
                  )}
                  Analizza ACOS
                </button>
              </div>
            )}

            <div className="flex items-center gap-4 justify-end flex-wrap">
              <button
                onClick={generateReportsForAll}
                disabled={generatingAllReports}
                className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg text-sm font-medium hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {generatingAllReports ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Download size={16} />
                )}
                Genera Report per Tutti
              </button>
              <button
                onClick={runAnalysisForAll}
                disabled={analyzingAll}
                className="px-4 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg text-sm font-medium hover:from-green-700 hover:to-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {analyzingAll ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Zap size={16} />
                )}
                Analizza ACOS per Tutti i Profili
              </button>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
              <button
                onClick={() => setShowActions(!showActions)}
                className="w-full p-4 border-b border-slate-100 bg-gray-50 flex items-center justify-between hover:bg-gray-100 transition-colors"
              >
                <h2 className="font-semibold text-slate-700 flex items-center gap-2">
                  <Zap size={18} className="text-green-500" />
                  Azioni Pianificate
                  {plannedActions.length > 0 && (
                    <span className="text-xs bg-green-100 px-2 py-0.5 rounded-full text-green-600">
                      {plannedActions.length}
                    </span>
                  )}
                  {plannedActions.filter(a => a.source === 'autopilot').length > 0 && (
                    <span className="text-xs bg-purple-100 px-2 py-0.5 rounded-full text-purple-600 flex items-center gap-1">
                      <Bot size={10} />
                      {plannedActions.filter(a => a.source === 'autopilot').length}
                    </span>
                  )}
                </h2>
                {plannedActions.length > 0 && (
                  showActions ? (
                    <ChevronDown size={18} className="text-slate-400" />
                  ) : (
                    <ChevronRight size={18} className="text-slate-400" />
                  )
                )}
              </button>

              {loadingActions ? (
                <div className="p-8 flex items-center justify-center">
                  <Loader2 size={32} className="animate-spin text-green-500" />
                </div>
              ) : plannedActions.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <Zap size={48} className="mx-auto mb-4 text-slate-300" />
                  <p>Nessuna azione pianificata</p>
                  <p className="text-sm mt-2">Seleziona un profilo e clicca "Analizza ACOS"</p>
                </div>
              ) : showActions && (
                <div>
                  <div className="p-4 bg-gray-50 border-b border-gray-200 space-y-3">
                    <div className="flex flex-wrap gap-3">
                      <select
                        value={actionFilterAccount}
                        onChange={(e) => setActionFilterAccount(e.target.value)}
                        className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg bg-white"
                      >
                        <option value="">Tutti gli Account</option>
                        {getUniqueAccounts().map(acc => (
                          <option key={acc.id} value={String(acc.id)}>{acc.name}</option>
                        ))}
                      </select>
                      <select
                        value={actionFilterCountry}
                        onChange={(e) => setActionFilterCountry(e.target.value)}
                        className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg bg-white"
                      >
                        <option value="">Tutti i Marketplace</option>
                        {getUniqueCountries().map(cc => (
                          <option key={cc} value={cc}>{getCountryFlag(cc)} {cc}</option>
                        ))}
                      </select>
                      <select
                        value={actionFilterAsin}
                        onChange={(e) => setActionFilterAsin(e.target.value)}
                        className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg bg-white"
                      >
                        <option value="">Tutti i Prodotti</option>
                        {getUniqueAsins().map(asin => (
                          <option key={asin} value={asin}>{asin}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={toggleExpandAll}
                          className="px-3 py-1.5 text-xs bg-indigo-100 hover:bg-indigo-200 rounded-lg text-indigo-700 font-medium flex items-center gap-1"
                        >
                          {isAllExpanded() ? (
                            <>
                              <ChevronRight size={14} />
                              Comprimi Tutto
                            </>
                          ) : (
                            <>
                              <ChevronDown size={14} />
                              Espandi Tutto
                            </>
                          )}
                        </button>
                        <span className="text-slate-300">|</span>
                        <button
                          onClick={selectAllActions}
                          className="px-3 py-1.5 text-xs bg-slate-200 hover:bg-slate-300 rounded-lg text-slate-700 font-medium"
                        >
                          Seleziona Tutti
                        </button>
                        <button
                          onClick={deselectAllActions}
                          className="px-3 py-1.5 text-xs bg-slate-200 hover:bg-slate-300 rounded-lg text-slate-700 font-medium"
                        >
                          Deseleziona
                        </button>
                        <span className="text-sm text-gray-500">
                          {selectedActionIds.size} selezionati
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={deleteSelectedActions}
                          disabled={deleting || selectedActionIds.size === 0}
                          className="px-3 py-2 bg-red-100 text-red-700 rounded-lg text-sm font-medium hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                          {deleting ? (
                            <Loader2 size={16} className="animate-spin" />
                          ) : (
                            <Trash2 size={16} />
                          )}
                          Elimina
                        </button>
                        <button
                          onClick={executeSelectedActions}
                          disabled={executing || selectedActionIds.size === 0}
                          className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                          {executing ? (
                            <Loader2 size={16} className="animate-spin" />
                          ) : (
                            <Play size={16} />
                          )}
                          Esegui
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="divide-y divide-slate-100">
                  {groupActionsHierarchically(getFilteredActions()).map((account) => (
                    <div key={account.accountId} className="border-b border-gray-200">
                      <div className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors bg-gray-100">
                        <div className="flex items-center gap-3">
                          <button onClick={() => toggleAccountExpand(String(account.accountId))} className="p-1">
                            {expandedActionAccounts.has(String(account.accountId)) ? (
                              <ChevronDown size={18} className="text-gray-500" />
                            ) : (
                              <ChevronRight size={18} className="text-gray-500" />
                            )}
                          </button>
                          <input
                            type="checkbox"
                            checked={isAccountFullySelected(account.accountId)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                selectAccountActions(account.accountId);
                              } else {
                                deselectAccountActions(account.accountId);
                              }
                            }}
                            className="w-4 h-4 text-green-600 rounded border-gray-300"
                          />
                          <span className="font-semibold text-slate-800">{account.accountName}</span>
                        </div>
                        <span className="text-xs bg-slate-300 px-2 py-1 rounded-full text-slate-700">
                          {account.profiles.reduce((sum, p) => sum + p.campaigns.reduce((s, c) => s + c.actions.length, 0), 0)} azioni
                        </span>
                      </div>
                      
                      {expandedActionAccounts.has(String(account.accountId)) && (
                        <div className="pl-4">
                          {account.profiles.map((profile) => (
                            <div key={profile.profileId} className="border-l-2 border-gray-200">
                              <div className="w-full p-3 flex items-center justify-between hover:bg-gray-50 transition-colors">
                                <div className="flex items-center gap-3">
                                  <button onClick={() => toggleProfileExpand(profile.profileId)} className="p-1">
                                    {expandedActionProfiles.has(profile.profileId) ? (
                                      <ChevronDown size={16} className="text-slate-400" />
                                    ) : (
                                      <ChevronRight size={16} className="text-slate-400" />
                                    )}
                                  </button>
                                  <input
                                    type="checkbox"
                                    checked={isProfileFullySelected(profile.profileId)}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        selectProfileActions(profile.profileId);
                                      } else {
                                        deselectProfileActions(profile.profileId);
                                      }
                                    }}
                                    className="w-4 h-4 text-green-600 rounded border-gray-300"
                                  />
                                  <span className="text-lg">{getCountryFlag(profile.countryCode)}</span>
                                  <span className="font-medium text-slate-700">{profile.countryCode}</span>
                                  <code className="text-xs text-slate-400 font-mono">{profile.profileId}</code>
                                </div>
                                <span className="text-xs bg-slate-200 px-2 py-1 rounded-full text-gray-600">
                                  {profile.campaigns.reduce((s, c) => s + c.actions.length, 0)} azioni
                                </span>
                              </div>
                              
                              {expandedActionProfiles.has(profile.profileId) && (
                                <div className="pl-4">
                                  {profile.campaigns.map((campaign) => (
                                    <div key={campaign.campaignId} className="border-l-2 border-slate-100">
                                      <div className="p-3 flex items-center justify-between hover:bg-gray-50">
                                        <div className="flex items-center gap-3">
                                          <button
                                            onClick={() => toggleCampaignExpand(campaign.campaignId)}
                                            className="p-1"
                                          >
                                            {expandedCampaigns.has(campaign.campaignId) ? (
                                              <ChevronDown size={14} className="text-slate-400" />
                                            ) : (
                                              <ChevronRight size={14} className="text-slate-400" />
                                            )}
                                          </button>
                                          <input
                                            type="checkbox"
                                            checked={isCampaignFullySelected(campaign.campaignId)}
                                            onChange={(e) => {
                                              if (e.target.checked) {
                                                selectCampaignActions(campaign.campaignId);
                                              } else {
                                                deselectCampaignActions(campaign.campaignId);
                                              }
                                            }}
                                            className="w-4 h-4 text-green-600 rounded border-gray-300"
                                          />
                                          <div>
                                            <div className="font-medium text-slate-700 text-sm flex items-center gap-2">
                                              <span>{campaign.campaignName}</span>
                                              {campaign.asin && (
                                                <a
                                                  href={`https://www.amazon.it/dp/${campaign.asin}`}
                                                  target="_blank"
                                                  rel="noopener noreferrer"
                                                  className="text-[#00D4FF] hover:underline font-mono text-xs"
                                                >
                                                  {campaign.asin}
                                                </a>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                        <span className="text-xs bg-gray-100 px-2 py-1 rounded-full text-gray-500">
                                          {campaign.actions.length} target
                                        </span>
                                      </div>
                                      
                                      {expandedCampaigns.has(campaign.campaignId) && (
                                        <div className="bg-white ml-8 border-l border-slate-100">
                                          <table className="w-full text-sm">
                                            <thead className="bg-gray-50 border-b border-slate-100">
                                              <tr>
                                                <th className="w-8 p-2"></th>
                                                <th className="text-left p-2 font-medium text-gray-500 text-xs">Target</th>
                                                <th className="text-center p-2 font-medium text-gray-500 text-xs">Bid</th>
                                                <th className="text-center p-2 font-medium text-gray-500 text-xs">ACOS 14D</th>
                                                <th className="text-center p-2 font-medium text-gray-500 text-xs">ACOS 30D</th>
                                                <th className="text-center p-2 font-medium text-gray-500 text-xs">Delta</th>
                                                <th className="text-left p-2 font-medium text-gray-500 text-xs">Tipo</th>
                                              </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-50">
                                              {campaign.actions.map((action) => (
                                                <tr 
                                                  key={action.id} 
                                                  className={`hover:bg-gray-50 cursor-pointer ${selectedActionIds.has(action.id) ? 'bg-green-50' : ''}`}
                                                  onClick={() => toggleActionSelection(action.id)}
                                                >
                                                  <td className="p-2 text-center">
                                                    <input
                                                      type="checkbox"
                                                      checked={selectedActionIds.has(action.id)}
                                                      onChange={() => toggleActionSelection(action.id)}
                                                      onClick={(e) => e.stopPropagation()}
                                                      className="w-3 h-3 text-green-600 rounded border-gray-300"
                                                    />
                                                  </td>
                                                  <td className="p-2">
                                                    <span className="text-slate-700 truncate max-w-[150px] inline-block text-xs">
                                                      {action.target || '-'}
                                                    </span>
                                                  </td>
                                                  <td className="p-2 text-center">
                                                    <span className="text-xs font-mono text-gray-600">
                                                      {action.current_bid != null ? `${action.current_bid.toFixed(2)}${getCurrencySymbol(action.country_code)}` : '-'}
                                                    </span>
                                                  </td>
                                                  <td className="p-2 text-center">
                                                    <span className={`text-xs font-mono ${
                                                      action.acos_14d != null 
                                                        ? action.acos_14d < 0.20 ? 'text-green-600' : action.acos_14d > 0.50 ? 'text-red-600' : 'text-gray-600'
                                                        : 'text-slate-400'
                                                    }`}>
                                                      {action.acos_14d != null ? `${(action.acos_14d * 100).toFixed(1)}%` : '-'}
                                                    </span>
                                                  </td>
                                                  <td className="p-2 text-center">
                                                    <span className={`text-xs font-mono ${
                                                      action.acos_30d != null 
                                                        ? action.acos_30d < 0.20 ? 'text-green-600' : action.acos_30d > 0.50 ? 'text-red-600' : 'text-gray-600'
                                                        : 'text-slate-400'
                                                    }`}>
                                                      {action.acos_30d != null ? `${(action.acos_30d * 100).toFixed(1)}%` : '-'}
                                                    </span>
                                                  </td>
                                                  <td className="p-2 text-center">
                                                    <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                                                      action.delta_bid > 0 
                                                        ? 'bg-green-100 text-green-700' 
                                                        : 'bg-red-100 text-red-700'
                                                    }`}>
                                                      {action.delta_bid > 0 ? '+' : ''}{action.delta_bid.toFixed(2)}{getCurrencySymbol(action.country_code)}
                                                    </span>
                                                  </td>
                                                  <td className="p-2">
                                                    <div className="flex items-center gap-1">
                                                      {action.source === 'autopilot' && (
                                                        <span title="Autopilot"><Bot size={12} className="text-purple-500" /></span>
                                                      )}
                                                      <span className={`px-1.5 py-0.5 rounded text-xs ${
                                                        action.tipo_azione.includes('INCREMENTO') 
                                                          ? 'bg-green-50 text-green-600' 
                                                          : 'bg-red-50 text-red-600'
                                                      }`}>
                                                        {action.tipo_azione.includes('INCREMENTO') ? '↑' : '↓'} ACOS
                                                      </span>
                                                    </div>
                                                  </td>
                                                </tr>
                                              ))}
                                            </tbody>
                                          </table>
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  </div>
                </div>
              )}
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
              <button
                onClick={() => setShowExecutedHistory(!showExecutedHistory)}
                className="w-full p-4 border-b border-slate-100 bg-gray-50 flex items-center justify-between hover:bg-gray-100 transition-colors"
              >
                <h2 className="font-semibold text-slate-700 flex items-center gap-2">
                  <Check size={18} className="text-[#00D4FF]" />
                  Storico Esecuzioni
                  {executedActions.length > 0 && (
                    <span className="text-xs bg-cyan-50 px-2 py-0.5 rounded-full text-[#00D4FF]">
                      {executedActions.length}
                    </span>
                  )}
                </h2>
                {executedActions.length > 0 && (
                  showExecutedHistory ? (
                    <ChevronDown size={18} className="text-slate-400" />
                  ) : (
                    <ChevronRight size={18} className="text-slate-400" />
                  )
                )}
              </button>

              {showExecutedHistory && executedActions.length > 0 && (
                <div className="divide-y divide-slate-100 max-h-96 overflow-auto">
                  {groupActionsByCampaign(executedActions).map((campaign) => (
                    <div key={campaign.id} className="p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="font-medium text-slate-800">{campaign.name}</span>
                        {campaign.asin && (
                          <>
                            <span className="text-slate-400">-</span>
                            <a
                              href={`https://www.amazon.it/dp/${campaign.asin}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[#00D4FF] hover:underline font-mono text-sm"
                            >
                              {campaign.asin}
                            </a>
                          </>
                        )}
                      </div>
                      <div className="space-y-2">
                        {campaign.actions.map((action) => (
                          <div key={action.id} className="flex items-center justify-between text-sm bg-gray-50 rounded-lg p-2">
                            <span className="text-gray-600 truncate max-w-[200px]">{action.target || '-'}</span>
                            <div className="flex items-center gap-2">
                              <span className={`px-2 py-1 rounded-full text-xs font-bold ${
                                action.delta_bid > 0 
                                  ? 'bg-green-100 text-green-700' 
                                  : 'bg-red-100 text-red-700'
                              }`}>
                                {action.delta_bid > 0 ? '+' : ''}{action.delta_bid.toFixed(2)}{getCurrencySymbol(action.country_code)}
                              </span>
                              <Check size={14} className="text-green-500" />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {showExecutedHistory && executedActions.length === 0 && (
                <div className="p-8 text-center text-gray-500">
                  <Check size={48} className="mx-auto mb-4 text-slate-300" />
                  <p>Nessuna esecuzione ancora</p>
                  <p className="text-sm mt-2">Le azioni eseguite appariranno qui</p>
                </div>
              )}
            </div>

            {lastExecutionResult && (
              <div className="bg-white rounded-2xl shadow-sm border border-red-200 overflow-hidden">
                <button
                  onClick={() => setShowDebug(!showDebug)}
                  className="w-full p-4 border-b border-red-100 bg-red-50 flex items-center justify-between hover:bg-red-100 transition-colors"
                >
                  <h2 className="font-semibold text-red-700 flex items-center gap-2">
                    <Bug size={18} className="text-red-500" />
                    Debug Ultima Esecuzione
                    {lastExecutionResult.failed_count > 0 && (
                      <span className="text-xs bg-red-200 px-2 py-0.5 rounded-full text-red-700">
                        {lastExecutionResult.failed_count} falliti
                      </span>
                    )}
                  </h2>
                  {showDebug ? (
                    <ChevronDown size={18} className="text-red-400" />
                  ) : (
                    <ChevronRight size={18} className="text-red-400" />
                  )}
                </button>

                {showDebug && (
                  <div className="p-4 space-y-4">
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div className="bg-green-50 p-3 rounded-lg">
                        <div className="font-medium text-green-700">Successo</div>
                        <div className="text-2xl font-bold text-green-600">{lastExecutionResult.executed_count || 0}</div>
                      </div>
                      <div className="bg-red-50 p-3 rounded-lg">
                        <div className="font-medium text-red-700">Falliti</div>
                        <div className="text-2xl font-bold text-red-600">{lastExecutionResult.failed_count || 0}</div>
                      </div>
                      <div className="bg-gray-50 p-3 rounded-lg">
                        <div className="font-medium text-slate-700">Totale</div>
                        <div className="text-2xl font-bold text-gray-600">{lastExecutionResult.total_keywords || 0}</div>
                      </div>
                    </div>

                    {lastExecutionResult.error && (
                      <div className="bg-red-100 border border-red-300 rounded-lg p-4">
                        <div className="font-medium text-red-800 mb-2">Errore:</div>
                        <code className="text-sm text-red-700 block whitespace-pre-wrap">{lastExecutionResult.error}</code>
                      </div>
                    )}

                    {lastExecutionResult.details?.results && (
                      <div className="space-y-2">
                        <div className="font-medium text-slate-700">Dettagli Batch:</div>
                        {lastExecutionResult.details.results.map((batch: any, idx: number) => (
                          <div key={idx} className={`p-3 rounded-lg text-sm ${batch.status === 'completed' ? 'bg-green-50' : 'bg-red-50'}`}>
                            <div className="flex justify-between items-center mb-2">
                              <span className="font-medium">Batch {batch.batch}</span>
                              <span className={`px-2 py-1 rounded text-xs ${batch.status === 'completed' ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}`}>
                                {batch.status}
                              </span>
                            </div>
                            {batch.http_status && (
                              <div className="text-red-600 mb-1">HTTP Status: {batch.http_status}</div>
                            )}
                            {batch.error && (
                              <pre className="bg-white p-2 rounded text-xs overflow-x-auto whitespace-pre-wrap text-red-700">{batch.error}</pre>
                            )}
                            {batch.failed_details && batch.failed_details.length > 0 && (
                              <div className="mt-2">
                                <div className="text-red-600 text-xs mb-1">Keywords falliti:</div>
                                {batch.failed_details.map((f: any, i: number) => (
                                  <div key={i} className="text-xs text-red-600">
                                    {f.keywordId}: {f.code} - {f.message}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    <button
                      onClick={() => setLastExecutionResult(null)}
                      className="w-full py-2 text-sm text-gray-600 hover:text-slate-800 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                      Chiudi Debug
                    </button>
                  </div>
                )}
              </div>
            )}

            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="p-4 border-b border-slate-100 bg-gray-50 flex items-center justify-between">
                <h2 className="font-semibold text-slate-700 flex items-center gap-2">
                  <FileText size={18} className="text-purple-500" />
                  Tutti i Report
                  {reports.length > 0 && (
                    <span className="text-xs bg-purple-100 px-2 py-0.5 rounded-full text-purple-600">
                      {reports.length}
                    </span>
                  )}
                </h2>
                <div className="flex items-center gap-2">
                  {selectedReportIds.size > 0 && (
                    <button
                      onClick={deleteSelectedReports}
                      disabled={deletingReports}
                      className="px-3 py-2 bg-red-100 text-red-600 rounded-lg text-sm font-medium hover:bg-red-200 disabled:opacity-50 flex items-center gap-1"
                    >
                      {deletingReports ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      Elimina ({selectedReportIds.size})
                    </button>
                  )}
                  {reports.length > 0 && (
                    <button
                      onClick={deleteAllReports}
                      disabled={deletingReports}
                      className="px-3 py-2 bg-red-500 text-white rounded-lg text-sm font-medium hover:bg-red-600 disabled:opacity-50 flex items-center gap-1"
                    >
                      {deletingReports ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      Elimina Tutti
                    </button>
                  )}
                  <button
                    onClick={loadAllReports}
                    disabled={loadingReports}
                    className="px-3 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-slate-200 disabled:opacity-50"
                  >
                    <RefreshCw size={16} className={loadingReports ? 'animate-spin' : ''} />
                  </button>
                </div>
              </div>

              {loadingReports ? (
                <div className="p-8 flex items-center justify-center">
                  <Loader2 size={32} className="animate-spin text-purple-500" />
                </div>
              ) : reports.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <FileText size={48} className="mx-auto mb-4 text-slate-300" />
                  <p>Nessun report disponibile</p>
                  <p className="text-sm mt-2">Seleziona un profilo e genera un report</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {Object.entries(groupedReports).map(([profileId, profileReports]) => (
                    <div key={profileId} className="p-4">
                      <h3 className="text-sm font-medium text-gray-600 mb-3 flex items-center gap-2">
                        {getProfileLabel(profileId)}
                      </h3>
                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead className="bg-gray-50 border-b border-gray-200">
                            <tr>
                              <th className="w-10 p-3">
                                <input
                                  type="checkbox"
                                  checked={selectedReportIds.size === reports.length && reports.length > 0}
                                  onChange={selectAllReports}
                                  className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                                />
                              </th>
                              <th className="text-left p-3 font-semibold text-gray-600 text-sm">Tipo</th>
                              <th className="text-left p-3 font-semibold text-gray-600 text-sm">Report ID</th>
                              <th className="text-left p-3 font-semibold text-gray-600 text-sm">Periodo</th>
                              <th className="text-left p-3 font-semibold text-gray-600 text-sm">Stato</th>
                              <th className="text-left p-3 font-semibold text-gray-600 text-sm">Creato</th>
                              <th className="text-right p-3 font-semibold text-gray-600 text-sm">Azioni</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {profileReports.map((report) => (
                              <tr key={report.id} className="hover:bg-gray-50">
                                <td className="p-3">
                                  <input
                                    type="checkbox"
                                    checked={selectedReportIds.has(report.id)}
                                    onChange={() => toggleReportSelection(report.id)}
                                    className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                                  />
                                </td>
                                <td className="p-3">
                                  <span className="font-medium text-slate-800 text-sm">
                                    {report.report_type.includes('14D') ? '14 giorni' : '30 giorni'}
                                  </span>
                                </td>
                                <td className="p-3">
                                  <div className="flex items-center gap-2">
                                    <code className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-600 font-mono">
                                      {report.report_id ? `${report.report_id.substring(0, 12)}...` : '-'}
                                    </code>
                                    {report.report_id && (
                                      <button
                                        onClick={() => {
                                          navigator.clipboard.writeText(report.report_id);
                                          setCopiedReportId(report.report_id);
                                          setTimeout(() => setCopiedReportId(null), 2000);
                                        }}
                                        className="p-1 hover:bg-slate-200 rounded text-gray-500 hover:text-slate-700"
                                        title="Copia ID completo"
                                      >
                                        {copiedReportId === report.report_id ? (
                                          <Check size={14} className="text-green-500" />
                                        ) : (
                                          <Copy size={14} />
                                        )}
                                      </button>
                                    )}
                                  </div>
                                </td>
                                <td className="p-3 text-sm text-gray-600">
                                  {report.start_date} → {report.end_date}
                                </td>
                                <td className="p-3">
                                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getReportStatusColor(report.status)}`}>
                                    {report.status}
                                  </span>
                                </td>
                                <td className="p-3 text-sm text-gray-500">
                                  {new Date(report.created_at).toLocaleString('it-IT')}
                                </td>
                                <td className="p-3 text-right">
                                  {report.status === 'COMPLETED' && (
                                    <div className="flex items-center gap-2 justify-end">
                                      <button
                                        onClick={() => viewReportContent(report.report_id)}
                                        className="px-3 py-1.5 bg-green-100 text-green-700 rounded-lg text-sm font-medium hover:bg-green-200 flex items-center gap-1"
                                      >
                                        <Eye size={14} />
                                        Apri
                                      </button>
                                      <button
                                        onClick={() => downloadReport(report.report_id, report.report_type)}
                                        className="px-3 py-1.5 bg-cyan-50 text-[#00A8CC] rounded-lg text-sm font-medium hover:bg-blue-200 flex items-center gap-1"
                                      >
                                        <Download size={14} />
                                        Scarica
                                      </button>
                                    </div>
                                  )}
                                  {report.status === 'PENDING' && (
                                    <span className="text-sm text-yellow-600 flex items-center gap-1 justify-end">
                                      <Loader2 size={14} className="animate-spin" />
                                      In elaborazione...
                                    </span>
                                  )}
                                  {report.status === 'FAILED' && (
                                    <span className="text-sm text-red-600">Errore</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {profilesWithoutReports.length > 0 && (
        <div className="mt-6 bg-white rounded-2xl shadow-sm border border-cyan-200 overflow-hidden">
          <button
            onClick={() => setShowProfilesWithoutReports(!showProfilesWithoutReports)}
            className="w-full p-4 bg-cyan-50 flex items-center justify-between hover:bg-cyan-100 transition-colors"
          >
            <div className="flex items-center gap-3">
              <AlertCircle size={20} className="text-cyan-600" />
              <h3 className="font-semibold text-cyan-800">
                Profili senza Report
                <span className="ml-2 text-xs bg-cyan-200 px-2 py-0.5 rounded-full text-cyan-700">
                  {profilesWithoutReports.length}
                </span>
              </h3>
            </div>
            {showProfilesWithoutReports ? (
              <ChevronDown size={18} className="text-cyan-600" />
            ) : (
              <ChevronRight size={18} className="text-cyan-600" />
            )}
          </button>
          
          {showProfilesWithoutReports && (
            <div className="p-4 border-t border-cyan-100">
              <p className="text-sm text-cyan-700 mb-3">
                I seguenti profili hanno campagne ma nessun report generato. Selezionali e genera i report per includerli nell'analisi ACOS.
              </p>
              <div className="flex flex-wrap gap-2">
                {profilesWithoutReports.map(p => (
                  <span 
                    key={p.profile_id}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-cyan-100 text-cyan-800 rounded-md text-sm"
                  >
                    {getCountryFlag(p.country_code)} {p.account_name} ({p.country_code})
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {showReportModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-800 flex items-center gap-2">
                <FileText size={20} className="text-purple-500" />
                Contenuto Report
              </h3>
              <div className="flex items-center gap-2">
                {reportContent && (
                  <button
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(reportContent, null, 2)], { type: 'application/json' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = `report_${new Date().toISOString().slice(0,10)}.json`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                    className="px-3 py-2 bg-[#00D4FF] text-white rounded-lg text-sm font-medium hover:bg-[#00A8CC] flex items-center gap-2"
                  >
                    <Download size={16} />
                    Scarica JSON
                  </button>
                )}
                <button
                  onClick={() => {
                    setShowReportModal(false);
                    setReportContent(null);
                  }}
                  className="p-2 hover:bg-gray-100 rounded-lg"
                >
                  <X size={20} className="text-gray-500" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {loadingContent ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={40} className="animate-spin text-purple-500" />
                </div>
              ) : reportContent ? (
                <pre className="text-sm bg-slate-900 text-green-400 p-4 rounded-xl overflow-auto font-mono">
                  {JSON.stringify(reportContent, null, 2)}
                </pre>
              ) : (
                <div className="text-center text-gray-500 py-12">
                  Nessun contenuto disponibile
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
