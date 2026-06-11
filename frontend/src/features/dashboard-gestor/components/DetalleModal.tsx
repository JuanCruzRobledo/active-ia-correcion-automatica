import { Modal, Spinner } from '@/shared/components/ui';
import { ESTADO_LABEL } from '../constants';
import { useDetalle } from '../hooks/useDashboardGestor';
import type { EstadoAvance } from '../types';

interface DetalleModalProps {
  cuatrimestreId: number | null;
  materiaId: number | null;
  estado: EstadoAvance;
  onClose: () => void;
}

/** Modal con la lista de alumnos de un estado (al clickear una porción del gráfico). */
export const DetalleModal = ({ cuatrimestreId, materiaId, estado, onClose }: DetalleModalProps) => {
  const { data: alumnos, isLoading } = useDetalle(cuatrimestreId, estado, materiaId);

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
        <div className="max-h-[60vh] overflow-auto">
          <table className="w-full text-sm">
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
                  <td className="px-3 py-2 text-muted-foreground">
                    {a.le_falta ? (
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
                    )}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {a.examenes || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
};
