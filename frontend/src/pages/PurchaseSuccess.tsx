import { Link } from 'react-router-dom';

export default function PurchaseSuccess() {
  return (
    <div className="min-h-screen bg-[#0F1D32] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="mb-6 flex justify-center">
          <div className="w-20 h-20 rounded-full bg-[#00D4FF]/10 border border-[#00D4FF]/30 flex items-center justify-center">
            <svg className="w-10 h-10 text-[#00D4FF]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
        </div>

        <h1 className="text-3xl font-bold text-white mb-3">
          Acquisto completato!
        </h1>
        <p className="text-gray-400 text-base mb-6 leading-relaxed">
          Grazie per aver acquistato Essentia Suite.<br />
          Controlla la tua email: ti abbiamo inviato un link per impostare la password e accedere al tuo account.
        </p>

        <div className="bg-[#1a2d47] border border-[#00D4FF]/20 rounded-xl p-5 mb-8 text-left">
          <p className="text-[#00D4FF] font-semibold text-sm mb-2">Cosa fare adesso</p>
          <ol className="space-y-2 text-sm text-gray-300">
            <li className="flex gap-2">
              <span className="text-[#00D4FF] font-bold">1.</span>
              <span>Apri la tua casella email e cerca il messaggio da <strong className="text-white">noreply@essentia-ads.io</strong></span>
            </li>
            <li className="flex gap-2">
              <span className="text-[#00D4FF] font-bold">2.</span>
              <span>Clicca il link per impostare la tua password (valido 48 ore)</span>
            </li>
            <li className="flex gap-2">
              <span className="text-[#00D4FF] font-bold">3.</span>
              <span>Accedi e inizia a usare il software</span>
            </li>
          </ol>
        </div>

        <p className="text-gray-500 text-sm mb-4">
          Non hai ricevuto l'email? Controlla la cartella spam o{' '}
          <Link to="/forgot-password" className="text-[#00D4FF] hover:underline">
            richiedila di nuovo
          </Link>
          .
        </p>

        <Link
          to="/login"
          className="inline-block px-6 py-3 rounded-lg bg-[#00D4FF]/10 border border-[#00D4FF]/30 text-[#00D4FF] hover:bg-[#00D4FF]/20 transition-colors text-sm font-medium"
        >
          Vai al login
        </Link>
      </div>
    </div>
  );
}
