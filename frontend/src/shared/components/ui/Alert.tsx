import { forwardRef } from 'react';
import { cn } from '@/shared/utils/cn';
import { Info, CheckCircle, AlertTriangle, AlertCircle } from 'lucide-react';

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'warning' | 'destructive';
  title?: string;
}

const variantStyles = {
  default: {
    container: 'bg-info/10 border-info/30 text-foreground',
    icon: 'text-info',
    Icon: Info,
  },
  success: {
    container: 'bg-success/10 border-success/30 text-foreground',
    icon: 'text-success',
    Icon: CheckCircle,
  },
  warning: {
    container: 'bg-warning/10 border-warning/30 text-foreground',
    icon: 'text-warning',
    Icon: AlertTriangle,
  },
  destructive: {
    container: 'bg-destructive/10 border-destructive/30 text-foreground',
    icon: 'text-destructive',
    Icon: AlertCircle,
  },
};

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = 'default', title, children, ...props }, ref) => {
    const styles = variantStyles[variant];
    const Icon = styles.Icon;

    return (
      <div
        ref={ref}
        role="alert"
        className={cn(
          'relative rounded-lg border p-4',
          styles.container,
          className
        )}
        {...props}
      >
        <div className="flex items-start gap-3">
          <Icon className={cn('h-5 w-5 flex-shrink-0', styles.icon)} />
          <div className="flex-1">
            {title && (
              <h5 className="mb-1 font-medium leading-none tracking-tight">
                {title}
              </h5>
            )}
            <div className="text-sm [&_p]:leading-relaxed">
              {children}
            </div>
          </div>
        </div>
      </div>
    );
  }
);

Alert.displayName = 'Alert';
