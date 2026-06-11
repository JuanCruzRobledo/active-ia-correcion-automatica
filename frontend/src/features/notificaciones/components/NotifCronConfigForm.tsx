import { useState } from 'react';
import { Button, Checkbox, Input, Select } from '@/shared/components/ui';
import type { SelectOption } from '@/shared/components/ui';
import type { UsuarioListItem } from '@/features/usuarios/types';
import { useSetNotifConfig } from '../hooks/useNotificaciones';
import type { NotifCronConfig } from '../types';

interface Props {
  config: NotifCronConfig;
  usuarios: UsuarioListItem[];
}

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

/**
 * Form de config del cron semanal de notificaciones: usuario de servicio (credenciales
 * Moodle) + día + hora + remitente + activo. Se monta con la config cargada (sin useEffect).
 */
export const NotifCronConfigForm = ({ config, usuarios }: Props) => {
  const [usuarioId, setUsuarioId] = useState(
    config.usuario_id != null ? String(config.usuario_id) : ''
  );
  const [diaSemana, setDiaSemana] = useState(String(config.dia_semana));
  const [hora, setHora] = useState(String(config.hora));
  const [minuto, setMinuto] = useState(String(config.minuto));
  const [remitente, setRemitente] = useState(config.remitente ?? '');
  const [activo, setActivo] = useState(config.activo);

  const setConfig = useSetNotifConfig();

  const usuarioOptions: SelectOption[] = [
    { value: '', label: 'Sin asignar' },
    ...usuarios.map((u) => ({
      value: String(u.id),
      label: `${u.nombre} (@${u.username}) — ${u.rol}`,
    })),
  ];
  const diaOptions: SelectOption[] = DIAS.map((d, i) => ({ value: String(i), label: d }));
  const horaOptions: SelectOption[] = Array.from({ length: 24 }, (_, h) => ({
    value: String(h),
    label: `${String(h).padStart(2, '0')}:00`,
  }));

  const handleGuardar = () => {
    setConfig.mutate({
      usuario_id: usuarioId ? Number(usuarioId) : null,
      dia_semana: Number(diaSemana),
      hora: Number(hora),
      minuto: Number(minuto),
      remitente: remitente.trim() || null,
      activo,
    });
  };

  return (
    <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
      <h2 className="text-lg font-semibold text-foreground">Programación del envío semanal</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Corre 1×/semana (hora de Argentina). Refresca los snapshots con las credenciales de
        Moodle del usuario elegido y luego envía los 3 tipos de email en cadena.
      </p>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <div className="md:col-span-3">
          <Select
            label="Usuario (credenciales de Moodle)"
            options={usuarioOptions}
            value={usuarioId}
            onChange={(e) => setUsuarioId(e.target.value)}
          />
        </div>
        <Select
          label="Día"
          options={diaOptions}
          value={diaSemana}
          onChange={(e) => setDiaSemana(e.target.value)}
        />
        <Select
          label="Hora (Argentina)"
          options={horaOptions}
          value={hora}
          onChange={(e) => setHora(e.target.value)}
        />
        <Input
          label="Minuto"
          type="number"
          inputMode="numeric"
          pattern="[0-9]*"
          min={0}
          max={59}
          value={minuto}
          onChange={(e) => setMinuto(e.target.value)}
        />
        <div className="md:col-span-2">
          <Input
            label="Remitente (opcional)"
            placeholder="onboarding@resend.dev (sandbox) o notificaciones@active-ia.com"
            value={remitente}
            onChange={(e) => setRemitente(e.target.value)}
            maxLength={150}
          />
        </div>
        <div className="flex items-end pb-2">
          <Checkbox
            label="Cron activo"
            checked={activo}
            onChange={(e) => setActivo(e.target.checked)}
          />
        </div>
      </div>

      <div className="mt-4 flex justify-end">
        <Button onClick={handleGuardar} isLoading={setConfig.isPending} className="w-full sm:w-auto">
          Guardar
        </Button>
      </div>
    </div>
  );
};
