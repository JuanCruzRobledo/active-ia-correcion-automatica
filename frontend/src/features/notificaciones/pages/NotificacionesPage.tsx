import { useState } from 'react';
import toast from 'react-hot-toast';
import { Eye, FileSpreadsheet, FileText, Play, Send } from 'lucide-react';
import {
  Alert,
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
  const { data: config, isLoading: loadingConfig, isError: errorConfig } = useNotifConfig();
  const {
    data: usuariosData,
    isLoading: loadingUsuarios,
    isError: errorUsuarios,
  } = useUsuarios({
    rol: 'TODOS',
    activo: true,
    search: '',
    page: 1,
    per_page: 100,
  });
  const { data: historial, isError: errorHistorial } = useHistorialNotif();

  const disparar = useDispararCorrida();
  const enviarPrueba = useEnviarPrueba();

  const [emailPrueba, setEmailPrueba] = useState('');
  const [refrescar, setRefrescar] = useState(false);
  // Fase de prueba: por defecto NO se manda a alumnos y solo a las comisiones objetivo.
  const [incluirAlumnos, setIncluirAlumnos] = useState(false);
  // Tutores nexo: por defecto SÍ se notifican (comportamiento actual); se puede desmarcar.
  const [incluirNexos, setIncluirNexos] = useState(true);
  // UI-009: default vacío (= todas las comisiones). El formato esperado va en el
  // placeholder del Input, sin quemar identificadores de producción en la UI.
  const [comisionesText, setComisionesText] = useState('');
  const [resumen, setResumen] = useState<CorridaResumen | null>(null);

  const handleDisparar = async () => {
    const comisiones = comisionesText
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean);
    try {
      const r = await disparar.mutateAsync({ refrescar, incluirAlumnos, incluirNexos, comisiones });
      setResumen(r);
    } catch {
      // El onError del hook ya muestra el toast; acá sólo evitamos la unhandled rejection.
    }
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
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-foreground sm:text-3xl">Notificaciones por email</h1>
          <HelpButton title="Ayuda — Notificaciones" content={helpContent.notificaciones} />
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Envío semanal automático de actividades faltantes a alumnos, tutores académicos y
          tutores nexo.
        </p>
      </div>

      {/* UI-004: si fallan las queries de config/usuarios, avisamos en vez de
          mostrar la sección vacía (que se confundiría con "no hay config"). */}
      {(errorConfig || errorUsuarios) && (
        <Alert variant="destructive" title="No se pudo cargar la configuración">
          <p>
            Hubo un problema al consultar el servidor. Revisá tu conexión e intentá recargar la
            página.
          </p>
        </Alert>
      )}

      {/* Config del cron */}
      {config && (
        <NotifCronConfigForm config={config} usuarios={usuariosData?.items ?? []} />
      )}

      {/* Probar y previsualizar */}
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
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
              inputMode="email"
              autoCapitalize="none"
              autoComplete="email"
              autoCorrect="off"
              spellCheck={false}
              placeholder="tu-email@ejemplo.com"
              value={emailPrueba}
              onChange={(e) => setEmailPrueba(e.target.value)}
            />
          </div>
          <Button
            onClick={() => enviarPrueba.mutate(emailPrueba.trim())}
            isLoading={enviarPrueba.isPending}
            disabled={!emailPrueba.trim()}
            className="w-full sm:w-auto"
          >
            <Send className="h-4 w-4" /> Enviar prueba
          </Button>
        </div>

        {/* Preview */}
        <div className="mt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Vista previa (no envía)
          </p>
          <div className="grid grid-cols-1 gap-2 sm:flex sm:flex-wrap">
            <Button
              variant="secondary"
              onClick={() => handlePreview('alumno')}
              className="min-h-11 w-full sm:w-auto"
            >
              <Eye className="h-4 w-4" /> HTML alumno
            </Button>
            <Button
              variant="secondary"
              onClick={() => handlePreview('tutor')}
              className="min-h-11 w-full sm:w-auto"
            >
              <FileText className="h-4 w-4" /> PDF tutor
            </Button>
            <Button
              variant="secondary"
              onClick={() => handlePreview('nexo')}
              className="min-h-11 w-full sm:w-auto"
            >
              <FileSpreadsheet className="h-4 w-4" /> Excel nexo
            </Button>
          </div>
        </div>
      </div>

      {/* Disparar corrida manual */}
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <h2 className="text-lg font-semibold text-foreground">Disparar ahora (QA)</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Corre la cadena a mano. Sin refrescar, usa los snapshots actuales (rápido); con
          refrescar, los regenera primero (lento, pega a Moodle).
        </p>

        {/* Fase de prueba: controles de a quién se envía */}
        <div className="mt-4 rounded-lg border border-warning/30 bg-warning/10 p-4">
          <p className="text-sm font-medium text-foreground">Fase de prueba — destinatarios</p>
          {/* El Checkbox ya envuelve input+label en un <label> con hit-area >=44px
              e items-start, ideal para estos labels largos que pueden envolver. */}
          <Checkbox
            label="Incluir alumnos (⚠️ desmarcado = NO se manda a alumnos)"
            checked={incluirAlumnos}
            onChange={(e) => setIncluirAlumnos(e.target.checked)}
          />
          <Checkbox
            label="Notificar a los tutores nexo (Excel por regional)"
            checked={incluirNexos}
            onChange={(e) => setIncluirNexos(e.target.checked)}
          />
          <div className="mt-3">
            <Input
              label="Comisiones objetivo de tutores (vacío = todas)"
              placeholder="7:1, 7:2, 7:3, 9:7"
              value={comisionesText}
              onChange={(e) => setComisionesText(e.target.value)}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Formato <code className="break-words">materia_id:numero</code> separadas por coma. Ej:
              Prog1 (id 7) comisiones 1, 2 y 3 + Prog3 (id 9) comisión 7 →{' '}
              <code className="break-words">7:1, 7:2, 7:3, 9:7</code>. Los tutores nexo se envían
              siempre.
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Checkbox
            label="Refrescar snapshots antes de enviar"
            checked={refrescar}
            onChange={(e) => setRefrescar(e.target.checked)}
          />
          <Button
            onClick={handleDisparar}
            isLoading={disparar.isPending}
            className="w-full sm:w-auto"
          >
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
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <h2 className="text-lg font-semibold text-foreground">Historial de envíos</h2>
        {errorHistorial ? (
          <p className="mt-4 text-sm text-destructive">
            No se pudo cargar el historial de envíos. Reintentá recargando la página.
          </p>
        ) : !historial || historial.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">Todavía no hay envíos registrados.</p>
        ) : (
          <>
            {/* Desktop (sm:+): tabla clasica */}
            <div className="mt-4 hidden overflow-x-auto sm:block">
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
                      <td className="px-4 py-2 text-muted-foreground break-all">
                        {log.destinatario_email}
                      </td>
                      <td className="px-4 py-2">
                        <Badge variant={estadoVariant(log.estado)}>{log.estado}</Badge>
                      </td>
                      <td className="px-4 py-2 text-xs text-destructive">{log.error ?? ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile (<sm): card-list apilada */}
            <div className="mt-4 flex flex-col gap-3 sm:hidden">
              {historial.map((log) => (
                <div
                  key={log.id}
                  className="rounded-lg border border-border bg-background/50 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="text-sm font-medium text-foreground">
                      {TIPO_LABEL[log.tipo] ?? log.tipo}
                    </span>
                    <Badge variant={estadoVariant(log.estado)}>{log.estado}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{fmtFecha(log.created_at)}</div>
                  <div className="mt-2 text-sm text-muted-foreground break-all">
                    {log.destinatario_email}
                  </div>
                  {log.error && (
                    <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive break-words">
                      {log.error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
