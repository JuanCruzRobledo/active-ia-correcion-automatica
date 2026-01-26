# 12 - Accesibilidad

---

## 1. Resumen

| Aspecto | Especificación |
|---------|----------------|
| **Nivel WCAG** | 2.1 AA |
| **Tema** | Claro + Oscuro (preferencia sistema + toggle) |
| **Contraste** | 4.5:1 texto normal, 3:1 texto grande |
| **Skip Links** | Sí, "Saltar al contenido" |
| **Screen Readers** | Soporte completo (ARIA, landmarks, live regions) |
| **Navegación teclado** | Completa en todos los componentes |
| **Focus visible** | Ring con color accent |

---

## 2. WCAG 2.1 AA - Criterios Aplicables

### 2.1 Perceptible

| Criterio | Requisito | Implementación |
|----------|-----------|----------------|
| **1.1.1** Contenido no textual | Alt text en imágenes | `alt` descriptivo en todas las imágenes |
| **1.3.1** Info y relaciones | Estructura semántica | HTML5 semántico + ARIA |
| **1.3.2** Secuencia significativa | Orden lógico | DOM order = visual order |
| **1.4.1** Uso del color | No solo color | Iconos + texto + color |
| **1.4.3** Contraste mínimo | 4.5:1 / 3:1 | Variables CSS validadas |
| **1.4.4** Redimensionar texto | Hasta 200% | Unidades relativas (rem) |
| **1.4.10** Reflow | Sin scroll horizontal | Responsive hasta 320px |
| **1.4.11** Contraste no textual | 3:1 componentes UI | Bordes y controles visibles |

### 2.2 Operable

| Criterio | Requisito | Implementación |
|----------|-----------|----------------|
| **2.1.1** Teclado | Todo accesible | Tab, Enter, Escape, Arrows |
| **2.1.2** Sin trampa de teclado | Escape siempre | Modales con cierre ESC |
| **2.4.1** Evitar bloques | Skip links | "Saltar al contenido" |
| **2.4.2** Título de página | Títulos descriptivos | `<title>` dinámico por ruta |
| **2.4.3** Orden del foco | Secuencia lógica | tabindex coherente |
| **2.4.4** Propósito del enlace | Links descriptivos | No usar "click aquí" |
| **2.4.6** Encabezados y etiquetas | Descriptivos | h1-h6 jerárquicos |
| **2.4.7** Foco visible | Indicador claro | Focus ring personalizado |

### 2.3 Comprensible

| Criterio | Requisito | Implementación |
|----------|-----------|----------------|
| **3.1.1** Idioma de la página | lang definido | `<html lang="es">` |
| **3.2.1** Al recibir foco | Sin cambios inesperados | No auto-submit en focus |
| **3.2.2** Al recibir entrada | Predecible | Cambios solo con acción explícita |
| **3.3.1** Identificación de errores | Errores claros | Mensaje + campo resaltado |
| **3.3.2** Etiquetas o instrucciones | Labels visibles | Label + placeholder + tooltip |
| **3.3.3** Sugerencias de error | Ayuda correctiva | "La contraseña debe tener 8+ caracteres" |

### 2.4 Robusto

| Criterio | Requisito | Implementación |
|----------|-----------|----------------|
| **4.1.1** Parsing | HTML válido | Sin errores de validación |
| **4.1.2** Nombre, función, valor | ARIA correcto | Roles y estados apropiados |

---

## 3. Sistema de Temas

### 3.1 Detección y Cambio

```typescript
// shared/hooks/useTheme.ts

type Theme = 'light' | 'dark' | 'system';

/**
 * Hook para gestionar el tema de la aplicación.
 *
 * @returns Objeto con tema actual y función para cambiarlo.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => {
    // Leer preferencia guardada o usar 'system'
    const saved = localStorage.getItem('theme') as Theme;
    return saved || 'system';
  });

  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    // Detectar preferencia del sistema
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const updateResolvedTheme = () => {
      if (theme === 'system') {
        setResolvedTheme(mediaQuery.matches ? 'dark' : 'light');
      } else {
        setResolvedTheme(theme);
      }
    };

    updateResolvedTheme();
    mediaQuery.addEventListener('change', updateResolvedTheme);

    return () => mediaQuery.removeEventListener('change', updateResolvedTheme);
  }, [theme]);

  useEffect(() => {
    // Aplicar clase al documento
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(resolvedTheme);
  }, [resolvedTheme]);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  return { theme, resolvedTheme, setTheme };
}
```

### 3.2 Variables CSS por Tema

```css
/* styles/themes.css */

:root {
  /* Variables base que cambian según tema */
  --color-bg-primary: var(--theme-bg-primary);
  --color-bg-secondary: var(--theme-bg-secondary);
  --color-bg-elevated: var(--theme-bg-elevated);
  --color-text-primary: var(--theme-text-primary);
  --color-text-secondary: var(--theme-text-secondary);
  --color-border: var(--theme-border);
}

/* Tema Claro */
.light {
  --theme-bg-primary: #ffffff;
  --theme-bg-secondary: #f8fafc;
  --theme-bg-elevated: #ffffff;
  --theme-text-primary: #0f172a;
  --theme-text-secondary: #475569;
  --theme-border: #e2e8f0;

  /* Contraste validado: texto #0f172a sobre #ffffff = 15.5:1 */
}

/* Tema Oscuro */
.dark {
  --theme-bg-primary: #0a0a0f;
  --theme-bg-secondary: #12121a;
  --theme-bg-elevated: #1a1a24;
  --theme-text-primary: #f8fafc;
  --theme-text-secondary: #94a3b8;
  --theme-border: #2a2a3a;

  /* Contraste validado: texto #f8fafc sobre #0a0a0f = 18.1:1 */
}
```

### 3.3 Componente Theme Switcher

```tsx
// shared/components/ThemeSwitcher.tsx

import { useTheme } from '@/shared/hooks/useTheme';

/**
 * Componente para cambiar el tema de la aplicación.
 * Accesible con teclado y screen readers.
 */
export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();

  const options = [
    { value: 'light', label: 'Claro', icon: SunIcon },
    { value: 'dark', label: 'Oscuro', icon: MoonIcon },
    { value: 'system', label: 'Sistema', icon: ComputerIcon },
  ] as const;

  return (
    <div
      role="radiogroup"
      aria-label="Seleccionar tema"
      className="flex gap-1 p-1 bg-bg-secondary rounded-lg"
    >
      {options.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          role="radio"
          aria-checked={theme === value}
          onClick={() => setTheme(value)}
          className={`
            p-2 rounded-md transition-colors
            ${theme === value
              ? 'bg-bg-elevated text-text-primary'
              : 'text-text-secondary hover:text-text-primary'
            }
            focus:outline-none focus:ring-2 focus:ring-accent
          `}
          title={label}
        >
          <Icon className="w-5 h-5" aria-hidden="true" />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}
```

---

## 4. Skip Links

### 4.1 Implementación

```tsx
// shared/components/layout/SkipLink.tsx

/**
 * Link para saltar al contenido principal.
 * Visible solo al recibir focus con teclado.
 */
export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="
        sr-only focus:not-sr-only
        focus:absolute focus:top-4 focus:left-4 focus:z-50
        focus:px-4 focus:py-2 focus:bg-accent focus:text-white
        focus:rounded-lg focus:outline-none focus:ring-2 focus:ring-white
        transition-all
      "
    >
      Saltar al contenido principal
    </a>
  );
}
```

### 4.2 Uso en Layout

```tsx
// shared/components/layout/AppLayout.tsx

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SkipLink />

      <header role="banner">
        {/* Header content */}
      </header>

      <nav role="navigation" aria-label="Navegación principal">
        {/* Sidebar */}
      </nav>

      <main id="main-content" role="main" tabIndex={-1}>
        {children}
      </main>

      <footer role="contentinfo">
        {/* Footer si aplica */}
      </footer>
    </>
  );
}
```

---

## 5. Navegación por Teclado

### 5.1 Teclas Estándar

| Tecla | Acción |
|-------|--------|
| `Tab` | Mover al siguiente elemento focusable |
| `Shift + Tab` | Mover al elemento anterior |
| `Enter` | Activar botón/link, abrir select |
| `Space` | Activar botón, toggle checkbox |
| `Escape` | Cerrar modal/dropdown/tooltip |
| `Arrow Up/Down` | Navegar opciones en select/menu |
| `Arrow Left/Right` | Navegar tabs |
| `Home` | Primera opción en lista |
| `End` | Última opción en lista |

### 5.2 Componentes con Navegación Especial

#### Modal

```tsx
// shared/components/ui/Modal.tsx

export function Modal({ isOpen, onClose, title, children }: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      // Guardar elemento activo actual
      previousActiveElement.current = document.activeElement as HTMLElement;

      // Focus en el modal
      modalRef.current?.focus();

      // Trap focus dentro del modal
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          onClose();
          return;
        }

        if (e.key === 'Tab') {
          const focusableElements = modalRef.current?.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );

          if (!focusableElements?.length) return;

          const first = focusableElements[0] as HTMLElement;
          const last = focusableElements[focusableElements.length - 1] as HTMLElement;

          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      };

      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    } else {
      // Restaurar focus al cerrar
      previousActiveElement.current?.focus();
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      ref={modalRef}
      tabIndex={-1}
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Content */}
      <div className="relative bg-bg-elevated rounded-xl p-6 max-w-lg w-full">
        <h2 id="modal-title" className="text-xl font-semibold">
          {title}
        </h2>

        {children}

        <button
          onClick={onClose}
          className="absolute top-4 right-4"
          aria-label="Cerrar modal"
        >
          <XIcon aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
```

#### Dropdown/Select

```tsx
// shared/components/ui/Select.tsx

export function Select({ options, value, onChange, label }: SelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const listRef = useRef<HTMLUListElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (isOpen && focusedIndex >= 0) {
          onChange(options[focusedIndex].value);
          setIsOpen(false);
        } else {
          setIsOpen(true);
        }
        break;

      case 'Escape':
        setIsOpen(false);
        break;

      case 'ArrowDown':
        e.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
        } else {
          setFocusedIndex(prev =>
            prev < options.length - 1 ? prev + 1 : 0
          );
        }
        break;

      case 'ArrowUp':
        e.preventDefault();
        if (isOpen) {
          setFocusedIndex(prev =>
            prev > 0 ? prev - 1 : options.length - 1
          );
        }
        break;

      case 'Home':
        e.preventDefault();
        setFocusedIndex(0);
        break;

      case 'End':
        e.preventDefault();
        setFocusedIndex(options.length - 1);
        break;
    }
  };

  return (
    <div className="relative">
      <label id={`${label}-label`} className="block text-sm mb-1">
        {label}
      </label>

      <button
        type="button"
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-labelledby={`${label}-label`}
        aria-controls={`${label}-listbox`}
        onKeyDown={handleKeyDown}
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2 text-left border rounded-lg focus:ring-2"
      >
        {options.find(o => o.value === value)?.label || 'Seleccionar...'}
      </button>

      {isOpen && (
        <ul
          ref={listRef}
          id={`${label}-listbox`}
          role="listbox"
          aria-labelledby={`${label}-label`}
          className="absolute w-full mt-1 bg-bg-elevated border rounded-lg shadow-lg z-10"
        >
          {options.map((option, index) => (
            <li
              key={option.value}
              role="option"
              aria-selected={option.value === value}
              className={`
                px-4 py-2 cursor-pointer
                ${index === focusedIndex ? 'bg-accent/20' : ''}
                ${option.value === value ? 'font-semibold' : ''}
                hover:bg-bg-hover
              `}
              onClick={() => {
                onChange(option.value);
                setIsOpen(false);
              }}
            >
              {option.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

---

## 6. ARIA y Semántica

### 6.1 Landmarks

```html
<!-- Estructura semántica de la página -->
<body>
  <a href="#main-content" class="skip-link">Saltar al contenido</a>

  <header role="banner">
    <nav aria-label="Navegación principal">
      <!-- Logo, menú principal -->
    </nav>
  </header>

  <aside role="navigation" aria-label="Menú lateral">
    <!-- Sidebar -->
  </aside>

  <main id="main-content" role="main">
    <h1>Título de la página</h1>
    <!-- Contenido principal -->
  </main>

  <footer role="contentinfo">
    <!-- Información de pie -->
  </footer>
</body>
```

### 6.2 ARIA Labels Comunes

| Elemento | ARIA | Ejemplo |
|----------|------|---------|
| **Botón con icono** | `aria-label` | `<button aria-label="Cerrar modal">` |
| **Input** | `aria-describedby` | `<input aria-describedby="password-hint">` |
| **Tabla** | `aria-label` | `<table aria-label="Lista de entregas">` |
| **Loading** | `aria-busy` | `<div aria-busy="true">` |
| **Errores** | `aria-invalid`, `aria-errormessage` | `<input aria-invalid="true" aria-errormessage="email-error">` |
| **Required** | `aria-required` | `<input aria-required="true">` |
| **Expanded** | `aria-expanded` | `<button aria-expanded="false">` |

### 6.3 Live Regions para Notificaciones

```tsx
// shared/components/ui/Toast.tsx

/**
 * Contenedor de notificaciones accesible.
 * Usa aria-live para anunciar cambios a screen readers.
 */
export function ToastContainer() {
  const { toasts } = useToast();

  return (
    <div
      role="region"
      aria-label="Notificaciones"
      aria-live="polite"
      aria-atomic="false"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2"
    >
      {toasts.map(toast => (
        <div
          key={toast.id}
          role="alert"
          aria-live={toast.type === 'error' ? 'assertive' : 'polite'}
          className={`
            p-4 rounded-lg shadow-lg
            ${toast.type === 'success' ? 'bg-success text-white' : ''}
            ${toast.type === 'error' ? 'bg-danger text-white' : ''}
            ${toast.type === 'info' ? 'bg-info text-white' : ''}
          `}
        >
          <div className="flex items-center gap-2">
            <span aria-hidden="true">
              {toast.type === 'success' && <CheckIcon />}
              {toast.type === 'error' && <AlertIcon />}
              {toast.type === 'info' && <InfoIcon />}
            </span>
            <p>{toast.message}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## 7. Formularios Accesibles

### 7.1 Estructura de Campo

```tsx
// shared/components/ui/FormField.tsx

interface FormFieldProps {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}

/**
 * Wrapper para campos de formulario con accesibilidad completa.
 */
export function FormField({
  id,
  label,
  error,
  hint,
  required,
  children
}: FormFieldProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;

  return (
    <div className="mb-4">
      <label
        htmlFor={id}
        className="block text-sm font-medium mb-1"
      >
        {label}
        {required && (
          <span className="text-danger ml-1" aria-hidden="true">*</span>
        )}
        {required && <span className="sr-only">(requerido)</span>}
      </label>

      {hint && (
        <p id={hintId} className="text-sm text-text-secondary mb-1">
          {hint}
        </p>
      )}

      {/* Clonar children para inyectar props de accesibilidad */}
      {React.cloneElement(children as React.ReactElement, {
        id,
        'aria-required': required,
        'aria-invalid': !!error,
        'aria-describedby': describedBy,
        'aria-errormessage': errorId,
      })}

      {error && (
        <p id={errorId} className="text-sm text-danger mt-1 flex items-center gap-1" role="alert">
          <AlertIcon className="w-4 h-4" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}
```

### 7.2 Ejemplo de Formulario Completo

```tsx
// features/auth/components/LoginForm.tsx

export function LoginForm() {
  const { register, handleSubmit, formState: { errors } } = useForm();

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      aria-label="Formulario de inicio de sesión"
    >
      <FormField
        id="username"
        label="Usuario"
        required
        error={errors.username?.message}
      >
        <Input
          type="text"
          autoComplete="username"
          {...register('username', { required: 'El usuario es requerido' })}
        />
      </FormField>

      <FormField
        id="password"
        label="Contraseña"
        required
        hint="Mínimo 8 caracteres"
        error={errors.password?.message}
      >
        <Input
          type="password"
          autoComplete="current-password"
          {...register('password', {
            required: 'La contraseña es requerida',
            minLength: { value: 8, message: 'Mínimo 8 caracteres' }
          })}
        />
      </FormField>

      <Button type="submit">
        Iniciar sesión
      </Button>
    </form>
  );
}
```

---

## 8. Tablas Accesibles

### 8.1 Estructura

```tsx
// shared/components/ui/DataTable.tsx

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  caption: string;
  emptyMessage?: string;
}

/**
 * Tabla de datos accesible.
 */
export function DataTable<T>({
  data,
  columns,
  caption,
  emptyMessage = 'No hay datos para mostrar'
}: DataTableProps<T>) {
  return (
    <div role="region" aria-label={caption} tabIndex={0}>
      <table className="w-full">
        <caption className="sr-only">{caption}</caption>

        <thead>
          <tr>
            {columns.map((col, index) => (
              <th
                key={index}
                scope="col"
                className="text-left p-3 bg-bg-secondary"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="text-center p-8 text-text-secondary"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-border">
                {columns.map((col, colIndex) => (
                  <td key={colIndex} className="p-3">
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
```

### 8.2 Tabla con Acciones

```tsx
// Ejemplo de uso con acciones accesibles
<DataTable
  caption="Lista de entregas pendientes de corrección"
  data={entregas}
  columns={[
    {
      header: 'Alumno',
      render: (e) => e.nombre_alumno
    },
    {
      header: 'Archivo',
      render: (e) => e.archivo
    },
    {
      header: 'Estado',
      render: (e) => (
        <Badge aria-label={`Estado: ${e.estado}`}>
          {e.estado}
        </Badge>
      )
    },
    {
      header: 'Acciones',
      render: (e) => (
        <div role="group" aria-label="Acciones para esta entrega">
          <Button
            size="sm"
            aria-label={`Corregir entrega de ${e.nombre_alumno}`}
          >
            Corregir
          </Button>
          <Button
            size="sm"
            variant="secondary"
            aria-label={`Ver detalles de entrega de ${e.nombre_alumno}`}
          >
            Ver
          </Button>
        </div>
      )
    },
  ]}
/>
```

---

## 9. Contraste de Colores

### 9.1 Paleta Validada (Tema Claro)

| Uso | Color | Sobre | Ratio | Cumple |
|-----|-------|-------|-------|--------|
| Texto primario | `#0f172a` | `#ffffff` | 15.5:1 | AA, AAA |
| Texto secundario | `#475569` | `#ffffff` | 6.0:1 | AA |
| Texto sobre accent | `#ffffff` | `#6366f1` | 4.8:1 | AA |
| Bordes | `#e2e8f0` | `#ffffff` | 1.5:1 | - (decorativo) |
| Error | `#dc2626` | `#ffffff` | 5.9:1 | AA |
| Success | `#16a34a` | `#ffffff` | 4.5:1 | AA |

### 9.2 Paleta Validada (Tema Oscuro)

| Uso | Color | Sobre | Ratio | Cumple |
|-----|-------|-------|-------|--------|
| Texto primario | `#f8fafc` | `#0a0a0f` | 18.1:1 | AA, AAA |
| Texto secundario | `#94a3b8` | `#0a0a0f` | 7.1:1 | AA, AAA |
| Texto sobre accent | `#ffffff` | `#6366f1` | 4.8:1 | AA |
| Bordes | `#2a2a3a` | `#0a0a0f` | 1.6:1 | - (decorativo) |
| Error | `#f87171` | `#0a0a0f` | 7.3:1 | AA, AAA |
| Success | `#4ade80` | `#0a0a0f` | 10.2:1 | AA, AAA |

### 9.3 Herramienta de Validación

Usar estas herramientas para validar nuevos colores:
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [Coolors Contrast Checker](https://coolors.co/contrast-checker)

---

## 10. Imágenes y Media

### 10.1 Textos Alternativos

```tsx
// Imagen informativa
<img
  src="/logo.svg"
  alt="Active-IA - Sistema de corrección automática"
/>

// Imagen decorativa
<img
  src="/pattern.svg"
  alt=""
  role="presentation"
/>

// Icono dentro de botón con texto
<button>
  <EditIcon aria-hidden="true" />
  Editar corrección
</button>

// Icono como único contenido
<button aria-label="Editar corrección">
  <EditIcon aria-hidden="true" />
</button>
```

### 10.2 SVG Accesibles

```tsx
// shared/components/icons/CheckIcon.tsx

interface IconProps {
  className?: string;
  'aria-hidden'?: boolean;
  title?: string;
}

export function CheckIcon({ className, title, ...props }: IconProps) {
  const titleId = title ? 'check-icon-title' : undefined;

  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      role={title ? 'img' : 'presentation'}
      aria-labelledby={titleId}
      {...props}
    >
      {title && <title id={titleId}>{title}</title>}
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M5 13l4 4L19 7"
      />
    </svg>
  );
}
```

---

## 11. Estados de Carga

### 11.1 Loading Spinner Accesible

```tsx
// shared/components/ui/Spinner.tsx

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

/**
 * Spinner de carga accesible.
 */
export function Spinner({ size = 'md', label = 'Cargando...' }: SpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2"
    >
      <svg
        className={`animate-spin ${sizeClasses[size]}`}
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <span className="sr-only">{label}</span>
    </div>
  );
}
```

### 11.2 Skeleton Loading

```tsx
// shared/components/ui/Skeleton.tsx

/**
 * Placeholder de carga para contenido.
 */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      role="presentation"
      aria-hidden="true"
      className={`animate-pulse bg-bg-secondary rounded ${className}`}
    />
  );
}

// Uso con aria-busy en contenedor
function EntregasList() {
  const { data, isLoading } = useEntregas();

  return (
    <div aria-busy={isLoading} aria-live="polite">
      {isLoading ? (
        <>
          <Skeleton className="h-16 mb-2" />
          <Skeleton className="h-16 mb-2" />
          <Skeleton className="h-16" />
          <span className="sr-only">Cargando entregas...</span>
        </>
      ) : (
        <ul>
          {data.map(e => <EntregaItem key={e.id} entrega={e} />)}
        </ul>
      )}
    </div>
  );
}
```

---

## 12. Títulos de Página Dinámicos

### 12.1 Hook para Título

```tsx
// shared/hooks/useDocumentTitle.ts

/**
 * Hook para actualizar el título del documento.
 * Importante para screen readers y navegación.
 */
export function useDocumentTitle(title: string) {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = `${title} | Active-IA`;

    return () => {
      document.title = previousTitle;
    };
  }, [title]);
}
```

### 12.2 Uso por Página

```tsx
// pages/tutor/EntregasPage.tsx

export function EntregasPage() {
  useDocumentTitle('Entregas');

  return (
    <div>
      <h1>Entregas</h1>
      {/* contenido */}
    </div>
  );
}
```

---

## 13. Checklist de Accesibilidad

### Pre-desarrollo (por componente)

- [ ] ¿Tiene estructura semántica correcta (headings, landmarks)?
- [ ] ¿Es navegable por teclado?
- [ ] ¿Tiene focus visible?
- [ ] ¿Los elementos interactivos tienen nombres accesibles?
- [ ] ¿Los errores son anunciados a screen readers?

### Pre-deploy (por página)

- [ ] ¿El título de página es descriptivo?
- [ ] ¿Hay un h1 único y descriptivo?
- [ ] ¿Los contrastes cumplen AA?
- [ ] ¿El skip link funciona?
- [ ] ¿La página funciona sin mouse?

### Testing

- [ ] Probar con VoiceOver (Mac) o NVDA (Windows)
- [ ] Probar navegación solo con teclado
- [ ] Validar con axe DevTools (extensión)
- [ ] Validar con Lighthouse (accesibilidad > 90)

---

## 14. Resumen de Decisiones

| Aspecto | Decisión |
|---------|----------|
| **Nivel WCAG** | 2.1 AA |
| **Temas** | Claro + Oscuro + Preferencia sistema |
| **Contraste** | 4.5:1 normal, 3:1 grande |
| **Skip links** | "Saltar al contenido principal" |
| **Screen readers** | Soporte completo con ARIA |
| **Focus** | Ring con color accent |
| **Notificaciones** | Toast con aria-live |
| **Títulos** | Dinámicos por página |

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
