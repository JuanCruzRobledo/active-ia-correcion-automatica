/**
 * UniversidadSelector — selector de universidad accesible desde el layout.
 *
 * Poblado con `GET /universidades/mias`. Para un superadmin incluye además
 * "Todas las universidades" (modo global, D6). Sin alternativas cuando el
 * usuario tiene una sola membresía y no es superadmin.
 *
 * Ref: openspec/changes/multi-tenant-frontend-workspace/design.md (D1, D4, D6)
 */
import { Building2, ChevronDown, Globe } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Dropdown } from '@/shared/components/ui/Dropdown';
import type { DropdownItem } from '@/shared/components/ui/Dropdown';
import { useUniversidadesMias } from '@/features/universidades/hooks';
import { useTenant } from '@/shared/context/useTenant';

export const UniversidadSelector = () => {
  const { data: universidades } = useUniversidadesMias();
  const { universidadActivaId, esSuperadmin, cambiarUniversidad } = useTenant();
  const navigate = useNavigate();

  if (!universidades) {
    return null;
  }

  const activa = universidades.find((u) => u.id === universidadActivaId);
  const nombreActivo = activa?.nombre ?? (esSuperadmin ? 'Todas las universidades' : 'Sin universidad');

  // Sin alternativas cuando hay una sola membresía y no es superadmin: no
  // tiene sentido ofrecer un selector con una única opción.
  const ofreceAlternativas = esSuperadmin || universidades.length > 1;

  const handleElegir = async (universidadId: number | null) => {
    try {
      await cambiarUniversidad(universidadId);
      navigate('/dashboard');
    } catch {
      toast.error('No se pudo cambiar de universidad. Intentá de nuevo.');
    }
  };

  if (!ofreceAlternativas) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-sidebar-foreground">
        <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="truncate">{nombreActivo}</span>
      </div>
    );
  }

  const items: DropdownItem[] = [
    ...universidades.map((u) => ({
      label: u.id === universidadActivaId ? `✓ ${u.nombre}` : u.nombre,
      onClick: () => handleElegir(u.id),
    })),
    ...(esSuperadmin
      ? [
          {
            label:
              universidadActivaId === null
                ? '✓ Todas las universidades'
                : 'Todas las universidades',
            onClick: () => handleElegir(null),
          },
        ]
      : []),
  ];

  return (
    <Dropdown
      align="left"
      items={items}
      trigger={
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent"
        >
          {universidadActivaId === null ? (
            <Globe className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
          <span className="flex-1 truncate text-left">{nombreActivo}</span>
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
      }
    />
  );
};
