import { useState, type KeyboardEvent } from 'react';
import { X, Plus } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

interface ExtensionTagInputProps {
  /** Controlled list of extensions (e.g. ['.sql', '.sh']) */
  value: string[];
  onChange: (tags: string[]) => void;
  className?: string;
  error?: string;
}

/**
 * ExtensionTagInput — Tag input specialized for file extensions.
 *
 * Normalizes input: strips whitespace, lowercases, prepends dot if missing.
 * De-duplicates tags automatically.
 * Trigger: Enter key or the + button.
 * Remove: click the × on each tag.
 *
 * Used in CargaEntregaModal when modo_consolidacion === 'PERSONALIZADO'.
 */
export function ExtensionTagInput({
  value = [],
  onChange,
  className,
  error,
}: ExtensionTagInputProps) {
  const [inputValue, setInputValue] = useState('');

  const normalize = (raw: string): string => {
    const trimmed = raw.trim().toLowerCase().replace(/[\s,]+/g, '');
    if (!trimmed) return '';
    return trimmed.startsWith('.') ? trimmed : `.${trimmed}`;
  };

  const addTag = () => {
    const ext = normalize(inputValue);
    if (!ext || value.includes(ext)) {
      setInputValue('');
      return;
    }
    onChange([...value, ext]);
    setInputValue('');
  };

  const removeTag = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag();
    }
  };

  return (
    <div className={cn('space-y-2', className)}>
      {/* Input row */}
      <div className="flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder=".sql, .sh, .env… (Enter para agregar)"
          className={cn(
            'flex-1 px-3 py-2 text-sm border rounded-md',
            'bg-background text-foreground',
            'focus:outline-none focus:ring-2 focus:ring-ring',
            'placeholder:text-muted-foreground',
            error ? 'border-destructive' : 'border-input'
          )}
        />
        <button
          type="button"
          onClick={addTag}
          disabled={!inputValue.trim()}
          className={cn(
            'px-3 py-2 rounded-md text-sm font-medium transition-colors',
            'bg-accent text-accent-foreground hover:bg-accent/90',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Tags */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((tag, index) => (
            <div
              key={index}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted text-foreground text-sm font-mono"
            >
              <span>{tag}</span>
              <button
                type="button"
                onClick={() => removeTag(index)}
                className="text-muted-foreground hover:text-destructive transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Help text / error */}
      {error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : (
        <p className="text-xs text-muted-foreground">
          El punto es opcional — se agrega automáticamente. Sin duplicados.
        </p>
      )}
    </div>
  );
}
