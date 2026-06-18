import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Code, Upload, Database, ListChecks, AlertTriangle, XCircle, FileText } from 'lucide-react';

import { Modal } from '@/shared/components/ui/Modal';
import { Button } from '@/shared/components/ui/Button';
import { Spinner } from '@/shared/components/ui/Spinner';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/shared/components/ui/Accordion';
import { KeyValueInput } from '@/shared/components/ui/KeyValueInput';
import { ExtensionTagInput } from '@/shared/components/ui/ExtensionTagInput';
import { cn } from '@/shared/utils/cn';

import { useCreateRubrica, useUpdateRubrica, useGenerarRubricaDesdePDF, usePreviewRubricaPDF, usePreviewRubricaPDFResumido } from '../hooks/useRubricas';
import { useMaterias } from '@/features/materias/hooks';
import type { Rubrica } from '../types';
import { criterioSchema } from '../schemas/rubrica-schema';
import { RubricaManualMode } from './RubricaManualMode';
import { PenalizacionesEditor } from './PenalizacionesEditor';
import { CondicionesEditor } from './CondicionesEditor';
import { RubricaGeneralInfo } from './RubricaGeneralInfo';
import { RubricaCreationModeSelector } from './RubricaCreationModeSelector';
import { RubricaPDFMode } from './RubricaPDFMode';
import { RubricaJSONMode } from './RubricaJSONMode';
import type { CreationMode } from '../constants/rubrica-constants';

// ========== SCHEMAS ==========

const rubricaFormSchema = z.object({
  materia_id: z.number().min(1, 'Materia requerida'),
  tipo: z.enum(['TP', 'PARCIAL_1', 'PARCIAL_2', 'RECUPERATORIO_1', 'RECUPERATORIO_2', 'FINAL', 'GLOBAL']),
  titulo: z.string().min(1, 'Título requerido').max(200),
  descripcion: z.string().min(1, 'Descripción requerida'),
  numero: z.number().min(1).max(999),
  anio: z.number().min(2020).max(2100),
  metadata: z.record(z.string(), z.any()),
  criterios: z
    .array(criterioSchema)
    .min(1, 'Debe haber al menos un criterio'),
  penalizaciones: z.array(z.object({
    id: z.string().min(1),
    descripcion: z.string().min(1),
    descuento_porcentaje: z.number().min(0).max(100),
  })),
  condiciones_desaprobacion: z.array(z.object({
    id: z.string().min(1),
    condicion: z.string().min(1),
    nota_maxima: z.number().min(0).max(100),
  })),
  moodle_assign_id: z
    .number()
    .int()
    .positive('Debe ser un número positivo')
    .nullable()
    .optional(),
  modo_consolidacion: z.enum(['solo_codigo', 'web_completo', 'proyecto_completo', 'personalizado']),
  extensiones_personalizadas: z.array(z.string()).nullable().optional(),
}).refine(
  (data) => {
    const suma = data.criterios.reduce((acc, c) => acc + c.peso, 0);
    return suma === 100;
  },
  {
    message: 'La suma de pesos debe ser exactamente 100',
    path: ['criterios'],
  }
);

type RubricaFormData = z.infer<typeof rubricaFormSchema>;

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
  const previewPDFMutation = usePreviewRubricaPDF();
  const previewPDFResumidoMutation = usePreviewRubricaPDFResumido();
  const { data: materiasData } = useMaterias({ page: 1, per_page: 100 });

  const [creationMode, setCreationMode] = useState<CreationMode>(rubrica ? 'manual' : 'pdf');
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [sumaPesos, setSumaPesos] = useState(0);

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
    reset,
    watch,
    setValue,
    getValues,
  } = useForm<RubricaFormData>({
    resolver: zodResolver(rubricaFormSchema),
    defaultValues: rubrica
      ? {
        materia_id: rubrica.materia_id,
        tipo: rubrica.tipo,
        titulo: rubrica.titulo,
        descripcion: rubrica.descripcion,
        numero: rubrica.numero,
        anio: rubrica.anio,
        metadata: rubrica.metadata_json || {},
        criterios: rubrica.criterios_json,
        penalizaciones: rubrica.penalizaciones_json || [],
        condiciones_desaprobacion: rubrica.condiciones_desaprobacion_json || [],
        moodle_assign_id: rubrica.moodle_assign_id ?? null,
        modo_consolidacion: rubrica.modo_consolidacion ?? 'solo_codigo',
        extensiones_personalizadas: rubrica.extensiones_personalizadas ?? [],
      }
      : {
        materia_id: materiaId || 0,
        tipo: 'TP',
        titulo: '',
        descripcion: '',
        numero: 1,
        anio: new Date().getFullYear(),
        metadata: {},
        criterios: [
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
        penalizaciones: [],
        condiciones_desaprobacion: [],
        modo_consolidacion: 'solo_codigo',
        extensiones_personalizadas: [],
      },
  });


  const criterios = watch('criterios');


  // Reset modal state on open or when rubrica changes
  useEffect(() => {
    if (!isOpen) return;

    setPdfFile(null);
    setJsonText('');
    setJsonError(null);

    if (rubrica) {
      // EDICIÓN: Cargar datos existentes en modo manual
      setCreationMode('manual');
      reset({
        materia_id: rubrica.materia_id,
        tipo: rubrica.tipo,
        titulo: rubrica.titulo,
        descripcion: rubrica.descripcion,
        numero: rubrica.numero,
        anio: rubrica.anio,
        metadata: rubrica.metadata_json || {},
        criterios: rubrica.criterios_json,
        penalizaciones: rubrica.penalizaciones_json || [],
        condiciones_desaprobacion: rubrica.condiciones_desaprobacion_json || [],
        moodle_assign_id: rubrica.moodle_assign_id ?? null,
        modo_consolidacion: rubrica.modo_consolidacion ?? 'solo_codigo',
        extensiones_personalizadas: rubrica.extensiones_personalizadas ?? [],
      });
    } else {
      // CREACIÓN: Empezar en modo PDF con datos vacíos
      setCreationMode('pdf');
      reset({
        materia_id: materiaId || 0,
        tipo: 'TP',
        titulo: '',
        descripcion: '',
        numero: 1,
        anio: new Date().getFullYear(),
        metadata: {},
        criterios: [
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
        penalizaciones: [],
        condiciones_desaprobacion: [],
        modo_consolidacion: 'solo_codigo',
        extensiones_personalizadas: [],
      });
    }
  }, [isOpen, rubrica, materiaId, reset]);

  // Calcular suma de pesos
  useEffect(() => {
    const suma = criterios.reduce((acc, c) => acc + (c.peso || 0), 0);
    setSumaPesos(suma);
  }, [criterios]);

  // Precargar JSON cuando se cambia a modo JSON
  useEffect(() => {
    if (creationMode === 'json' && isEditing && rubrica) {
      // Si estamos editando y cambiamos a modo JSON, precargar con los datos actuales
      const currentData = {
        titulo: watch('titulo'),
        descripcion: watch('descripcion'),
        metadata: watch('metadata'),
        criterios: watch('criterios'),
        penalizaciones: watch('penalizaciones'),
        condiciones_desaprobacion: watch('condiciones_desaprobacion'),
      };

      // Solo precargar si el JSON está vacío
      if (!jsonText.trim()) {
        setJsonText(JSON.stringify(currentData, null, 2));
      }
    }
  }, [creationMode, isEditing, rubrica, watch, jsonText]);

  // ── JSON handlers ──
  const handleLoadJSON = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setJsonError(null);
    try {
      const parsed = JSON.parse(jsonText);

      // Validar estructura mínima
      if (!parsed.titulo || !parsed.descripcion || !parsed.criterios || !Array.isArray(parsed.criterios)) {
        setJsonError('El JSON debe contener: titulo, descripcion y criterios (array)');
        return;
      }

      // Cargar datos en el formulario
      setValue('titulo', parsed.titulo);
      setValue('descripcion', parsed.descripcion);
      setValue('metadata', parsed.metadata || {});
      setValue('criterios', parsed.criterios);
      setValue('penalizaciones', parsed.penalizaciones || []);
      setValue('condiciones_desaprobacion', parsed.condiciones_desaprobacion || []);

      setCreationMode('manual');
      setJsonText('');
    } catch (error) {
      setJsonError('JSON inválido. Revisa la sintaxis.');
    }
  };

  // ── PDF handler ──
  const handleGenerarPDF = async () => {
    if (!pdfFile) return;
    try {
      const response = await generarPDFMutation.mutateAsync({
        materiaId: watch('materia_id'),
        tipo: watch('tipo'),
        anio: watch('anio'),
        file: pdfFile,
      });

      // Cargar la rúbrica V2 generada en el formulario
      if (response) {
        setValue('titulo', response.titulo || '');
        setValue('descripcion', response.descripcion || '');
        setValue('metadata', response.metadata || {});
        setValue('criterios', response.criterios || []);
        setValue('penalizaciones', response.penalizaciones || []);
        setValue('condiciones_desaprobacion', response.condiciones_desaprobacion || []);
      }

      setPdfFile(null);
      setCreationMode('manual');
      // NO cerrar el modal - permitir que el usuario revise y edite
    } catch (error) {
      console.error('Error generando rúbrica:', error);
    }
  };

  // ── Preview PDF handler ──
  const handlePreviewPDF = async () => {
    try {
      // Get current form data (use getValues to get fresh values)
      const formData = getValues();

      // Get materia name from materiasData
      const materia = materiasData?.items?.find(m => m.id === formData.materia_id);
      const materiaNombre = materia ? `${materia.codigo} - ${materia.nombre}` : 'N/A';

      console.log('📄 Generando preview PDF con datos:', {
        titulo: formData.titulo,
        criterios: formData.criterios,
      });

      // Call preview mutation
      await previewPDFMutation.mutateAsync({
        materia_nombre: materiaNombre,
        tipo: formData.tipo,
        numero: formData.numero,
        anio: formData.anio,
        titulo: formData.titulo || 'Sin título',
        descripcion: formData.descripcion || 'Sin descripción',
        puntaje_maximo: 100,
        criterios: formData.criterios || [],
        penalizaciones: formData.penalizaciones || [],
        condiciones_desaprobacion: formData.condiciones_desaprobacion || [],
      });
    } catch (error) {
      console.error('Error generando preview PDF:', error);
      alert('Error al generar la vista previa del PDF. Por favor, verifica que todos los campos requeridos estén completos.');
    }
  };

  // ── Preview PDF RESUMIDO handler ──
  const handlePreviewPDFResumido = async () => {
    try {
      // Get current form data (use getValues to get fresh values)
      const formData = getValues();

      // Get materia name from materiasData
      const materia = materiasData?.items?.find(m => m.id === formData.materia_id);
      const materiaNombre = materia ? `${materia.codigo} - ${materia.nombre}` : 'N/A';

      // Call preview mutation for summary
      await previewPDFResumidoMutation.mutateAsync({
        materia_nombre: materiaNombre,
        tipo: formData.tipo,
        numero: formData.numero,
        anio: formData.anio,
        titulo: formData.titulo || 'Sin título',
        descripcion: formData.descripcion || 'Sin descripción',
        puntaje_maximo: 100,
        criterios: formData.criterios || [],
        penalizaciones: formData.penalizaciones || [],
        condiciones_desaprobacion: formData.condiciones_desaprobacion || [],
      });
    } catch (error) {
      console.error('Error generando preview de guía para estudiantes:', error);
      alert('Error al generar la vista previa de la guía para estudiantes.');
    }
  };

  // ── Form submit ──
  const onSubmit = async (data: RubricaFormData) => {
    console.log('📝 Intentando crear rúbrica con datos:', data);
    console.log('📝 Criterios JSON:', JSON.stringify(data.criterios, null, 2));
    try {
      if (isEditing) {
        await updateMutation.mutateAsync({
          id: rubrica.id,
          data: {
            titulo: data.titulo,
            descripcion: data.descripcion,
            metadata_json: data.metadata,
            criterios_json: data.criterios,
            penalizaciones_json: data.penalizaciones,
            condiciones_desaprobacion_json: data.condiciones_desaprobacion,
            moodle_assign_id: data.moodle_assign_id ?? undefined,
            modo_consolidacion: data.modo_consolidacion,
            extensiones_personalizadas:
              data.modo_consolidacion === 'personalizado'
                ? data.extensiones_personalizadas ?? []
                : null,
          },
        });
      } else {
        await createMutation.mutateAsync({
          materia_id: data.materia_id,
          tipo: data.tipo,
          numero: data.numero,
          anio: data.anio,
          titulo: data.titulo,
          descripcion: data.descripcion,
          puntaje_maximo: 100,
          metadata_json: data.metadata,
          criterios_json: data.criterios,
          penalizaciones_json: data.penalizaciones,
          condiciones_desaprobacion_json: data.condiciones_desaprobacion,
          fuente: 'manual',
          moodle_assign_id: data.moodle_assign_id ?? undefined,
          modo_consolidacion: data.modo_consolidacion,
          extensiones_personalizadas:
            data.modo_consolidacion === 'personalizado'
              ? data.extensiones_personalizadas ?? []
              : null,
        });
      }

      reset();
      onClose();
    } catch (error: any) {
      console.error('❌ Error guardando rúbrica:', error);
      console.error('❌ Detalle de respuesta:', error?.response?.data);
      // Mostrar error al usuario
      if (error?.response?.data?.detail) {
        alert(`Error: ${JSON.stringify(error.response.data.detail, null, 2)}`);
      }
    }
  };

  const handleClose = () => {
    reset();
    setCreationMode('pdf');
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
      fullScreen
    >
      <form
        onSubmit={(e) => {
          console.log('🚀 Form submit triggered');
          console.log('📋 Errores de validación:', errors);
          handleSubmit(onSubmit)(e);
        }}
        className="space-y-6"
      >
        {/* ── Información General ── */}
        <RubricaGeneralInfo
          register={register}
          errors={errors}
          watch={watch}
          setValue={setValue}
          materiasData={materiasData}
          isEditing={isEditing}
          creationMode={creationMode}
        />

        {/* ── Modo de Creación ── */}
        <RubricaCreationModeSelector
          creationMode={creationMode}
          setCreationMode={setCreationMode}
        />

        {/* ── Manual: Editor Completo con Accordion ── */}
        {creationMode === 'manual' && (
          <>
          {/* Tipo de proyecto: define cómo se consolida el código de las entregas */}
          <div className="space-y-2 rounded-lg border border-border bg-muted/20 p-4">
            <label className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Code className="h-4 w-4" />
              Tipo de proyecto (consolidación del código)
            </label>
            <select
              {...register('modo_consolidacion')}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="solo_codigo">Solo código (.py .java .js .ts .c .cpp …)</option>
              <option value="web_completo">Web completo (+ .html .css .scss .json)</option>
              <option value="proyecto_completo">Proyecto completo (+ .md .yml .xml .sql)</option>
              <option value="personalizado">Personalizado</option>
            </select>
            <p className="text-xs text-muted-foreground">
              Define qué archivos se incluyen al consolidar las entregas (importadas de Moodle o
              subidas a mano) antes de corregir con IA.
            </p>
            {watch('modo_consolidacion') === 'personalizado' && (
              <div className="pt-1">
                <ExtensionTagInput
                  value={watch('extensiones_personalizadas') || []}
                  onChange={(exts) => setValue('extensiones_personalizadas', exts)}
                />
              </div>
            )}
          </div>

          <Accordion defaultValue={[]} multiple>
            {/* Sección 1: Metadata (opcional) */}
            <AccordionItem value="metadata">
              <AccordionTrigger
                value="metadata"
                icon={<Database className="h-4 w-4" />}
                badge={
                  Object.keys(watch('metadata') || {}).length > 0 && (
                    <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-accent/20 text-accent rounded-full">
                      {Object.keys(watch('metadata') || {}).length}
                    </span>
                  )
                }
              >
                Metadata (opcional)
              </AccordionTrigger>
              <AccordionContent value="metadata">
                <KeyValueInput
                  value={watch('metadata') || {}}
                  onChange={(metadata) => setValue('metadata', metadata)}
                  placeholder={{ key: 'lenguaje', value: 'JavaScript' }}
                />
              </AccordionContent>
            </AccordionItem>

            {/* Sección 2: Criterios */}
            <AccordionItem value="criterios">
              <AccordionTrigger
                value="criterios"
                icon={<ListChecks className="h-4 w-4" />}
                badge={
                  <span className={cn(
                    "ml-2 px-2 py-0.5 text-xs font-medium rounded-full",
                    sumaPesos === 100
                      ? "bg-success/20 text-success"
                      : "bg-destructive/20 text-destructive"
                  )}>
                    {sumaPesos}%
                  </span>
                }
              >
                Criterios de Evaluación
              </AccordionTrigger>
              <AccordionContent value="criterios">
                <RubricaManualMode
                  control={control}
                  register={register}
                  errors={errors}
                  watch={watch}
                  setValue={setValue}
                />
              </AccordionContent>
            </AccordionItem>

            {/* Sección 3: Penalizaciones (opcional) */}
            <AccordionItem value="penalizaciones">
              <AccordionTrigger
                value="penalizaciones"
                icon={<AlertTriangle className="h-4 w-4" />}
                badge={
                  (watch('penalizaciones') || []).length > 0 && (
                    <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-warning/20 text-warning rounded-full">
                      {(watch('penalizaciones') || []).length}
                    </span>
                  )
                }
              >
                Penalizaciones (opcional)
              </AccordionTrigger>
              <AccordionContent value="penalizaciones">
                <PenalizacionesEditor
                  control={control}
                  register={register}
                  errors={errors}
                />
              </AccordionContent>
            </AccordionItem>

            {/* Sección 4: Condiciones de Desaprobación (opcional) */}
            <AccordionItem value="condiciones">
              <AccordionTrigger
                value="condiciones"
                icon={<XCircle className="h-4 w-4" />}
                badge={
                  (watch('condiciones_desaprobacion') || []).length > 0 && (
                    <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-destructive/20 text-destructive rounded-full">
                      {(watch('condiciones_desaprobacion') || []).length}
                    </span>
                  )
                }
              >
                Condiciones de Desaprobación (opcional)
              </AccordionTrigger>
              <AccordionContent value="condiciones">
                <CondicionesEditor
                  control={control}
                  register={register}
                  errors={errors}
                />
              </AccordionContent>
            </AccordionItem>
          </Accordion>
          </>
        )}

        {/* ── PDF Mode ── */}
        {creationMode === 'pdf' && (
          <RubricaPDFMode
            pdfFile={pdfFile}
            setPdfFile={setPdfFile}
            isError={generarPDFMutation.isError}
          />
        )}

        {/* ── JSON Mode ── */}
        {creationMode === 'json' && (
          <RubricaJSONMode
            jsonText={jsonText}
            setJsonText={setJsonText}
            jsonError={jsonError}
            setJsonError={setJsonError}
            currentJSON={
              isEditing || watch('titulo')
                ? JSON.stringify({
                    titulo: watch('titulo'),
                    descripcion: watch('descripcion'),
                    metadata: watch('metadata'),
                    criterios: watch('criterios'),
                    penalizaciones: watch('penalizaciones'),
                    condiciones_desaprobacion: watch('condiciones_desaprobacion'),
                  }, null, 2)
                : undefined
            }
          />
        )}

        {/* ── Footer ── */}
        <div className="flex flex-col gap-3 pt-4 border-t border-border sm:flex-row sm:items-center sm:justify-between">
          {/* Left side: Preview PDF buttons (only in manual mode) */}
          <div className="flex flex-col gap-2 sm:flex-row">
            {creationMode === 'manual' && (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handlePreviewPDF}
                  disabled={previewPDFMutation.isPending || !watch('titulo') || !watch('descripcion')}
                  title="Vista previa PDF completo"
                  className="w-full sm:w-auto"
                >
                  {previewPDFMutation.isPending ? (
                    <Spinner size="sm" />
                  ) : (
                    <>
                      <FileText className="h-3.5 w-3.5 mr-1.5" />
                      PDF Completo
                    </>
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handlePreviewPDFResumido}
                  disabled={previewPDFResumidoMutation.isPending || !watch('titulo') || !watch('descripcion')}
                  title="Vista previa de la guía para estudiantes"
                  className="w-full sm:w-auto"
                >
                  {previewPDFResumidoMutation.isPending ? (
                    <Spinner size="sm" />
                  ) : (
                    <>
                      <FileText className="h-3.5 w-3.5 mr-1.5" />
                      Guía Estudiante
                    </>
                  )}
                </Button>
              </>
            )}
          </div>

          {/* Right side: Action buttons */}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              className="w-full sm:w-auto"
            >
              Cancelar
            </Button>

            {creationMode === 'pdf' ? (
              <Button
                type="button"
                onClick={handleGenerarPDF}
                disabled={!pdfFile || isGeneratingPDF}
                className="w-full sm:w-auto sm:min-w-[140px]"
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
            ) : creationMode === 'json' ? (
              <Button
                type="button"
                onClick={handleLoadJSON}
                disabled={!jsonText.trim()}
                className="w-full sm:w-auto"
              >
                <Code className="h-4 w-4 mr-2" />
                Cargar criterios
              </Button>
            ) : (
              <Button
                type="submit"
                disabled={isSubmitting || sumaPesos !== 100}
                className="w-full sm:w-auto sm:min-w-[120px]"
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
        </div>
      </form>
    </Modal>
  );
}
