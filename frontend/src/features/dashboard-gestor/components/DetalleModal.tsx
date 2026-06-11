import { Modal, Spinner } from '@/shared/components/ui';
import { ESTADO_LABEL } from '../constants';
import { useDetalle } from '../hooks/useDashboardGestor';
import type { AlumnoDetalle, EstadoAvance } from '../types';

interface DetalleModalProps {
  cuatrimestreId: number | null;
  materiaId: number | null;
  estado: EstadoAvance;
  onClose: () => void;
}

/** Modal con la lista de alumnos de un estado (al clickear una porción del gráfico). */
export const DetalleModal = ({ cuatrimestreId, materiaId, estado, onClose }: DetalleModalProps) => {
  const { data: alumnos, isLoading } = useDetalle(cuatrimestreId, estado, materiaId);

  const renderLeFalta = (a: AlumnoDetalle) =>
    a.le_falta ? (
      <>
        {a.le_falta}
        {a.actividad_actual_desaprobada && (
          <span className="ml-1 rounded-full bg-destructive/15 px-2 py-0.5 text-xs text-destructive">
            desaprobada
          </span>
        )}
      </>
    ) : (
      <span className="text-emerald-600 dark:text-emerald-500">al día</span>
    );

  return (
    <Modal isOpen onClose={onClose} title={`Alumnos — ${ESTADO_LABEL[estado]}`} size="2xl">
      {isLoading ? (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Spinner /> Cargando alumnos…
        </div>
      ) : !alumnos || alumnos.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No hay alumnos en este estado.
        </p>
      ) : (
        <div className="max-h-[70vh] overflow-auto scroll-momentum sm:max-h-[60vh]">
          {/* Desktop (sm:): tabla ancha alumno × estado/examen (look intacto) */}
          <table className="hidden w-full text-sm sm:table">
            <thead className="sticky top-0 bg-card text-xs uppercase tracking-wider text-muted-foreground">
              <tr className="border-b border-border">
                <th className="px-3 py-2 text-left">Alumno</th>
                <th className="px-3 py-2 text-left">Email</th>
                <th className="px-3 py-2 text-left">Comisión</th>
                <th className="px-3 py-2 text-left">Alcanzó</th>
                <th className="px-3 py-2 text-left">Le falta</th>
                <th className="px-3 py-2 text-left">Exámenes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {alumnos.map((a) => (
                <tr key={a.moodle_user_id}>
                  <td className="px-3 py-2 text-foreground">
                    {a.apellido}, {a.nombre}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{a.email ?? '—'}</td>
                  <td className="px-3 py-2 text-muted-foreground">{a.comision ?? '—'}</td>
                  <td className="px-3 py-2 text-foreground">
                    {a.unidad_alcanzada != null
                      ? `${a.etiqueta_unidad} ${a.unidad_alcanzada}`
                      : '—'}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{renderLeFalta(a)}</td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {a.examenes || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Mobile (<sm): cards apiladas con pares label/valor */}
          <div className="flex flex-col gap-3 sm:hidden">
            {alumnos.map((a) => (
              <div
                key={a.moodle_user_id}
                className="rounded-lg border border-border bg-card p-4"
              >
                <p className="font-medium text-foreground">
                  {a.apellido}, {a.nombre}
                </p>
                <dl className="mt-2 flex flex-col text-sm">
                  <div className="flex justify-between gap-3 border-b border-border/50 py-1.5">
                    <dt className="shrink-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Email
                    </dt>
                    <dd className="min-w-0 break-all text-right text-muted-foreground">
                      {a.email ?? '—'}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3 border-b border-border/50 py-1.5">
                    <dt className="shrink-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Comisión
                    </dt>
                    <dd className="min-w-0 break-words text-right text-muted-foreground">
                      {a.comision ?? '—'}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3 border-b border-border/50 py-1.5">
                    <dt className="shrink-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Alcanzó
                    </dt>
                    <dd className="min-w-0 break-words text-right text-foreground">
                      {a.unidad_alcanzada != null
                        ? `${a.etiqueta_unidad} ${a.unidad_alcanzada}`
                        : '—'}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3 border-b border-border/50 py-1.5">
                    <dt className="shrink-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Le falta
                    </dt>
                    <dd className="min-w-0 break-words text-right text-muted-foreground">
                      {renderLeFalta(a)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3 py-1.5">
                    <dt className="shrink-0 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Exámenes
                    </dt>
                    <dd className="min-w-0 break-words text-right text-muted-foreground">
                      {a.examenes || '—'}
                    </dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        </div>
      )}
    </Modal>
  );
};
