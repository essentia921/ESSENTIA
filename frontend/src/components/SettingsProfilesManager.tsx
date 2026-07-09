import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Check, Loader2, Settings } from 'lucide-react';
import api from '../lib/api';

interface SettingsProfile {
  id: number;
  name: string;
  description: string | null;
  delta_excellent: number;
  delta_good: number;
  delta_above_be: number;
  delta_high: number;
  delta_low_impressions: number;
  delta_no_sales: number;
  low_impressions_threshold: number;
  min_spend_for_decrement: number;
  max_clicks_no_sales: number;
  max_clicks_for_low_impressions: number;
  pause_on_clicks_enabled: boolean;
  is_default: boolean;
  is_system?: boolean;
}

interface Props {
  accountId: number;
  onProfileSelect?: (profileId: number) => void;
  selectedProfileId?: number | null;
  compact?: boolean;
  refreshKey?: number;
  onProfilesChanged?: () => void;
}

export default function SettingsProfilesManager({ accountId, onProfileSelect, selectedProfileId, compact = false, refreshKey, onProfilesChanged }: Props) {
  const [profiles, setProfiles] = useState<SettingsProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingProfile, setEditingProfile] = useState<SettingsProfile | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  
  const defaultProfile: Omit<SettingsProfile, 'id'> = {
    name: '',
    description: '',
    delta_excellent: 0.05,
    delta_good: 0.02,
    delta_above_be: -0.02,
    delta_high: -0.05,
    delta_low_impressions: 0.01,
    delta_no_sales: -0.02,
    low_impressions_threshold: 100,
    min_spend_for_decrement: 1.00,
    max_clicks_no_sales: 10,
    max_clicks_for_low_impressions: 0,
    pause_on_clicks_enabled: true,
    is_default: false
  };

  const [formData, setFormData] = useState(defaultProfile);

  useEffect(() => {
    loadProfiles();
  }, [accountId, refreshKey]);

  const loadProfiles = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/autopilot/settings-profiles/${accountId}`);
      setProfiles(response.data.profiles || []);
    } catch (error) {
      console.error('Failed to load profiles:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!formData.name.trim()) return;
    
    try {
      setSaving(true);
      await api.post(`/autopilot/settings-profiles/${accountId}`, formData);
      await loadProfiles();
      setIsCreating(false);
      setFormData(defaultProfile);
      onProfilesChanged?.();
    } catch (error) {
      console.error('Failed to create profile:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!editingProfile || !formData.name.trim()) return;
    
    try {
      setSaving(true);
      await api.put(`/autopilot/settings-profiles/${accountId}/${editingProfile.id}`, formData);
      await loadProfiles();
      setEditingProfile(null);
      setFormData(defaultProfile);
      onProfilesChanged?.();
    } catch (error) {
      console.error('Failed to update profile:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (profileId: number) => {
    if (!confirm('Sei sicuro di voler eliminare questo profilo?')) return;
    
    try {
      await api.delete(`/autopilot/settings-profiles/${accountId}/${profileId}`);
      await loadProfiles();
      onProfilesChanged?.();
    } catch (error) {
      console.error('Failed to delete profile:', error);
    }
  };

  const startEdit = (profile: SettingsProfile) => {
    setEditingProfile(profile);
    setFormData({
      name: profile.name,
      description: profile.description || '',
      delta_excellent: profile.delta_excellent,
      delta_good: profile.delta_good,
      delta_above_be: profile.delta_above_be,
      delta_high: profile.delta_high,
      delta_low_impressions: profile.delta_low_impressions,
      delta_no_sales: profile.delta_no_sales,
      low_impressions_threshold: profile.low_impressions_threshold,
      min_spend_for_decrement: profile.min_spend_for_decrement,
      max_clicks_no_sales: profile.max_clicks_no_sales ?? 10,
      max_clicks_for_low_impressions: profile.max_clicks_for_low_impressions ?? 0,
      pause_on_clicks_enabled: profile.pause_on_clicks_enabled ?? true,
      is_default: profile.is_default
    });
    setIsCreating(false);
  };

  const startCreate = () => {
    setIsCreating(true);
    setEditingProfile(null);
    setFormData(defaultProfile);
  };

  const cancelEdit = () => {
    setIsCreating(false);
    setEditingProfile(null);
    setFormData(defaultProfile);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <select
          value={selectedProfileId || ''}
          onChange={(e) => {
            const value = e.target.value;
            if (value === '' || value === 'clear') {
              onProfileSelect?.(0);
            } else {
              const parsed = parseInt(value);
              if (!isNaN(parsed)) {
                onProfileSelect?.(parsed);
              }
            }
          }}
          className="text-sm border border-gray-300 rounded px-2 py-1 bg-white"
        >
          <option value="">Default (account)</option>
          {profiles.map(p => (
            <option key={p.id} value={p.id}>
              {p.name} {p.is_default ? '(default)' : ''}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Settings className="w-5 h-5 text-indigo-600" />
          Profili Ottimizzazione
        </h2>
        <button
          onClick={startCreate}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        >
          <Plus className="w-4 h-4" />
          Nuovo Profilo
        </button>
      </div>

      <div className="divide-y divide-gray-100">
        {profiles.length === 0 && !isCreating && (
          <div className="p-6 text-center text-gray-500">
            Nessun profilo configurato. Crea il tuo primo profilo per personalizzare le regole di bidding.
          </div>
        )}

        {profiles.map(profile => (
          <div key={profile.id} className="p-4">
            {editingProfile?.id === profile.id ? (
              <ProfileForm
                formData={formData}
                setFormData={setFormData}
                onSave={handleUpdate}
                onCancel={cancelEdit}
                saving={saving}
                isEdit
              />
            ) : (
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{profile.name}</span>
                    {profile.is_system && (
                      <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">Sistema</span>
                    )}
                    {profile.is_default && (
                      <span className="px-2 py-0.5 text-xs bg-indigo-100 text-indigo-700 rounded">Default</span>
                    )}
                  </div>
                  {profile.description && (
                    <p className="text-sm text-gray-500 mt-1">{profile.description}</p>
                  )}
                  <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-500">
                    <span>Eccellente: <b className="text-green-600">+{profile.delta_excellent}</b></span>
                    <span>Buono: <b className="text-green-600">+{profile.delta_good}</b></span>
                    <span>Sopra BE: <b className="text-red-600">{profile.delta_above_be}</b></span>
                    <span>Alto: <b className="text-red-600">{profile.delta_high}</b></span>
                    <span>Low Impr: <b className="text-blue-600">+{profile.delta_low_impressions}</b></span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => startEdit(profile)}
                    className="p-1.5 text-gray-400 hover:text-indigo-600 rounded"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  {!profile.is_system && (
                    <button
                      onClick={() => handleDelete(profile.id)}
                      className="p-1.5 text-gray-400 hover:text-red-600 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}

        {isCreating && (
          <div className="p-4">
            <ProfileForm
              formData={formData}
              setFormData={setFormData}
              onSave={handleCreate}
              onCancel={cancelEdit}
              saving={saving}
            />
          </div>
        )}
      </div>
    </div>
  );
}

interface ProfileFormProps {
  formData: Omit<SettingsProfile, 'id'>;
  setFormData: (data: Omit<SettingsProfile, 'id'>) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
  isEdit?: boolean;
}

function ProfileForm({ formData, setFormData, onSave, onCancel, saving, isEdit }: ProfileFormProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Nome Profilo *</label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Es: Aggressivo, Conservativo..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Descrizione</label>
          <input
            type="text"
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Descrizione opzionale"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Eccellente (ACOS &lt; BE/3)
          </label>
          <div className="flex items-center gap-1">
            <span className="text-green-600 text-sm">+$</span>
            <input
              type="number"
              step="0.01"
              value={formData.delta_excellent}
              onChange={(e) => setFormData({ ...formData, delta_excellent: parseFloat(e.target.value) || 0 })}
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Buono (BE/3 &lt; ACOS &lt; BE/1.5)
          </label>
          <div className="flex items-center gap-1">
            <span className="text-green-600 text-sm">+$</span>
            <input
              type="number"
              step="0.01"
              value={formData.delta_good}
              onChange={(e) => setFormData({ ...formData, delta_good: parseFloat(e.target.value) || 0 })}
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Sopra BE (BE &lt; ACOS &lt; BE/0.75)
          </label>
          <div className="flex items-center gap-1">
            <span className="text-red-600 text-sm">$</span>
            <input
              type="number"
              step="0.01"
              value={formData.delta_above_be}
              onChange={(e) => setFormData({ ...formData, delta_above_be: parseFloat(e.target.value) || 0 })}
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Alto (ACOS &gt; BE/0.75)
          </label>
          <div className="flex items-center gap-1">
            <span className="text-red-600 text-sm">$</span>
            <input
              type="number"
              step="0.01"
              value={formData.delta_high}
              onChange={(e) => setFormData({ ...formData, delta_high: parseFloat(e.target.value) || 0 })}
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Low Impressions (soglia)
          </label>
          <input
            type="number"
            step="10"
            value={formData.low_impressions_threshold}
            onChange={(e) => setFormData({ ...formData, low_impressions_threshold: parseInt(e.target.value) || 0 })}
            className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Delta Low Impressions
          </label>
          <div className="flex items-center gap-1">
            <span className="text-blue-600 text-sm">+$</span>
            <input
              type="number"
              step="0.01"
              value={formData.delta_low_impressions}
              onChange={(e) => setFormData({ ...formData, delta_low_impressions: parseFloat(e.target.value) || 0 })}
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            No Sales (spesa &gt;)
          </label>
          <div className="flex items-center gap-1">
            <span className="text-gray-500 text-sm">$</span>
            <input
              type="number"
              step="0.50"
              value={formData.min_spend_for_decrement}
              onChange={(e) => setFormData({ ...formData, min_spend_for_decrement: parseFloat(e.target.value) || 0 })}
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Delta No Sales
          </label>
          <div className="flex items-center gap-1">
            <span className="text-red-600 text-sm">$</span>
            <input
              type="number"
              step="0.01"
              value={formData.delta_no_sales}
              onChange={(e) => setFormData({ ...formData, delta_no_sales: parseFloat(e.target.value) || 0 })}
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Max Clicks Low Impr
          </label>
          <div className="flex items-center gap-1">
            <span className="text-blue-500 text-sm">&lt;</span>
            <input
              type="number"
              step="1"
              min="0"
              value={formData.max_clicks_for_low_impressions}
              onChange={(e) => setFormData({ ...formData, max_clicks_for_low_impressions: parseInt(e.target.value) || 0 })}
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
          </div>
          <p className="text-xs text-gray-400 mt-0.5">Incremento solo se clicks &lt; soglia (0 = disattivato)</p>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Max Clicks No Sales
          </label>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setFormData({ ...formData, pause_on_clicks_enabled: !formData.pause_on_clicks_enabled })}
              className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${formData.pause_on_clicks_enabled ? 'bg-indigo-600' : 'bg-gray-300'}`}
            >
              <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${formData.pause_on_clicks_enabled ? 'translate-x-4' : 'translate-x-0'}`} />
            </button>
            <input
              type="number"
              step="1"
              min="1"
              value={formData.max_clicks_no_sales}
              onChange={(e) => setFormData({ ...formData, max_clicks_no_sales: parseInt(e.target.value) || 10 })}
              disabled={!formData.pause_on_clicks_enabled}
              className={`w-full px-2 py-1.5 border border-gray-300 rounded text-sm ${!formData.pause_on_clicks_enabled ? 'bg-gray-100 text-gray-400' : ''}`}
            />
          </div>
          <p className="text-xs text-gray-400 mt-0.5">{formData.pause_on_clicks_enabled ? `PAUSA se clicks ≥ ${formData.max_clicks_no_sales} e 0 vendite` : 'Pausa disattivata'}</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={formData.is_default}
            onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
            className="rounded border-gray-300"
          />
          Imposta come default
        </label>
      </div>

      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
        >
          Annulla
        </button>
        <button
          onClick={onSave}
          disabled={saving || !formData.name.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
          {isEdit ? 'Salva Modifiche' : 'Crea Profilo'}
        </button>
      </div>
    </div>
  );
}
