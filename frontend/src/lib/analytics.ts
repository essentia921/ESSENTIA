import ReactGA from 'react-ga4';

const GA_ID = import.meta.env.VITE_GA4_ID as string | undefined;

export function initGA(): void {
  if (!GA_ID) return;
  ReactGA.initialize(GA_ID, { gtagOptions: { anonymize_ip: true } });
}

export function trackPageView(path: string, title?: string, params?: Record<string, string>): void {
  if (!GA_ID) return;
  ReactGA.send({ hitType: 'pageview', page: path, title: title || document.title, ...params });
}

export function trackEvent(name: string, params?: Record<string, string | number | boolean>): void {
  if (!GA_ID) return;
  ReactGA.event(name, params);
}
