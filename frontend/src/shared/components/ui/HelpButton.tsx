import { useState, type ReactNode } from 'react';
import { HelpCircle } from 'lucide-react';
import { Modal } from './Modal';

export interface HelpButtonProps {
  /** Título del modal de ayuda. */
  title: string;
  /** Contenido de ayuda (JSX). */
  content: ReactNode;
  /** Tamaño del ícono: 'sm' para formularios, 'md' (default) para páginas. */
  size?: 'sm' | 'md';
  /** Texto opcional al lado del ícono. */
  label?: string;
}

/**
 * Botón de ayuda contextual: muestra un ícono "?" que abre un modal con guía.
 * Reutilizable en páginas (label opcional) y formularios (size="sm").
 */
export function HelpButton({ title, content, size = 'md', label }: HelpButtonProps) {
  const [open, setOpen] = useState(false);
  const iconCls = size === 'sm' ? 'h-4 w-4' : 'h-5 w-5';

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Ayuda"
        title="Ayuda"
        className="flex cursor-pointer items-center gap-1.5 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <HelpCircle className={iconCls} />
        {label && <span className="text-sm font-medium">{label}</span>}
      </button>

      <Modal
        isOpen={open}
        onClose={() => setOpen(false)}
        title={title}
        size="lg"
        disableBackdropClose={false}
      >
        {content}
      </Modal>
    </>
  );
}
