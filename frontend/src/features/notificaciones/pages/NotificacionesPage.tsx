import { useState } from 'react';
import toast from 'react-hot-toast';
import { Eye, FileSpreadsheet, FileText, Play, Send } from 'lucide-react';
import {
  Badge,
  Button,
  Checkbox,
  HelpButton,
  Input,
  LoadingState,
} from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { useUsuarios } from '@/features/usuarios/hooks';
import { NotifCronConfigForm } from '../components/NotifCronConfigForm';
import {
  useDispararCorrida,
  useEnviarPrueba,
  useHistorialNotif,
  useNotifConfig,
} from '../hooks/useNotificaciones';
import { abrirPreview } from '../services/notificaciones.service';
import type { CorridaResumen, EstadoEnvio } from '../types';
import { formatFechaHoraArg } from '@/shared/utils/fecha';

const fmtFecha = (iso: string | null) => formatFechaHoraArg(iso);

const TIPO_LABEL: Record<string, string> = {
  ALUMNO: 'Alumno',
  TUTOR_ACADEMICO: 'Tutor académico',
  TUTOR_NEXO: 'Tutor nexo',
};

export const NotificacionesPage = () => {
  const { data: config, isLoading: loadingConfig } = useNotifConfig();
  const { data: usuariosData, isLoading: loadingUsuarios } = useUsuarios({
    rol: 'TODOS',
    activo: true,
    search: '',
    page: 1,
    per_page: 100,
  });
  const { data: historial } = useHistorialNotif();

  const disparar = useDispararCorrida();
  const enviarPrueba = useEnviarPrueba();

  const [emailPrueba, setEmailPrueba] = useState('');
  const [refrescar, setRefrescar] = useState(false);
  // Fase de prueba: por defecto NO se manda a alumnos y solo a las comisiones objetivo.
  const [incluirAlumnos, setIncluirAlumnos] = useState(false);
  // Tutores nexo: por defecto SÍ se notifican (comportamiento actual); se puede desmarcar.
  const [incluirNexos, setIncluirNexos] = useState(true);
  const [comisionesText, setComisionesText] = useState('7:1, 7:2, 7:3, 9:7');
  const [resumen, setResumen] = useState<CorridaResumen | null>(null);

  const handleDisparar = async () => {
    const comisiones = comisionesText
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean);
    const r = await disparar.mutateAsync({ refrescar, incluirAlumnos, incluirNexos, comisiones });
    setResumen(r);
  };

  const handlePreview = (tipo: 'alumno' | 'tutor' | 'nexo') => {
    abrirPreview(tipo).catch((e) =>
      toast.error(e instanceof Error ? e.message : 'No se pudo abrir la vista previa')
    );
  };

  if (loadingConfig || loadingUsuarios) {
    return <LoadingState title="Cargando notificaciones…" />;
  }

  const estadoVariant = (estado: EstadoEnvio) => (estado === 'ENVIADO' ? 'success' : 'default');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-foreground">Notificaciones por email</h1>
          <HelpButton title="Ayuda — Notificaciones" content={helpContent.notificaciones} />
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Envío semanal automático de actividades faltantes a alumnos, tutores académicos y
          tutores nexo.
        </p>
      </div>

      {/* Config del cron */}
      {config && (
        <NotifCronConfigForm config={config} usuarios={usuariosData?.items ?? []} />
      )}

      {/* Probar y previsualizar */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-foreground">Probar y previsualizar</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Enviá un email de prueba a una casilla y mirá cómo se ven los formatos sin mandar nada.
        </p>

        {/* Enviar prueba */}
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Input
              label="Email de prueba"
              type="email"
              placeholder="tu-email@ejemplo.com"
              value={emailPrueba}
              onChange={(e) => setEmailPrueba(e.target.value)}
            />
          </div>
          <Button
            onClick={() => enviarPrueba.mutate(emailPrueba.trim())}
            isLoading={enviarPrueba.isPending}
            disabled={!emailPrueba.trim()}
          >
            <Send className="h-4 w-4" /> Enviar prueba
          </Button>
        </div>

        {/* Preview */}
        <div className="mt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Vista previa (no envía)
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => handlePreview('alumno')}>
              <Eye className="h-4 w-4" /> HTML alumno
            </Button>
            <Button variant="secondary" onClick={() => handlePreview('tutor')}>
              <FileText className="h-4 w-4" /> PDF tutor
            </Button>
            <Button variant="secondary" onClick={() => handlePreview('nexo')}>
              <FileSpreadsheet className="h-4 w-4" /> Excel nexo
            </Button>
          </div>
        </div>
      </div>

      {/* Disparar corrida manual */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-foreground">Disparar ahora (QA)</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Corre la cadena a mano. Sin refrescar, usa los snapshots actuales (rápido); con
          refrescar, los regenera primero (lento, pega a Moodle).
        </p>

        {/* Fase de prueba: controles de a quién se envía */}
        <div className="mt-4 rounded-lg border border-warning/30 bg-warning/10 p-4">
          <p className="text-sm font-medium text-foreground">Fase de prueba — destinatarios</p>
          <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-foreground">
            <Checkbox
              checked={incluirAlumnos}
              onChange={(e) => setIncluirAlumnos(e.target.checked)}
            />
            Incluir alumnos (⚠️ desmarcado = NO se manda a alumnos)
          </label>
          <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-foreground">
            <Checkbox
              checked={incluirNexos}
              onChange={(e) => setIncluirNexos(e.target.checked)}
            />
            Notificar a los tutores nexo (Excel por regional)
          </label>
          <div className="mt-3">
            <Input
              label="Comisiones objetivo de tutores (vacío = todas)"
              placeholder="7:1, 7:2, 7:3, 9:7"
              value={comisionesText}
              onChange={(e) => setComisionesText(e.target.value)}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Formato <code>materia_id:numero</code> separadas por coma. Ej: Prog1 (id 7)
              comisiones 1, 2 y 3 + Prog3 (id 9) comisión 7 → <code>7:1, 7:2, 7:3, 9:7</code>.
              Los tutores nexo se envían siempre.
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
            <Checkbox checked={refrescar} onChange={(e) => setRefrescar(e.target.checked)} />
            Refrescar snapshots antes de enviar
          </label>
          <Button onClick={handleDisparar} isLoading={disparar.isPending}>
            <Play className="h-4 w-4" /> Disparar corrida
          </Button>
        </div>
        {resumen && !disparar.isPending && (
          <div className="mt-4 rounded-lg border border-success/30 bg-success/10 p-4 text-sm text-foreground">
            ✅ Corrida <strong>{resumen.tanda_id.slice(0, 8)}</strong>:{' '}
            {resumen.alumnos} alumnos · {resumen.tutores} tutores · {resumen.nexos} nexos.
          </div>
        )}
      </div>

      {/* Historial */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-foreground">Historial de envíos</h2>
        {!historial || historial.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">Todavía no hay envíos registrados.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">Fecha</th>
                  <th className="px-4 py-2 text-left">Tipo</th>
                  <th className="px-4 py-2 text-left">Destinatario</th>
                  <th className="px-4 py-2 text-left">Estado</th>
                  <th className="px-4 py-2 text-left">Detalle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {historial.map((log) => (
                  <tr key={log.id} className="transition-colors hover:bg-muted/30">
                    <td className="px-4 py-2 text-muted-foreground">{fmtFecha(log.created_at)}</td>
                    <td className="px-4 py-2 text-foreground">{TIPO_LABEL[log.tipo] ?? log.tipo}</td>
                    <td className="px-4 py-2 text-muted-foreground">{log.destinatario_email}</td>
                    <td className="px-4 py-2">
                      <Badge variant={estadoVariant(log.estado)}>{log.estado}</Badge>
                    </td>
                    <td className="px-4 py-2 text-xs text-destructive">{log.error ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
