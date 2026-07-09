import { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ShoppingBag, X } from 'lucide-react';

const NOTIFICATIONS = [
  { name: 'Marco from Milan 💰', action: 'just booked a Free Strategy Call', time: '2 min ago', amount: '+$1,997' },
  { name: 'Giulia from Rome 🤑', action: 'joined the Profit-First Bundle', time: '5 min ago', amount: '+$947' },
  { name: 'Luca from Turin 💸', action: 'started the Setup Call', time: '8 min ago', amount: '+$500' },
  { name: 'Sara from Florence 💰', action: 'just booked a Free Strategy Call', time: '11 min ago', amount: '+$1,997' },
  { name: 'Davide from Naples 🤑', action: 'purchased Annual Access', time: '14 min ago', amount: '+$1,497' },
  { name: 'Chiara from Bologna 💸', action: 'joined the Profit-First Bundle', time: '18 min ago', amount: '+$947' },
  { name: 'Andrea from Venice 💰', action: 'started the Setup Call', time: '22 min ago', amount: '+$500' },
  { name: 'Francesca from Palermo 🤑', action: 'just booked a Free Strategy Call', time: '25 min ago', amount: '+$1,997' },
  { name: 'Roberto from Genoa 💸', action: 'purchased Annual Access', time: '30 min ago', amount: '+$1,497' },
  { name: 'Elena from Verona 💰', action: 'joined the Profit-First Bundle', time: '33 min ago', amount: '+$947' },
];

export default function SocialProofToast() {
  const [current, setCurrent] = useState<number | null>(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const showDelay = setTimeout(() => {
      setCurrent(0);
      setIndex(0);
    }, 4000);

    return () => clearTimeout(showDelay);
  }, []);

  useEffect(() => {
    if (current === null) return;

    const hideTimer = setTimeout(() => {
      setCurrent(null);
    }, 4000);

    const nextTimer = setTimeout(() => {
      const next = (index + 1) % NOTIFICATIONS.length;
      setIndex(next);
      setCurrent(next);
    }, 15000);

    return () => {
      clearTimeout(hideTimer);
      clearTimeout(nextTimer);
    };
  }, [current, index]);

  const notif = current !== null ? NOTIFICATIONS[current] : null;

  return (
    <div className="fixed bottom-4 left-3 sm:bottom-6 sm:left-6 z-[100] pointer-events-none">
      <AnimatePresence>
        {notif && (
          <motion.div
            key={current}
            initial={{ x: -120, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -120, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            className="pointer-events-auto"
          >
            <div
              style={{
                background: 'rgba(7, 13, 26, 0.92)',
                border: '1px solid rgba(0, 212, 255, 0.25)',
                boxShadow: '0 0 30px rgba(0, 212, 255, 0.12), 0 8px 32px rgba(0,0,0,0.5)',
                backdropFilter: 'blur(16px)',
                maxWidth: 'min(288px, calc(100vw - 1.5rem))',
              }}
              className="rounded-2xl p-3 sm:p-4 flex items-start gap-3"
            >
              <div
                style={{
                  background: 'rgba(0, 212, 255, 0.12)',
                  border: '1px solid rgba(0, 212, 255, 0.3)',
                  boxShadow: '0 0 12px rgba(0, 212, 255, 0.2)',
                }}
                className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
              >
                <ShoppingBag className="w-5 h-5" style={{ color: '#00D4FF' }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-bold text-sm leading-tight">{notif.name}</p>
                <p className="text-gray-400 text-xs mt-0.5 leading-snug">{notif.action}</p>
                <p
                  className="text-sm font-black mt-1"
                  style={{
                    color: '#00D4FF',
                    textShadow: '0 0 10px rgba(0,212,255,0.8)',
                  }}
                >
                  {notif.amount}
                </p>
                <p className="text-gray-600 text-xs mt-0.5">{notif.time}</p>
              </div>
              <button
                onClick={() => setCurrent(null)}
                className="text-gray-600 hover:text-gray-400 transition flex-shrink-0"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
