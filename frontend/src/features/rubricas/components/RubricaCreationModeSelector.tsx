import { cn } from '@/shared/utils/cn';
import { CREATION_MODES } from '../constants/rubrica-constants';
import type { CreationMode } from '../constants/rubrica-constants';

interface Props {
  creationMode: CreationMode;
  setCreationMode: (mode: CreationMode) => void;
}

export function RubricaCreationModeSelector({ creationMode, setCreationMode }: Props) {
  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold">Modo de Creación</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {CREATION_MODES.map((mode) => {
          const Icon = mode.icon;
          const isActive = creationMode === mode.id;
          return (
            <button
              key={mode.id}
              type="button"
              onClick={() => setCreationMode(mode.id)}
              className={cn(
                'flex flex-row items-center gap-3 p-4 text-left rounded-lg transition-colors touch-manipulation',
                'sm:flex-col sm:items-center sm:text-center sm:gap-0',
                isActive
                  ? cn('border-2', mode.activeBorder, mode.activeBg)
                  : 'border border-border bg-card hover:bg-muted'
              )}
            >
              <Icon
                className={cn('h-6 w-6 shrink-0 sm:mb-2', isActive ? mode.activeText : 'text-muted-foreground')}
              />
              <span className="flex flex-col sm:items-center">
                <span
                  className={cn(
                    'text-sm font-medium',
                    isActive ? mode.activeText : 'text-foreground'
                  )}
                >
                  {mode.label}
                </span>
                <span
                  className={cn(
                    'text-xs text-left sm:mt-0.5 sm:text-center',
                    'text-muted-foreground'
                  )}
                >
                  {mode.description}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
