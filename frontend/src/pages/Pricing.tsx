import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { subscriptionAPI } from '../lib/api';
import { Check, Zap } from 'lucide-react';
import Layout from '../components/Layout';
import { trackEvent } from '../lib/analytics';

export default function Pricing() {
  const { user, isSubscribed } = useAuth();
  const [isLoading, setIsLoading] = useState(false);

  const handleSubscribe = async () => {
    setIsLoading(true);
    try {
      const affiliateCode = localStorage.getItem('affiliate_ref') || undefined;
      const response = await subscriptionAPI.createCheckout({
        success_url: `${window.location.origin}/pricing?success=true`,
        cancel_url: `${window.location.origin}/pricing?canceled=true`,
        ...(affiliateCode ? { affiliate_code: affiliateCode } : {}),
      });
      window.location.href = response.data.checkout_url;
    } catch (error) {
      console.error('Checkout error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const features = [
    'Gestione multi-account Amazon Ads',
    'Dashboard profili per 22 paesi',
    'Visualizzazione campagne SP',
    'Analisi keyword e target',
    'Modifica bid manuale e automatica',
    'Regole di automazione ACOS',
    'Supporto prioritario',
    'Aggiornamenti gratuiti',
  ];

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 to-slate-800">
        <div className="text-center text-white">
          <h1 className="text-3xl font-bold mb-4">Abbonati per accedere</h1>
          <p className="text-slate-300 mb-6">Effettua il login per visualizzare i piani</p>
          <a
            href="/login"
            onClick={() => trackEvent('click_login')}
            className="inline-block bg-[#00D4FF] text-white px-6 py-3 rounded-lg font-medium hover:bg-[#00A8CC] transition"
          >
            Accedi
          </a>
        </div>
      </div>
    );
  }

  return (
    <Layout>
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-[#0F1D32] mb-4">
            {isSubscribed ? 'Il tuo abbonamento' : 'Scegli il piano PRO'}
          </h1>
          <p className="text-gray-600 text-lg">
            {isSubscribed
              ? 'Grazie per essere un membro PRO!'
              : 'Sblocca tutte le funzionalità di Amazon Ads Manager'}
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl overflow-hidden border-2 border-cyan-500">
          <div className="bg-gradient-to-r from-cyan-600 to-cyan-700 px-8 py-6 text-white">
            <div className="flex items-center gap-2 mb-2">
              <Zap size={24} />
              <span className="text-lg font-semibold">Piano PRO</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-5xl font-bold">97</span>
              <span className="text-2xl">EUR</span>
              <span className="text-cyan-200 ml-1">/mese</span>
            </div>
          </div>

          <div className="p-8">
            <ul className="space-y-4 mb-8">
              {features.map((feature, index) => (
                <li key={index} className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                    <Check size={14} className="text-green-600" />
                  </div>
                  <span className="text-slate-700">{feature}</span>
                </li>
              ))}
            </ul>

            {isSubscribed ? (
              <div className="text-center">
                <div className="inline-flex items-center gap-2 bg-green-100 text-green-700 px-6 py-3 rounded-lg font-medium">
                  <Check size={20} />
                  Abbonamento attivo
                </div>
                <p className="mt-4 text-sm text-gray-500">
                  Hai accesso a tutte le funzionalità PRO
                </p>
              </div>
            ) : (
              <button
                onClick={handleSubscribe}
                disabled={isLoading}
                className="w-full bg-[#00D4FF] text-white py-4 rounded-xl font-semibold text-lg hover:bg-[#00A8CC] transition disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  'Reindirizzamento...'
                ) : (
                  <>
                    <Zap size={20} />
                    Abbonati ora
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        <p className="text-center text-sm text-gray-500 mt-6">
          Pagamento sicuro con Stripe. Puoi cancellare in qualsiasi momento.
        </p>
      </div>
    </Layout>
  );
}
