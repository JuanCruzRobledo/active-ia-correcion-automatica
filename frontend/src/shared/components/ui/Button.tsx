import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * Visual style variant of the button
   * - primary: Main actions (black bg in light mode)
   * - secondary: Secondary actions (gray bg)
   * - success: Success/positive actions (green bg)
   * - destructive: Delete/danger actions (red bg)
   * - outline: Alternative actions (transparent with border)
   * - ghost: Subtle actions (transparent, no border)
   * - link: Link-styled button (transparent, accent color)
   */
  variant?: 'primary' | 'secondary' | 'success' | 'destructive' | 'outline' | 'ghost' | 'link';

  /**
   * Size of the button.
   * En mobile (base) los targets suben a >=44px (Apple HIG); en sm: vuelven
   * al tamaño visual de desktop actual, sin cambiar colores ni tipografía.
   * - sm: Small (visual h-8, text-xs; en mobile min-h 44px sin agrandar el resto)
   * - default: Medium (h-11 sm:h-9, text-sm)
   * - lg: Large (h-12 sm:h-10, text-base)
   * - icon: Square icon button (h-11 w-11 sm:h-9 sm:w-9)
   */
  size?: 'sm' | 'default' | 'lg' | 'icon';

  /**
   * Shows loading spinner and disables button
   */
  isLoading?: boolean;
}

const buttonVariants = {
  variant: {
    primary:
      'bg-primary text-primary-foreground hover:bg-primary/90 focus-visible:ring-primary',
    secondary:
      'bg-secondary text-secondary-foreground hover:bg-secondary/80 focus-visible:ring-secondary',
    success:
      'bg-success text-success-foreground hover:bg-success/90 focus-visible:ring-success',
    destructive:
      'bg-destructive text-destructive-foreground hover:bg-destructive/90 focus-visible:ring-destructive',
    outline:
      'border border-input bg-background hover:bg-accent hover:text-accent-foreground focus-visible:ring-ring',
    ghost:
      'hover:bg-accent hover:text-accent-foreground focus-visible:ring-ring',
    link:
      'text-accent underline-offset-4 hover:underline focus-visible:ring-accent',
  },
  size: {
    // En mobile el target táctil sube a >=44px; en sm: se mantiene el look desktop.
    sm: 'h-8 min-h-[44px] sm:min-h-0 px-3 text-xs',
    default: 'h-11 sm:h-9 px-4 text-sm',
    lg: 'h-12 sm:h-10 px-6 text-base',
    icon: 'h-11 w-11 sm:h-9 sm:w-9 p-2',
  },
};

/**
 * Button component with multiple variants and sizes.
 *
 * @example
 * ```tsx
 * <Button variant="primary" size="default">
 *   Save Changes
 * </Button>
 *
 * <Button variant="destructive" isLoading>
 *   Deleting...
 * </Button>
 *
 * <Button variant="ghost" size="icon">
 *   <Settings className="h-4 w-4" />
 * </Button>
 * ```
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'default',
      isLoading = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        className={cn(
          // Base styles
          'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium',
          // touch-manipulation: mata el delay de 300ms y el doble-tap-zoom en mobile
          'touch-manipulation',
          'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
          'disabled:pointer-events-none disabled:opacity-50',
          // Variant styles
          buttonVariants.variant[variant],
          // Size styles
          buttonVariants.size[size],
          className
        )}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
