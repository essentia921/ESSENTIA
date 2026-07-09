import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { 
  Settings as SettingsIcon, User, Bell, Shield, CreditCard, Check, AlertCircle,
  Lock, Mail, FileText, ExternalLink, Loader2, X
} from 'lucide-react';
import Layout from '../components/Layout';
import axios from 'axios';

interface SubscriptionDetails {
  status: string;
  current_period_end: number | null;
  cancel_at_period_end: boolean;
  plan_name: string | null;
  amount: number | null;
  currency: string | null;
  interval: string | null;
}

interface Invoice {
  id: string;
  number: string;
  amount: number;
  currency: string;
  status: string;
  created: number;
  invoice_pdf: string | null;
  hosted_invoice_url: string | null;
}

export default function Settings() {
  const { user, isSubscribed, refreshUser, logout } = useAuth();
  const [notifications, setNotifications] = useState({
    email: true,
    bidChanges: true,
    weeklyReport: false,
  });
  const [saved, setSaved] = useState(false);
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  const [newEmail, setNewEmail] = useState('');
  const [emailPassword, setEmailPassword] = useState('');
  const [emailError, setEmailError] = useState('');
  const [emailSuccess, setEmailSuccess] = useState('');
  const [isChangingEmail, setIsChangingEmail] = useState(false);

  const [subscriptionDetails, setSubscriptionDetails] = useState<SubscriptionDetails | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [isLoadingSubscription, setIsLoadingSubscription] = useState(true);
  const [isLoadingInvoices, setIsLoadingInvoices] = useState(true);
  const [isOpeningPortal, setIsOpeningPortal] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);

  useEffect(() => {
    if (user?.full_name) {
      setFullName(user.full_name);
    }
  }, [user]);

  useEffect(() => {
    fetchSubscriptionDetails();
    fetchInvoices();
  }, []);

  const fetchSubscriptionDetails = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get('/api/subscriptions/details', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSubscriptionDetails(response.data);
    } catch (error) {
      console.error('Error fetching subscription details:', error);
    } finally {
      setIsLoadingSubscription(false);
    }
  };

  const fetchInvoices = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get('/api/subscriptions/invoices', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setInvoices(response.data.invoices || []);
    } catch (error) {
      console.error('Error fetching invoices:', error);
    } finally {
      setIsLoadingInvoices(false);
    }
  };

  const handleSaveProfile = async () => {
    setIsUpdatingProfile(true);
    try {
      const token = localStorage.getItem('token');
      await axios.put('/api/auth/profile', 
        { full_name: fullName },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      refreshUser();
    } catch (error) {
      console.error('Error updating profile:', error);
    } finally {
      setIsUpdatingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError('');
    setPasswordSuccess('');

    if (newPassword !== confirmPassword) {
      setPasswordError('Le password non coincidono');
      return;
    }

    if (newPassword.length < 6) {
      setPasswordError('La password deve avere almeno 6 caratteri');
      return;
    }

    setIsChangingPassword(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post('/api/auth/change-password', 
        { current_password: currentPassword, new_password: newPassword },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setPasswordSuccess('Password aggiornata con successo');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error: any) {
      setPasswordError(error.response?.data?.detail || 'Errore nel cambio password');
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleChangeEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setEmailError('');
    setEmailSuccess('');

    setIsChangingEmail(true);
    try {
      const token = localStorage.getItem('token');
      const response = await axios.post('/api/auth/change-email',
        { new_email: newEmail, password: emailPassword },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      localStorage.setItem('token', response.data.access_token);
      setEmailSuccess('Email aggiornata con successo');
      setNewEmail('');
      setEmailPassword('');
      refreshUser();
    } catch (error: any) {
      setEmailError(error.response?.data?.detail || 'Errore nel cambio email');
    } finally {
      setIsChangingEmail(false);
    }
  };

  const handleOpenPortal = async () => {
    setIsOpeningPortal(true);
    try {
      const token = localStorage.getItem('token');
      const response = await axios.post('/api/subscriptions/customer-portal',
        { return_url: window.location.href },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      window.location.href = response.data.portal_url;
    } catch (error: any) {
      console.error('Error opening customer portal:', error);
      alert(error.response?.data?.detail || 'Errore nell\'apertura del portale');
      setIsOpeningPortal(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleteError('');
    setIsDeletingAccount(true);
    try {
      const token = localStorage.getItem('token');
      await axios.delete('/api/auth/account', {
        headers: { Authorization: `Bearer ${token}` }
      });
      logout();
      window.location.href = '/login';
    } catch (error: any) {
      setDeleteError(error.response?.data?.detail || 'Errore nell\'eliminazione dell\'account');
      setIsDeletingAccount(false);
    }
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString('it-IT', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };

  const formatCurrency = (amount: number, currency: string) => {
    return new Intl.NumberFormat('it-IT', {
      style: 'currency',
      currency: currency || 'EUR'
    }).format(amount);
  };

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[#0F1D32]">Impostazioni</h1>
        <p className="text-gray-600 mt-1">
          Gestisci il tuo account e le preferenze
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <User size={20} className="text-[#00D4FF]" />
              </div>
              <h2 className="text-lg font-semibold text-[#0F1D32]">Profilo</h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Email
                </label>
                <input
                  type="email"
                  value={user?.email || ''}
                  disabled
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nome completo
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
                />
              </div>

              <button
                onClick={handleSaveProfile}
                disabled={isUpdatingProfile}
                className="bg-[#00D4FF] text-white px-6 py-2.5 rounded-lg font-medium hover:bg-[#00B4D8] transition disabled:opacity-50 flex items-center gap-2"
              >
                {isUpdatingProfile ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : saved ? (
                  <Check size={18} />
                ) : (
                  <SettingsIcon size={18} />
                )}
                {saved ? 'Salvato!' : 'Salva profilo'}
              </button>
            </div>
          </div>

          {user?.has_password ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 bg-cyan-100 rounded-lg flex items-center justify-center">
                  <Lock size={20} className="text-cyan-600" />
                </div>
                <h2 className="text-lg font-semibold text-[#0F1D32]">Cambia Password</h2>
              </div>

              {passwordError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                  {passwordError}
                </div>
              )}
              {passwordSuccess && (
                <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">
                  {passwordSuccess}
                </div>
              )}

              <form onSubmit={handleChangePassword} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Password attuale
                  </label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Nuova password
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={6}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
                    placeholder="Minimo 6 caratteri"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Conferma nuova password
                  </label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isChangingPassword}
                  className="bg-[#00D4FF] text-white px-6 py-2.5 rounded-lg font-medium hover:bg-[#00B4D8] transition disabled:opacity-50 flex items-center gap-2"
                >
                  {isChangingPassword && <Loader2 size={18} className="animate-spin" />}
                  Cambia Password
                </button>
              </form>
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-cyan-100 rounded-lg flex items-center justify-center">
                  <Lock size={20} className="text-cyan-600" />
                </div>
                <h2 className="text-lg font-semibold text-[#0F1D32]">Password</h2>
              </div>
              <p className="text-sm text-gray-600">
                Accedi con Google - la password non è richiesta.
              </p>
            </div>
          )}

          {user?.has_password ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Mail size={20} className="text-blue-600" />
                </div>
                <h2 className="text-lg font-semibold text-[#0F1D32]">Cambia Email</h2>
              </div>

              {emailError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                  {emailError}
                </div>
              )}
              {emailSuccess && (
                <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">
                  {emailSuccess}
                </div>
              )}

            <form onSubmit={handleChangeEmail} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nuova email
                </label>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Password (per confermare)
                </label>
                <input
                  type="password"
                  value={emailPassword}
                  onChange={(e) => setEmailPassword(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#00D4FF] focus:border-[#00D4FF] outline-none"
                />
              </div>
              <button
                type="submit"
                disabled={isChangingEmail}
                className="bg-[#00D4FF] text-white px-6 py-2.5 rounded-lg font-medium hover:bg-[#00B4D8] transition disabled:opacity-50 flex items-center gap-2"
              >
                {isChangingEmail && <Loader2 size={18} className="animate-spin" />}
                Cambia Email
              </button>
            </form>
          </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Mail size={20} className="text-blue-600" />
                </div>
                <h2 className="text-lg font-semibold text-[#0F1D32]">Email</h2>
              </div>
              <p className="text-sm text-gray-600">
                L'email è gestita dal tuo account Google e non può essere modificata qui.
              </p>
            </div>
          )}

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                <Bell size={20} className="text-purple-600" />
              </div>
              <h2 className="text-lg font-semibold text-[#0F1D32]">Notifiche</h2>
            </div>

            <div className="space-y-4">
              <label className="flex items-center justify-between p-4 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50 transition">
                <div>
                  <p className="font-medium text-[#0F1D32]">Notifiche email</p>
                  <p className="text-sm text-gray-500">Ricevi aggiornamenti via email</p>
                </div>
                <input
                  type="checkbox"
                  checked={notifications.email}
                  onChange={(e) => setNotifications({ ...notifications, email: e.target.checked })}
                  className="w-5 h-5 rounded border-gray-300 text-[#00D4FF] focus:ring-[#00D4FF]"
                />
              </label>

              <label className="flex items-center justify-between p-4 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50 transition">
                <div>
                  <p className="font-medium text-[#0F1D32]">Notifiche modifica bid</p>
                  <p className="text-sm text-gray-500">Ricevi conferma quando i bid vengono modificati</p>
                </div>
                <input
                  type="checkbox"
                  checked={notifications.bidChanges}
                  onChange={(e) => setNotifications({ ...notifications, bidChanges: e.target.checked })}
                  className="w-5 h-5 rounded border-gray-300 text-[#00D4FF] focus:ring-[#00D4FF]"
                />
              </label>

              <label className="flex items-center justify-between p-4 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50 transition">
                <div>
                  <p className="font-medium text-[#0F1D32]">Report settimanale</p>
                  <p className="text-sm text-gray-500">Ricevi un riepilogo settimanale delle performance</p>
                </div>
                <input
                  type="checkbox"
                  checked={notifications.weeklyReport}
                  onChange={(e) => setNotifications({ ...notifications, weeklyReport: e.target.checked })}
                  className="w-5 h-5 rounded border-gray-300 text-[#00D4FF] focus:ring-[#00D4FF]"
                />
              </label>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <CreditCard size={20} className="text-green-600" />
              </div>
              <h2 className="text-lg font-semibold text-[#0F1D32]">Abbonamento</h2>
            </div>

            {isLoadingSubscription ? (
              <div className="flex justify-center py-4">
                <Loader2 className="animate-spin text-gray-400" size={24} />
              </div>
            ) : isSubscribed ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-green-600">
                  <Check size={20} />
                  <span className="font-medium">
                    {subscriptionDetails?.plan_name || 'Piano PRO'} attivo
                  </span>
                </div>
                
                {subscriptionDetails?.amount && (
                  <p className="text-sm text-gray-600">
                    {formatCurrency(subscriptionDetails.amount, subscriptionDetails.currency || 'EUR')}
                    /{subscriptionDetails.interval === 'month' ? 'mese' : 'anno'}
                  </p>
                )}
                
                {subscriptionDetails?.current_period_end && (
                  <p className="text-sm text-gray-600">
                    {subscriptionDetails.cancel_at_period_end ? (
                      <span className="text-cyan-600">
                        Scade il {formatDate(subscriptionDetails.current_period_end)}
                      </span>
                    ) : (
                      <>Prossimo rinnovo: {formatDate(subscriptionDetails.current_period_end)}</>
                    )}
                  </p>
                )}
                
                <button 
                  onClick={handleOpenPortal}
                  disabled={isOpeningPortal}
                  className="w-full text-sm text-gray-600 hover:text-gray-800 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition flex items-center justify-center gap-2"
                >
                  {isOpeningPortal ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <ExternalLink size={16} />
                  )}
                  Gestisci abbonamento
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-yellow-600">
                  <AlertCircle size={20} />
                  <span className="font-medium">Piano gratuito</span>
                </div>
                <p className="text-sm text-gray-600">
                  Upgrade al piano PRO per sbloccare tutte le funzionalità.
                </p>
                <a
                  href="/pricing"
                  className="block w-full text-center bg-[#00D4FF] text-white py-2 rounded-lg font-medium hover:bg-[#00B4D8] transition"
                >
                  Abbonati - 97 EUR/mese
                </a>
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                <FileText size={20} className="text-indigo-600" />
              </div>
              <h2 className="text-lg font-semibold text-[#0F1D32]">Fatture</h2>
            </div>

            {isLoadingInvoices ? (
              <div className="flex justify-center py-4">
                <Loader2 className="animate-spin text-gray-400" size={24} />
              </div>
            ) : invoices.length > 0 ? (
              <div className="space-y-3 max-h-64 overflow-y-auto">
                {invoices.map((invoice) => (
                  <div key={invoice.id} className="flex items-center justify-between p-3 border border-gray-100 rounded-lg">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {invoice.number || 'Fattura'}
                      </p>
                      <p className="text-xs text-gray-500">
                        {formatDate(invoice.created)} - {formatCurrency(invoice.amount, invoice.currency)}
                      </p>
                    </div>
                    {invoice.invoice_pdf && (
                      <a
                        href={invoice.invoice_pdf}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#00D4FF] hover:text-[#00B4D8] text-sm font-medium"
                      >
                        PDF
                      </a>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500 text-center py-4">
                Nessuna fattura disponibile
              </p>
            )}
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                <Shield size={20} className="text-red-600" />
              </div>
              <h2 className="text-lg font-semibold text-[#0F1D32]">Zona pericolosa</h2>
            </div>

            <div className="space-y-3">
              <p className="text-sm text-gray-600">
                Elimina permanentemente il tuo account e tutti i dati associati.
              </p>
              <button 
                onClick={() => setShowDeleteModal(true)}
                className="w-full text-sm text-red-600 hover:text-red-700 py-2 border border-red-200 rounded-lg hover:bg-red-50 transition"
              >
                Elimina account
              </button>
            </div>
          </div>
        </div>
      </div>

      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-[#0F1D32]">Elimina Account</h3>
              <button onClick={() => { setShowDeleteModal(false); setDeleteError(''); }} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <p className="text-gray-600 mb-4">
              Sei sicuro di voler eliminare il tuo account? Questa azione è irreversibile e tutti i tuoi dati verranno persi.
            </p>
            {deleteError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                {deleteError}
              </div>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => { setShowDeleteModal(false); setDeleteError(''); }}
                disabled={isDeletingAccount}
                className="flex-1 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition disabled:opacity-50"
              >
                Annulla
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={isDeletingAccount}
                className="flex-1 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isDeletingAccount && <Loader2 size={16} className="animate-spin" />}
                Elimina
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
