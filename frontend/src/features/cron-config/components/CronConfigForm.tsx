import { useState } from 'react';
import { Button, Checkbox, Input, Select } from '@/shared/components/ui';
import type { SelectOption } from '@/shared/components/ui';
import type { UsuarioListItem } from '@/features/usuarios/types';
import { useSetCronConfig } from '../hooks/useCronConfig';
import type { CronConfig } from '../types';

interface CronConfigFormProps {
  config: CronConfig;
  usuarios: UsuarioListItem[];
}

/**
 * Form de config del cron: usuario (credenciales Moodle) + hora + activo.
 * Se monta con la config cargada → inicializa estado directo (sin useEffect).
 */
export const CronConfigForm = ({ config, usuarios }: CronConfigFormProps) => {
  const [usuarioId, setUsuarioId] = useState<string>(
    config.usuario_id != null ? String(config.usuario_id) : ''
  );
  const [hora, setHora] = useState<string>(String(config.hora));
  const [minuto, setMinuto] = useState<string>(String(config.minuto));
  const [activo, setActivo] = useState<boolean>(config.activo);

  const setConfig = useSetCronConfig();

  const usuarioOptions: SelectOption[] = [
    { value: '', label: 'Sin asignar' },
    ...usuarios.map((u) => ({
      value: String(u.id),
      label: `${u.nombre} (@${u.username}) — ${u.rol}`,
    })),
  ];

  const horaOptions: SelectOption[] = Array.from({ length: 24 }, (_, h) => ({
    value: String(h),
    label: `${String(h).padStart(2, '0')}:00`,
  }));

  const handleGuardar = () => {
    setConfig.mutate({
      usuario_id: usuarioId ? Number(usuarioId) : null,
      hora: Number(hora),
      minuto: Number(minuto),
      activo,
    });
  };

  return (
    <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
      <h2 className="text-lg font-semibold text-foreground">Programación del cron</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        El cron corre 1×/día (hora de Argentina) y usa las credenciales de Moodle del
        usuario elegido. Activalo solo cuando todo esté configurado.
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
