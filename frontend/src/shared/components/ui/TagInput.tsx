import { useState, type KeyboardEvent } from 'react';
import { X, Plus } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  maxTags?: number;
  className?: string;
  error?: string;
}

/**
 * TagInput - Input para agregar/eliminar tags (chips)
 *
 * Uso: Para evidencias en subcriterios
 * - Enter o clic en + para agregar
 * - Clic en X para eliminar
 */
export function TagInput({
  value = [],
  onChange,
  placeholder = 'Escribir y presionar Enter...',
  maxTags = 20,
  className,
  error,
}: TagInputProps) {
  const [inputValue, setInputValue] = useState('');

  const handleAdd = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    if (value.includes(trimmed)) {
      // No agregar duplicados
      setInputValue('');
      return;
    }
    if (value.length >= maxTags) return;

    onChange([...value, trimmed]);
    setInputValue('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAdd();
    }
  };

  const handleRemove = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  return (
    <div className={cn('space-y-2', className)}>
      {/* Input + Botón Agregar */}
      <div className="flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={value.length >= maxTags}
          className={cn(
            'flex-1 px-3 py-2 text-sm border rounded-md',
            'bg-background text-foreground',
            'focus:outline-none focus:ring-2 focus:ring-ring',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            error ? 'border-destructive' : 'border-input'
          )}
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={!inputValue.trim() || value.length >= maxTags}
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

      {/* Lista de Tags */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((tag, index) => (
            <div
              key={index}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted text-foreground text-sm"
            >
              <span className="text-muted-foreground">•</span>
              <span>{tag}</span>
              <button
                type="button"
                onClick={() => handleRemove(index)}
                className="text-muted-foreground hover:text-destructive transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {/* Contador */}
      {value.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {value.length} {value.length === 1 ? 'evidencia' : 'evidencias'}
          {maxTags && ` (máx. ${maxTags})`}
        </p>
      )}
    </div>
  );
}
