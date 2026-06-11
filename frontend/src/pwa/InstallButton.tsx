import { useState } from 'react';
import { Download, Share } from 'lucide-react';
import { Button } from '@/shared/components/ui';
import { cn } from '@/shared/utils/cn';
import { useInstallPrompt } from './useInstallPrompt';

export interface InstallButtonProps {
  /** Clases extra para el contenedor. */
  className?: string;
  /** Variante visual del boton (default: outline). */
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
}

/**
 * Boton "Instalar app". Dispara el prompt nativo de instalacion (Chromium).
 * Se oculta automaticamente si la app ya esta en modo standalone o si el
 * navegador no ofrece la instalacion. En Safari iOS muestra las instrucciones
 * manuales (Compartir -> Agregar a inicio), ya que iOS no expone el prompt.
 */
export function InstallButton({ className, variant = 'outline' }: InstallButtonProps) {
  const { canInstall, promptInstall, isIos, installed } = useInstallPrompt();
  const [showIosHint, setShowIosHint] = useState(false);

  // Ya instalada: no mostrar nada.
  if (installed) return null;

  // iOS Safari: sin prompt nativo, ofrecemos instrucciones manuales.
  if (isIos) {
    return (
      <div className={cn('flex flex-col gap-2', className)}>
        <Button
          type="button"
          variant={variant}
          className="w-full justify-center"
          onClick={() => setShowIosHint((v) => !v)}
        >
          <Share className="h-4 w-4" aria-hidden="true" />
          Instalar app
        </Button>
        {showIosHint && (
          <p className="text-xs text-muted-foreground">
            Toca <span className="font-medium">Compartir</span> y luego{' '}
            <span className="font-medium">Agregar a inicio</span> para instalar Active-IA.
          </p>
        )}
      </div>
    );
  }

  // Chromium: solo si hay un prompt diferido disponible.
  if (!canInstall) return null;

  return (
    <Button
      type="button"
      variant={variant}
      className={cn('w-full justify-center', className)}
      onClick={() => {
        void promptInstall();
      }}
    >
      <Download className="h-4 w-4" aria-hidden="true" />
      Instalar app
    </Button>
  );
}
