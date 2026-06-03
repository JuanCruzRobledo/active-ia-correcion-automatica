/**
 * ThemeProvider — provee el tema claro/oscuro a la app.
 *
 * Sincroniza el estado de React con el atributo data-theme en <html> y lo
 * persiste en localStorage. El valor inicial ya queda aplicado por el script
 * anti-FOUC de index.html; acá lo levantamos y exponemos el toggle.
 */
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { ThemeContext, STORAGE_KEY, type Theme } from './useTheme';

const getInitialTheme = (): Theme => {
  if (typeof document !== 'undefined') {
    const current = document.documentElement.getAttribute('data-theme');
    if (current === 'light' || current === 'dark') return current;
  }
  if (typeof window !== 'undefined') {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === 'light' || stored === 'dark') return stored;
    } catch {
      /* localStorage no disponible */
    }
    if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark';
  }
  return 'light';
};

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* localStorage no disponible: el tema vive solo en memoria */
    }
  }, [theme]);

  const setTheme = useCallback((next: Theme) => setThemeState(next), []);
  const toggleTheme = useCallback(
    () => setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark')),
    []
  );

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
