import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  iconColor?: 'blue' | 'green' | 'purple' | 'orange' | 'yellow';
}

const iconColorClasses: Record<string, string> = {
  blue: 'bg-[#00D4FF] text-white',
  green: 'bg-green-500 text-white',
  purple: 'bg-purple-500 text-white',
  orange: 'bg-cyan-500 text-white',
  yellow: 'bg-[#00D4FF] text-white',
};

export default function MetricCard({ title, value, subtitle, icon: Icon, iconColor = 'blue' }: MetricCardProps) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow duration-200">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500 font-medium mb-1">{title}</p>
          <p className="text-3xl font-bold text-[#0F1D32]">{value}</p>
          {subtitle && (
            <p className="text-sm text-gray-400 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${iconColorClasses[iconColor]}`}>
          <Icon size={24} />
        </div>
      </div>
    </div>
  );
}
