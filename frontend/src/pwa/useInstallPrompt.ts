import { useCallback, useEffect, useState } from 'react';

/**
 * Evento no estandar `beforeinstallprompt` (Chromium). No esta en lib.dom,
 * por eso lo tipamos a mano.
 */
interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
  prompt: () => Promise<void>;
}

/** True si la app ya corre instalada (standalone). */
function isStandalone(): boolean {
  if (typeof window === 'undefined') return false;
  const mql = window.matchMedia('(display-mode: standalone)').matches;
  // iOS Safari expone `navigator.standalone` en vez de matchMedia.
  const iosStandalone = (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
  return mql || iosStandalone;
}

/** True si el navegador es Safari en iOS/iPadOS (no soporta beforeinstallprompt). */
function isIosSafari(): boolean {
  if (typeof window === 'undefined') return false;
  const ua = window.navigator.userAgent;
  const isIos = /iphone|ipad|ipod/i.test(ua) ||
    // iPadOS 13+ se reporta como Mac con touch.
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isSafari = /safari/i.test(ua) && !/crios|fxios|edgios|chrome/i.test(ua);
  return isIos && isSafari;
}

export interface UseInstallPromptResult {
  /** True si se puede ofrecer la instalacion (Chromium) y no esta ya instalada. */
  canInstall: boolean;
  /** Lanza el dialogo nativo de instalacion. Devuelve true si el usuario acepto. */
  promptInstall: () => Promise<boolean>;
  /** True en Safari iOS, donde la instalacion es manual (Compartir -> Agregar a inicio). */
  isIos: boolean;
  /** True si la app ya esta instalada / en modo standalone. */
  installed: boolean;
}

/**
 * Captura el evento `beforeinstallprompt` y expone una API simple para
 * ofrecer la instalacion de la PWA. En iOS, donde no existe ese evento,
 * expone `isIos` para mostrar instrucciones manuales.
 */
export function useInstallPrompt(): UseInstallPromptResult {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState<boolean>(() => isStandalone());

  useEffect(() => {
    const onBeforeInstallPrompt = (e: Event) => {
      // Evita el mini-infobar automatico de Chrome y guarda el evento para
      // dispararlo cuando el usuario toque "Instalar app".
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };

    const onAppInstalled = () => {
      setDeferredPrompt(null);
      setInstalled(true);
    };

    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    window.addEventListener('appinstalled', onAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
      window.removeEventListener('appinstalled', onAppInstalled);
    };
  }, []);

  const promptInstall = useCallback(async (): Promise<boolean> => {
    if (!deferredPrompt) return false;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    // El evento solo se puede usar una vez.
    setDeferredPrompt(null);
    return outcome === 'accepted';
  }, [deferredPrompt]);

  return {
    canInstall: !installed && deferredPrompt !== null,
    promptInstall,
    isIos: isIosSafari(),
    installed,
  };
}
