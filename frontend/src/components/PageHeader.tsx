import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}

export default function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-[#0F1D32] border border-[#00D4FF]/20 p-6 mb-6">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#00D4FF] via-[#00A8CC] to-[#00D4FF]"></div>
      <div className="relative flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{title}</h1>
          {subtitle && (
            <p className="text-gray-400 text-sm mt-1">{subtitle}</p>
          )}
        </div>
        {action && (
          <div>
            {action}
          </div>
        )}
      </div>
    </div>
  );
}
