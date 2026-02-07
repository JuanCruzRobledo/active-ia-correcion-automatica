import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

interface KeyValueInputProps {
  value: Record<string, any>;
  onChange: (metadata: Record<string, any>) => void;
  placeholder?: { key: string; value: string };
  className?: string;
}

/**
 * KeyValueInput - Input para pares clave-valor dinámicos
 *
 * Uso: Para metadata flexible de rúbricas
 * - Agregar campos personalizados
 * - Eliminar campos
 */
export function KeyValueInput({
  value = {},
  onChange,
  placeholder = { key: 'ej: lenguaje', value: 'ej: JavaScript' },
  className,
}: KeyValueInputProps) {
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');

  const entries = Object.entries(value);

  const handleAdd = () => {
    const trimmedKey = newKey.trim();
    const trimmedValue = newValue.trim();

    if (!trimmedKey || !trimmedValue) return;
    if (value[trimmedKey] !== undefined) {
      // Clave ya existe
      return;
    }

    onChange({ ...value, [trimmedKey]: trimmedValue });
    setNewKey('');
    setNewValue('');
  };

  const handleRemove = (key: string) => {
    const { [key]: _, ...rest } = value;
    onChange(rest);
  };

  const handleUpdate = (oldKey: string, newVal: string) => {
    onChange({ ...value, [oldKey]: newVal });
  };

  return (
    <div className={cn('space-y-3', className)}>
      {/* Campos existentes */}
      {entries.length > 0 && (
        <div className="space-y-2">
          {entries.map(([key, val]) => (
            <div key={key} className="flex gap-2 items-center">
              <div className="flex-1 grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={key}
                  disabled
                  className="px-3 py-2 text-sm border border-input rounded-md bg-muted text-muted-foreground"
                />
                <input
                  type="text"
                  value={val}
                  onChange={(e) => handleUpdate(key, e.target.value)}
                  className="px-3 py-2 text-sm border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <button
                type="button"
                onClick={() => handleRemove(key)}
                className="text-muted-foreground hover:text-destructive transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Agregar nuevo campo */}
      <div className="flex gap-2">
        <div className="flex-1 grid grid-cols-2 gap-2">
          <input
            type="text"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder={placeholder.key}
            className="px-3 py-2 text-sm border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <input
            type="text"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder={placeholder.value}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleAdd();
              }
            }}
            className="px-3 py-2 text-sm border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <button
          type="button"
          onClick={handleAdd}
          disabled={!newKey.trim() || !newValue.trim()}
          className={cn(
            'px-3 py-2 rounded-md text-sm font-medium transition-colors',
            'bg-accent text-accent-foreground',
            'hover:bg-accent/90',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Helper text */}
      {entries.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Agrega campos personalizados como: lenguaje, framework, modalidad, etc.
        </p>
      )}
    </div>
  );
}
