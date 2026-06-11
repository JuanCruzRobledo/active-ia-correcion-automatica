import { User } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';

/**
 * Header compacto mobile (oculto en desktop).
 *
 * Ya NO es la navegación principal: eso lo resuelve la bottom tab bar (BottomNav).
 * Solo expone identidad de marca (logo + nombre) y accesos rápidos de perfil y tema.
 * Translúcido + safe-area top para no quedar bajo el notch / dynamic island.
 */
export const MobileHeader = () => {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/80 pt-[env(safe-area-inset-top)] backdrop-blur-md lg:hidden">
      <div className="flex min-h-16 items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <img src="/active-ia-logo.svg" alt="Active-IA Logo" className="h-8 w-8" />
          <span className="text-lg font-semibold">Active-IA</span>
        </div>

        <div className="flex items-center gap-1">
          <ThemeToggle variant="icon" className="min-h-11 min-w-11" />
          <NavLink
            to="/perfil"
            className="flex min-h-11 min-w-11 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted"
            aria-label="Perfil"
          >
            <User className="h-6 w-6" />
          </NavLink>
        </div>
      </div>
    </header>
  );
};
