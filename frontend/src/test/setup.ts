// Setup global para la suite de tests con vitest + jsdom.
// Registra los matchers de @testing-library/jest-dom (toBeInTheDocument, etc.)
// y limpia el DOM montado por Testing Library tras cada test.
import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom no implementa matchMedia; varios componentes (Modal, Dropdown) lo
// consultan al montar. Stub que reporta "desktop" (matches: false) para que
// no rompan bajo el entorno de test.
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

afterEach(() => {
  cleanup();
});
