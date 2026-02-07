import { createContext, useContext, useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

// ============================================================================
// Accordion Context
// ============================================================================

type AccordionContextValue = {
  openItems: string[];
  toggleItem: (value: string) => void;
  multiple?: boolean;
};

const AccordionContext = createContext<AccordionContextValue | undefined>(undefined);

function useAccordion() {
  const context = useContext(AccordionContext);
  if (!context) {
    throw new Error('useAccordion must be used within Accordion');
  }
  return context;
}

// ============================================================================
// Accordion Root
// ============================================================================

interface AccordionProps {
  children: ReactNode;
  defaultValue?: string | string[];
  multiple?: boolean;
  className?: string;
}

export function Accordion({
  children,
  defaultValue = [],
  multiple = true,
  className,
}: AccordionProps) {
  const [openItems, setOpenItems] = useState<string[]>(
    Array.isArray(defaultValue) ? defaultValue : [defaultValue]
  );

  const toggleItem = (value: string) => {
    setOpenItems((prev) => {
      if (multiple) {
        return prev.includes(value)
          ? prev.filter((item) => item !== value)
          : [...prev, value];
      } else {
        return prev.includes(value) ? [] : [value];
      }
    });
  };

  return (
    <AccordionContext.Provider value={{ openItems, toggleItem, multiple }}>
      <div className={cn('space-y-3', className)}>{children}</div>
    </AccordionContext.Provider>
  );
}

// ============================================================================
// Accordion Item
// ============================================================================

interface AccordionItemProps {
  value: string;
  children: ReactNode;
  className?: string;
}

export function AccordionItem({ children, className }: AccordionItemProps) {
  // value prop is used by parent for identification, not needed in render
  return (
    <div
      className={cn(
        'border border-border rounded-lg bg-card overflow-hidden',
        className
      )}
    >
      {children}
    </div>
  );
}

// ============================================================================
// Accordion Trigger
// ============================================================================

interface AccordionTriggerProps {
  children: ReactNode;
  value: string;
  icon?: ReactNode;
  badge?: ReactNode;
  className?: string;
}

export function AccordionTrigger({
  children,
  value,
  icon,
  badge,
  className,
}: AccordionTriggerProps) {
  const { openItems, toggleItem } = useAccordion();
  const isOpen = openItems.includes(value);

  return (
    <button
      type="button"
      onClick={() => toggleItem(value)}
      className={cn(
        'w-full flex items-center justify-between px-4 py-3',
        'text-left font-medium transition-colors',
        'hover:bg-muted/50',
        className
      )}
    >
      <div className="flex items-center gap-2 flex-1">
        {icon && <span className="text-muted-foreground">{icon}</span>}
        <span className="text-foreground">{children}</span>
        {badge}
      </div>
      <ChevronDown
        className={cn(
          'h-5 w-5 text-muted-foreground transition-transform duration-200',
          isOpen && 'rotate-180'
        )}
      />
    </button>
  );
}

// ============================================================================
// Accordion Content
// ============================================================================

interface AccordionContentProps {
  value: string;
  children: ReactNode;
  className?: string;
}

export function AccordionContent({
  value,
  children,
  className,
}: AccordionContentProps) {
  const { openItems } = useAccordion();
  const isOpen = openItems.includes(value);

  if (!isOpen) return null;

  return (
    <div className={cn('px-4 pb-4 pt-2', className)}>
      {children}
    </div>
  );
}
