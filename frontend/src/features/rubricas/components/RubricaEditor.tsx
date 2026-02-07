import { useEffect, useState } from 'react';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { PenLine, FileText, Code, Upload, Trash2 } from 'lucide-react';

import { Modal } from '@/shared/components/ui/Modal';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { Select } from '@/shared/components/ui/Select';
import { Spinner } from '@/shared/components/ui/Spinner';
import { cn } from '@/shared/utils/cn';

import { useCreateRubrica, useUpdateRubrica, useGenerarRubricaDesdePDF } from '../hooks/useRubricas';
import { useMaterias } from '@/features/materias/hooks';
import type { Rubrica, TipoRubrica } from '../types';
import { RubricaManualMode } from './RubricaManualMode';

// ========== SCHEMAS ==========

const criterioSchema = z.object({
  id: z.string(),
  nombre: z.string().min(1, 'Nombre requerido').max(100),
  descripcion: z.string().min(10, 'Mínimo 10 caracteres').max(500),
  puntaje_maximo: z.number().min(1, 'Mínimo 1').max(100, 'Máximo 100'),
});

const subcriterioSchema = z.object({
  id: z.string().min(1, 'ID requerido'),
  descripcion: z.string().min(1, 'Descripción requerida'),
  evidencias: z.array(z.string()),
});

const criterioJerarquicoSchema = z.object({
  id: z.string().min(1, 'ID requerido'),
  nombre: z.string().min(1, 'Nombre requerido').max(100),
  descripcion: z.string().min(1, 'Descripción requerida').max(500),
  peso: z.number().min(1, 'Mínimo 1').max(100, 'Máximo 100'),
  instrucciones_puntuacion: z.string().optional(),
  subcriterios: z.array(subcriterioSchema).min(1, 'Debe haber al menos un subcriterio'),
});

const rubricaFormSchema = z.object({
  materia_id: z.number().min(1, 'Materia requerida'),
  tipo: z.enum(['TP', 'PARCIAL_1', 'PARCIAL_2', 'RECUPERATORIO_1', 'RECUPERATORIO_2', 'FINAL', 'GLOBAL']),
  nombre: z.string().min(1, 'Nombre requerido').max(200),
  numero: z.number().min(1).max(999),
  anio: z.number().min(2020).max(2100),
  criterios: z
    .array(criterioSchema)
    .min(1, 'Debe haber al menos un criterio')
    .max(20, 'Máximo 20 criterios'),
  criterios_jerarquicos: z.array(criterioJerarquicoSchema).optional(),
}).refine(
  (data) => {
    const suma = data.criterios.reduce((acc, c) => acc + c.puntaje_maximo, 0);
    return suma === 100;
  },
  {
    message: 'La suma de puntajes debe ser exactamente 100',
    path: ['criterios'],
  }
);

type RubricaFormData = z.infer<typeof rubricaFormSchema>;

// ========== CONSTANTS ==========

const TIPO_LABELS: Record<TipoRubrica, string> = {
  TP: 'Trabajo Práctico',
  PARCIAL_1: 'Parcial 1',
  PARCIAL_2: 'Parcial 2',
  RECUPERATORIO_1: 'Recuperatorio 1',
  RECUPERATORIO_2: 'Recuperatorio 2',
  FINAL: 'Final',
  GLOBAL: 'Global',
};

type CreationMode = 'manual' | 'pdf' | 'json';

const CREATION_MODES: { id: CreationMode; icon: typeof PenLine; label: string; description: string; activeBorder: string; activeText: string; activeBg: string }[] = [
  { id: 'manual', icon: PenLine, label: 'Manual', description: 'Define criterios manualmente', activeBorder: 'border-accent', activeText: 'text-accent', activeBg: 'bg-accent/10' },
  { id: 'pdf', icon: FileText, label: 'Desde PDF', description: 'Extrae criterios con IA', activeBorder: 'border-success', activeText: 'text-success', activeBg: 'bg-success/10' },
  { id: 'json', icon: Code, label: 'Desde JSON', description: 'Carga desde archivo JSON', activeBorder: 'border-warning', activeText: 'text-warning', activeBg: 'bg-warning/10' },
];

const JSON_EXAMPLE = JSON.stringify({
  criterios: [
    { nombre: 'Funcionalidad correcta', descripcion: 'El programa realiza todas las operaciones solicitadas en la consigna', puntaje_maximo: 40 },
    { nombre: 'Uso correcto de estructuras', descripcion: 'Implementa las estructuras de datos requeridas según lo indicado', puntaje_maximo: 30 },
    { nombre: 'Estilo y legibilidad', descripcion: 'Código limpio, bien indentado, con nombres de variables descriptivos', puntaje_maximo: 20 },
    { nombre: 'Manejo de errores', descripcion: 'Validación de entradas y tratamiento de casos borde', puntaje_maximo: 10 },
  ],
}, null, 2);

// ========== MAIN COMPONENT ==========

interface RubricaEditorProps {
  isOpen: boolean;
  onClose: () => void;
  materiaId?: number;
  rubrica?: Rubrica;
}

export function RubricaEditor({
  isOpen,
  onClose,
  materiaId,
  rubrica,
}: RubricaEditorProps) {
  const isEditing = !!rubrica;
  const createMutation = useCreateRubrica();
  const updateMutation = useUpdateRubrica();
  const generarPDFMutation = useGenerarRubricaDesdePDF();
  const { data: materiasData } = useMaterias({ page: 1, per_page: 100 });

  const [creationMode, setCreationMode] = useState<CreationMode>('manual');
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [sumaPuntajes, setSumaPuntajes] = useState(0);

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
    reset,
    watch,
    setValue,
  } = useForm<RubricaFormData>({
    resolver: zodResolver(rubricaFormSchema),
    defaultValues: rubrica
      ? {
        materia_id: rubrica.materia_id,
        tipo: rubrica.tipo,
        nombre: rubrica.titulo, // V2 usa "titulo"
        numero: rubrica.numero,
        anio: rubrica.anio,
        // Adaptar V2 → V1: Convertir criterios jerárquicos a planos (para modo PDF/JSON)
        criterios: rubrica.criterios_json.map((c) => ({
          id: crypto.randomUUID().replace(/-/g, '').slice(0, 20),
          nombre: c.nombre,
          descripcion: c.descripcion,
          puntaje_maximo: c.peso, // V2 usa "peso" en lugar de "puntaje_maximo"
        })),
        // Criterios jerárquicos para modo manual
        criterios_jerarquicos: rubrica.criterios_json,
      }
      : {
        materia_id: materiaId || 0,
        tipo: 'TP',
        nombre: '',
        numero: 1,
        anio: new Date().getFullYear(),
        criterios: [
          {
            id: crypto.randomUUID().replace(/-/g, '').slice(0, 20),
            nombre: '',
            descripcion: '',
            puntaje_maximo: 100,
          },
        ],
        criterios_jerarquicos: [
          {
            id: 'C1',
            nombre: '',
            descripcion: '',
            peso: 100,
            instrucciones_puntuacion: '',
            subcriterios: [
              {
                id: 'C1.1',
                descripcion: '',
                evidencias: [],
              },
            ],
          },
        ],
      },
  });

  const { replace } = useFieldArray({
    control,
    name: 'criterios',
  });

  // Fields para modo manual (estructura jerárquica)
  useFieldArray({
    control,
    name: 'criterios_jerarquicos',
  });

  const criterios = watch('criterios');
  const criteriosJerarquicos = watch('criterios_jerarquicos');

  // Reset modal state on open
  useEffect(() => {
    if (isOpen) {
      setCreationMode('manual');
      setPdfFile(null);
      setJsonText('');
      setJsonError(null);
      if (!rubrica) {
        reset({
          materia_id: materiaId || 0,
          tipo: 'TP',
          nombre: '',
          numero: 1,
          anio: new Date().getFullYear(),
          criterios: [{ id: crypto.randomUUID().replace(/-/g, '').slice(0, 20), nombre: '', descripcion: '', puntaje_maximo: 100 }],
          criterios_jerarquicos: [
            {
              id: 'C1',
              nombre: '',
              descripcion: '',
              peso: 100,
              instrucciones_puntuacion: '',
              subcriterios: [
                {
                  id: 'C1.1',
                  descripcion: '',
                  evidencias: [],
                },
              ],
            },
          ],
        });
      }
    }
  }, [isOpen]);

  // Calcular suma de puntajes según el modo
  useEffect(() => {
    if (creationMode === 'manual') {
      // En modo manual, usar criterios_jerarquicos (peso)
      const jerarquicos = (criteriosJerarquicos || []) as Array<{ peso?: number }>;
      const suma = jerarquicos.reduce((acc, c) => acc + (c.peso || 0), 0);
      setSumaPuntajes(suma);
    } else {
      // En modos PDF/JSON, usar criterios (puntaje_maximo)
      const suma = criterios.reduce((acc, c) => acc + (c.puntaje_maximo || 0), 0);
      setSumaPuntajes(suma);
    }
  }, [criterios, criteriosJerarquicos, creationMode]);

  // ── JSON handlers ──
  const handleJSONFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      setJsonText(event.target?.result as string);
      setJsonError(null);
    };
    reader.readAsText(file);
  };

  const handleLoadJSON = () => {
    setJsonError(null);
    try {
      const parsed = JSON.parse(jsonText);
      const raw: unknown[] = Array.isArray(parsed) ? parsed : parsed.criterios;
      if (!Array.isArray(raw) || raw.length === 0) {
        setJsonError('No se encontraron criterios válidos en el JSON');
        return;
      }
      const mapped = raw.map((c) => {
        const obj = c as Record<string, unknown>;
        return {
          id: (typeof obj.id === 'string' && obj.id) || crypto.randomUUID().replace(/-/g, '').slice(0, 20),
          nombre: String(obj.nombre || ''),
          descripcion: String(obj.descripcion || ''),
          puntaje_maximo: Number(obj.puntaje_maximo) || 0,
        };
      });
      replace(mapped);
      setCreationMode('manual');
      setJsonText('');
    } catch {
      setJsonError('JSON inválido. Revisa la sintaxis.');
    }
  };

  // ── PDF handler ──
  const handleGenerarPDF = async () => {
    if (!pdfFile) return;
    try {
      await generarPDFMutation.mutateAsync({
        materiaId: watch('materia_id'),
        tipo: watch('tipo'),
        anio: watch('anio'),
        file: pdfFile,
      });
      reset();
      setPdfFile(null);
      setCreationMode('manual');
      onClose();
    } catch (error) {
      console.error('Error generando rúbrica:', error);
    }
  };

  // ── Form submit ──
  const onSubmit = async (data: RubricaFormData) => {
    console.log('🟢 onSubmit disparado', data);

    try {
      // Usar criterios_jerarquicos si están disponibles (modo manual V2), sino adaptar V1 → V2
      const criterios_jerarquicos = data.criterios_jerarquicos || data.criterios.map((c, idx) => ({
        id: `C${idx + 1}`,
        nombre: c.nombre,
        descripcion: c.descripcion,
        peso: c.puntaje_maximo, // peso en % = puntaje en V1
        instrucciones_puntuacion: '',
        subcriterios: [
          {
            id: `C${idx + 1}.1`,
            descripcion: c.descripcion,
            evidencias: ['Cumple con los requisitos especificados'],
          }
        ],
      }));

      console.log('📦 Payload V2:', criterios_jerarquicos);

      if (isEditing) {
        console.log('✏️ Update rubrica', rubrica.id);
        await updateMutation.mutateAsync({
          id: rubrica.id,
          data: {
            titulo: data.nombre, // V2 usa "titulo" no "nombre"
            descripcion: data.nombre, // Usar nombre como descripción temporal
            criterios_json: criterios_jerarquicos,
            penalizaciones_json: [],
            condiciones_desaprobacion_json: [],
          },
        });
      } else {
        console.log('➕ Create rubrica');
        await createMutation.mutateAsync({
          materia_id: data.materia_id,
          tipo: data.tipo,
          numero: data.numero,
          anio: data.anio,
          titulo: data.nombre, // V2 usa "titulo" no "nombre"
          descripcion: data.nombre, // Usar nombre como descripción temporal
          puntaje_maximo: 100,
          metadata_json: {},
          criterios_json: criterios_jerarquicos,
          penalizaciones_json: [],
          condiciones_desaprobacion_json: [],
          fuente: 'MANUAL',
        });
      }

      console.log('✅ Guardado OK');
      reset();
      onClose();
    } catch (error) {
      console.error('❌ Error guardando rúbrica:', error);
    }
  };


  const handleClose = () => {
    reset();
    setCreationMode('manual');
    setPdfFile(null);
    setJsonText('');
    setJsonError(null);
    onClose();
  };

  const isSubmitting = createMutation.isPending || updateMutation.isPending;
  const isGeneratingPDF = generarPDFMutation.isPending;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isEditing ? 'Editar Rúbrica' : 'Crear Rúbrica'}
      size="xl"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* ── Información General ── */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Información General</h3>

          <Select
            label="Materia"
            value={watch('materia_id')?.toString() || ''}
            onChange={(e) =>
              setValue('materia_id', e.target.value ? parseInt(e.target.value) : 0, { shouldValidate: true })
            }
            error={errors.materia_id?.message}
            disabled={isEditing}
          >
            <option value="">Seleccionar materia</option>
            {(materiasData?.items || []).map((m) => (
              <option key={m.id} value={m.id.toString()}>
                {m.codigo} - {m.nombre}
              </option>
            ))}
          </Select>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Select
              label="Tipo"
              {...register('tipo')}
              error={errors.tipo?.message}
              disabled={isEditing}
            >
              <option value="">Seleccionar tipo</option>
              {Object.entries(TIPO_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>

            <Input
              label="Número"
              type="number"
              min={1}
              max={999}
              {...register('numero', { valueAsNumber: true })}
              error={errors.numero?.message}
              disabled={isEditing || creationMode === 'pdf'}
            />

            <Input
              label="Año"
              type="number"
              min={2020}
              max={2100}
              {...register('anio', { valueAsNumber: true })}
              error={errors.anio?.message}
              disabled={isEditing}
            />
          </div>

          <div>
            <Input
              label="Nombre"
              {...register('nombre')}
              error={errors.nombre?.message}
              placeholder="ej: TP1 - Listas en Python"
              disabled={creationMode === 'pdf'}
            />
            {creationMode === 'pdf' && (
              <p className="mt-1 text-xs text-muted-foreground">
                Se genera automáticamente desde el PDF
              </p>
            )}
          </div>
        </div>

        {/* ── Modo de Creación (solo al crear) ── */}
        {!isEditing && (
          <div className="space-y-3">
            <h3 className="text-lg font-semibold">Modo de Creación</h3>
            <div className="grid grid-cols-3 gap-3">
              {CREATION_MODES.map((mode) => {
                const Icon = mode.icon;
                const isActive = creationMode === mode.id;
                return (
                  <button
                    key={mode.id}
                    type="button"
                    onClick={() => setCreationMode(mode.id)}
                    className={cn(
                      'flex flex-col items-center p-4 rounded-lg transition-colors',
                      isActive
                        ? cn('border-2', mode.activeBorder, mode.activeBg)
                        : 'border border-border bg-card hover:bg-muted'
                    )}
                  >
                    <Icon className={cn('h-6 w-6 mb-2', isActive ? mode.activeText : 'text-muted-foreground')} />
                    <span className={cn('text-sm font-medium', isActive ? mode.activeText : 'text-foreground')}>
                      {mode.label}
                    </span>
                    <span className={cn('text-xs mt-0.5 text-center', isActive ? 'text-muted-foreground' : 'text-muted-foreground')}>
                      {mode.description}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Manual: Editor de Criterios ── */}
        {creationMode === 'manual' && (
          <RubricaManualMode
            control={control}
            register={register}
            errors={errors}
            watch={watch}
          />
        )}

        {/* ── PDF Mode ── */}
        {creationMode === 'pdf' && !isEditing && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Subir PDF de Consigna</h3>
            <p className="text-sm text-muted-foreground">
              La IA extraerá los criterios de evaluación del PDF automáticamente.
            </p>

            {!pdfFile ? (
              <label className="flex flex-col items-center justify-center w-full h-40 px-4 bg-card border-2 border-dashed border-border rounded-lg cursor-pointer hover:bg-muted transition-colors">
                <Upload className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  <span className="font-semibold text-accent">Haz clic</span> o arrastra un PDF aquí
                </p>
                <p className="text-xs text-muted-foreground mt-1">Solo archivos PDF (máx. 10 MB)</p>
                <input
                  type="file"
                  accept=".pdf"
                  className="sr-only"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) setPdfFile(file);
                  }}
                />
              </label>
            ) : (
              <div className="flex items-center justify-between bg-muted rounded-md px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-accent" />
                  <span className="text-sm text-foreground">{pdfFile.name}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setPdfFile(null)}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            )}

            {generarPDFMutation.isError && (
              <p className="text-sm text-destructive">
                Error al generar la rúbrica. Verifica tu API Key y vuelve a intentar.
              </p>
            )}
          </div>
        )}

        {/* ── JSON Mode ── */}
        {creationMode === 'json' && !isEditing && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Cargar desde JSON</h3>
              <label className="flex items-center gap-1.5 text-xs text-accent cursor-pointer hover:underline">
                <Upload className="h-3.5 w-3.5" />
                Subir archivo .json
                <input
                  type="file"
                  accept=".json"
                  className="sr-only"
                  onChange={handleJSONFileUpload}
                />
              </label>
            </div>
            <p className="text-sm text-muted-foreground">
              Pega o sube un JSON con la estructura de criterios. Se cargará en el editor para revisión.
            </p>

            {/* Ejemplo visible */}
            <div className="rounded-md border border-border bg-muted overflow-hidden">
              <div className="flex items-center justify-between px-3 py-1.5 border-b border-border">
                <span className="text-xs font-medium text-muted-foreground">Ejemplo de formato válido</span>
                <button
                  type="button"
                  onClick={() => { setJsonText(JSON_EXAMPLE); setJsonError(null); }}
                  className="text-xs text-warning font-medium hover:underline"
                >
                  Usar este ejemplo
                </button>
              </div>
              <pre className="px-3 py-2 text-xs font-mono text-foreground whitespace-pre-wrap overflow-x-auto max-h-36 overflow-y-auto">
                {JSON_EXAMPLE}
              </pre>
            </div>

            <textarea
              value={jsonText}
              onChange={(e) => { setJsonText(e.target.value); setJsonError(null); }}
              className="w-full h-40 px-3 py-2 border border-input rounded-md bg-background text-foreground text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              placeholder="Pega tu JSON aquí..."
            />
            {jsonError && <p className="text-sm text-destructive">{jsonError}</p>}
          </div>
        )}

        {/* ── Footer ── */}
        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <Button type="button" variant="outline" onClick={handleClose}>
            Cancelar
          </Button>

          {creationMode === 'pdf' && !isEditing ? (
            <Button
              type="button"
              onClick={handleGenerarPDF}
              disabled={!pdfFile || isGeneratingPDF}
              className="min-w-[140px]"
            >
              {isGeneratingPDF ? (
                <Spinner size="sm" />
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Generar Rúbrica
                </>
              )}
            </Button>
          ) : creationMode === 'json' && !isEditing ? (
            <Button type="button" onClick={handleLoadJSON} disabled={!jsonText.trim()}>
              <Code className="h-4 w-4 mr-2" />
              Cargar criterios
            </Button>
          ) : (
            <Button
              type="submit"
              disabled={isSubmitting || sumaPuntajes !== 100}
              className="min-w-[120px]"
            >
              {isSubmitting ? (
                <Spinner size="sm" />
              ) : isEditing ? (
                'Guardar Cambios'
              ) : (
                'Crear Rúbrica'
              )}
            </Button>
          )}
        </div>
      </form>
    </Modal>
  );
}
