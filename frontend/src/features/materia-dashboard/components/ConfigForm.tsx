import { useState } from 'react';
import { Button, Input, Select } from '@/shared/components/ui';
import type { SelectOption } from '@/shared/components/ui';
import type { Cohorte } from '@/features/cohortes/types';
import { useSetDashboardConfig } from '../hooks/useMateriaDashboard';
import type { MateriaDashboardConfigResponse, MoodleSeccionItem } from '../types';

interface ConfigFormProps {
  materiaId: number;
  config: MateriaDashboardConfigResponse;
  cohortes: Cohorte[];
  /** Secciones de Moodle ya detectadas (para poblar el selector de tope). */
  secciones: MoodleSeccionItem[] | null;
}

/**
 * Form de vinculación (cohorte→cuatrimestre), unidad actual y tope de la materia.
 * Se monta con la config ya cargada, así inicializa su estado directo (sin useEffect).
 */
export const ConfigForm = ({ materiaId, config, cohortes, secciones }: ConfigFormProps) => {
  const cohorteInicial = cohortes.find((c) =>
    c.cuatrimestres.some((q) => q.id === config.cuatrimestre_id)
  );

  const [cohorteId, setCohorteId] = useState<string>(
    cohorteInicial ? String(cohorteInicial.id) : ''
  );
  const [cuatrimestreId, setCuatrimestreId] = useState<string>(
    config.cuatrimestre_id ? String(config.cuatrimestre_id) : ''
  );
  const [unidadActual, setUnidadActual] = useState<string>(
    config.unidad_actual != null ? String(config.unidad_actual) : ''
  );
  const [topeId, setTopeId] = useState<string>(
    config.moodle_section_fin_id != null ? String(config.moodle_section_fin_id) : ''
  );
  const [etiqueta, setEtiqueta] = useState<string>(config.etiqueta_unidad || 'Unidad');
  const [riesgoMedio, setRiesgoMedio] = useState<string>(
    config.riesgo_medio_desde != null ? String(config.riesgo_medio_desde) : '1'
  );
  const [riesgoAlto, setRiesgoAlto] = useState<string>(
    config.riesgo_alto_desde != null ? String(config.riesgo_alto_desde) : '2'
  );

  const setConfig = useSetDashboardConfig(materiaId);

  // Plural de la etiqueta para los textos de ayuda ("unidades" / "semanas" de atraso).
  const plural = etiqueta === 'Semana' ? 'semanas' : 'unidades';

  // El umbral de riesgo alto debe ser mayor que el de riesgo medio (igual que el backend),
  // si no la franja de riesgo medio desaparece. Bloqueamos el guardado y avisamos.
  const medioNum = Number(riesgoMedio);
  const altoNum = Number(riesgoAlto);
  const umbralesInvalidos =
    !riesgoMedio ||
    !riesgoAlto ||
    medioNum < 1 ||
    altoNum < 1 ||
    altoNum <= medioNum;

  const etiquetaOptions: SelectOption[] = [
    { value: 'Unidad', label: 'Unidad (por defecto)' },
    { value: 'Semana', label: 'Semana (cursado por semanas, ej. PYE)' },
  ];

  const cohorteSel = cohortes.find((c) => String(c.id) === cohorteId);

  const cohorteOptions: SelectOption[] = [
    { value: '', label: 'Elegí una cohorte' },
    ...cohortes.map((c) => ({ value: String(c.id), label: c.codigo })),
  ];
  const cuatrimestreOptions: SelectOption[] = [
    { value: '', label: 'Elegí un cuatrimestre' },
    ...(cohorteSel?.cuatrimestres ?? []).map((q) => ({
      value: String(q.id),
      label: `Cuatrimestre ${q.numero}`,
    })),
  ];
  const topeOptions: SelectOption[] = [
    { value: '', label: 'Sin tope (cuentan todas las unidades)' },
    ...(secciones ?? [])
      .filter((s) => !s.es_cabecera_sugerida)
      .map((s) => ({
        value: String(s.moodle_section_id),
        label: `#${s.section} · ${s.nombre}`,
      })),
  ];

  const handleCohorteChange = (value: string) => {
    setCohorteId(value);
    setCuatrimestreId(''); // resetear el cuatrimestre al cambiar de cohorte
  };

  const handleGuardar = () => {
    if (umbralesInvalidos) return;
    setConfig.mutate({
      cuatrimestre_id: cuatrimestreId ? Number(cuatrimestreId) : null,
      unidad_actual: unidadActual ? Number(unidadActual) : null,
      moodle_section_fin_id: topeId ? Number(topeId) : null,
      etiqueta_unidad: etiqueta || 'Unidad',
      riesgo_medio_desde: medioNum,
      riesgo_alto_desde: altoNum,
    });
  };

  return (
    <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
      <h2 className="text-lg font-semibold text-foreground">Vinculación y unidad actual</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Asigná la materia a un cuatrimestre y definí en qué unidad se está cursando.
      </p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Select
          label="Cohorte"
          options={cohorteOptions}
          value={cohorteId}
          onChange={(e) => handleCohorteChange(e.target.value)}
        />
        <Select
          label="Cuatrimestre"
          options={cuatrimestreOptions}
          value={cuatrimestreId}
          onChange={(e) => setCuatrimestreId(e.target.value)}
          disabled={!cohorteSel}
        />
        <Input
          label="Unidad actual"
          type="number"
          inputMode="numeric"
          pattern="[0-9]*"
          min={1}
          placeholder="Ej: 5"
          value={unidadActual}
          onChange={(e) => setUnidadActual(e.target.value)}
        />
        <Select
          label="Tope (fin de unidades de contenido)"
          options={topeOptions}
          value={topeId}
          onChange={(e) => setTopeId(e.target.value)}
        />
        <Select
          label="Etiqueta de la progresión"
          options={etiquetaOptions}
          value={etiqueta}
          onChange={(e) => setEtiqueta(e.target.value)}
          helperText="Cómo se nombra en los reportes (Excel/PDF/emails): Unidad o Semana."
        />
      </div>

      {/* Umbrales de riesgo configurables por materia (atraso en unidades/semanas). */}
      <div className="mt-6 border-t border-border pt-4">
        <h3 className="text-base font-semibold text-foreground">Umbrales de riesgo</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Definí a partir de cuántas {plural} de atraso (respecto de la {etiqueta.toLowerCase()}{' '}
          actual) un alumno entra en cada nivel. Una materia por {plural} (ej. Estadística, 13
          semanas) suele tolerar más atraso que una por unidades.
        </p>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Input
            label={`Riesgo medio desde (${plural} de atraso)`}
            type="number"
            inputMode="numeric"
            pattern="[0-9]*"
            min={1}
            placeholder="Ej: 1"
            value={riesgoMedio}
            onChange={(e) => setRiesgoMedio(e.target.value)}
          />
          <Input
            label={`Riesgo alto desde (${plural} de atraso)`}
            type="number"
            inputMode="numeric"
            pattern="[0-9]*"
            min={1}
            placeholder="Ej: 2"
            value={riesgoAlto}
            onChange={(e) => setRiesgoAlto(e.target.value)}
          />
        </div>

        {umbralesInvalidos ? (
          <p className="mt-2 text-sm text-destructive">
            El umbral de riesgo alto debe ser mayor que el de riesgo medio (y ambos ≥ 1).
          </p>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            Al día: hasta {Math.max(0, medioNum - 1)} de atraso · Riesgo medio: {medioNum}
            {altoNum - 1 > medioNum ? `–${altoNum - 1}` : ''} · Riesgo alto: {altoNum} o más.
          </p>
        )}
      </div>

      <div className="mt-4 flex justify-end">
        <Button
          onClick={handleGuardar}
          isLoading={setConfig.isPending}
          disabled={umbralesInvalidos}
          className="w-full sm:w-auto"
        >
          Guardar configuración
        </Button>
      </div>
    </div>
  );
};
