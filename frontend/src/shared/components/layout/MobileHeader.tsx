import { useState } from 'react';
import { Menu, X, User } from 'lucide-react';
import { NavLink } from 'react-router-dom';

export const MobileHeader = () => {
  const [isOpen, setIsOpen] = useState(false);

  // TODO: Get user from auth context
  const userName = 'Administrador';

  return (
    <header className="lg:hidden sticky top-0 z-50 border-b border-border bg-background">
      <div className="flex h-16 items-center justify-between px-4">
        {/* Menu button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="rounded-lg p-2 hover:bg-muted"
          aria-label="Toggle menu"
        >
          {isOpen ? (
            <X className="h-6 w-6" />
          ) : (
            <Menu className="h-6 w-6" />
          )}
        </button>

        {/* Title */}
        <span className="text-lg font-semibold">Active-IA</span>

        {/* Avatar */}
        <NavLink
          to="/perfil"
          className="rounded-full p-2 hover:bg-muted"
          aria-label="Perfil"
        >
          <User className="h-6 w-6" />
        </NavLink>
      </div>

      {/* Mobile menu */}
      {isOpen && (
        <div className="border-t border-border bg-background p-4">
          <p className="mb-2 text-sm font-medium text-muted-foreground">
            {userName}
          </p>
          {/* TODO: Add mobile navigation items */}
          <p className="text-sm text-muted-foreground">
            Navegación móvil en desarrollo
          </p>
        </div>
      )}
    </header>
  );
};
