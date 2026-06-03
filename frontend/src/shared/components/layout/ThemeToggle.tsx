import { Moon, Sun } from 'lucide-react';
import { useTheme } from '@/shared/hooks/useTheme';
import { cn } from '@/shared/utils';

interface ThemeToggleProps {
  /** 'full' = botón ancho con texto (sidebar); 'icon' = solo ícono (mobile header) */
  variant?: 'full' | 'icon';
  className?: string;
}

/**
 * Alterna entre tema claro y oscuro. Lee/escribe el tema vía useTheme,
 * que persiste en localStorage y setea data-theme en <html>.
 */
export const ThemeToggle = ({ variant = 'full', className }: ThemeToggleProps) => {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';
  const Icon = isDark ? Sun : Moon;
  const label = isDark ? 'Modo claro' : 'Modo oscuro';

  if (variant === 'icon') {
    return (
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={label}
        title={label}
        className={cn('rounded-lg p-2 text-foreground transition-colors hover:bg-muted', className)}
      >
        <Icon className="h-6 w-6" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={label}
      className={cn(
        'flex w-full items-center gap-3 rounded-lg px-4 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent',
        className
      )}
    >
      <Icon className="h-5 w-5" />
      <span>{label}</span>
    </button>
  );
};
