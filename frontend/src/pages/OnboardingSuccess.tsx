export default function OnboardingSuccess() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-green-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
        <div className="w-20 h-20 bg-gradient-to-br from-green-400 to-green-600 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
          <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        
        <h1 className="text-2xl font-bold text-gray-900 mb-3">Account Collegato!</h1>
        
        <p className="text-gray-600 mb-6">
          Il tuo account Amazon Ads è stato collegato con successo. 
          Il tuo gestore potrà ora visualizzare e ottimizzare le tue campagne pubblicitarie.
        </p>
        
        <div className="bg-green-50 rounded-xl p-4 mb-6">
          <h3 className="font-medium text-green-900 mb-2">Prossimi passi</h3>
          <p className="text-sm text-green-800">
            Non devi fare nient'altro. Il tuo gestore ti contatterà per aggiornarti 
            sulle performance delle tue campagne.
          </p>
        </div>
        
        <p className="text-sm text-gray-500">
          Puoi chiudere questa pagina.
        </p>
      </div>
    </div>
  );
}
