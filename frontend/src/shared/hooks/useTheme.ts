/**
 * useTheme — contexto y hook del tema claro/oscuro de la app.
 *
 * El tema se persiste en localStorage ('active-ia-theme') y se aplica como
 * atributo data-theme en <html>, que es lo que consume index.css para
 * resolver los tokens OKLCH ([data-theme="dark"]).
 *
 * El ThemeProvider (componente) vive en ./ThemeProvider para no mezclar
 * componentes con utilidades en un mismo archivo (react-refresh).
 */
import { createContext, useContext } from 'react';

export type Theme = 'light' | 'dark';

export const STORAGE_KEY = 'active-ia-theme';

export interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export const useTheme = (): ThemeContextValue => {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme debe usarse dentro de un ThemeProvider');
  }
  return ctx;
};
