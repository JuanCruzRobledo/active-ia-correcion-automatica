// features/entregas/components/CargaEntregaModal.tsx
/**
 * CargaEntregaModal - Modal for uploading individual or bulk submissions.
 *
 * Mode selection uses card-style picker matching RubricaEditor's "Modo de Creación" pattern.
 * The form sub-component is keyed by mode so it remounts (and resets) on switch.
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md section 4.4
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-ENT-01, HU-ENT-02
 */

import { useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import toast from 'react-hot-toast';
import { useCreateEntrega, useCreateEntregaMasiva } from '../hooks';
import { Modal } from '@/shared/components/ui/Modal';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { Radio } from '@/shared/components/ui/Radio';
import { Checkbox } from '@/shared/components/ui/Checkbox';
import { Alert } from '@/shared/components/ui/Alert';
import { ExtensionTagInput } from '@/shared/components/ui/ExtensionTagInput';
import { FileUp, Upload, PackageOpen, CheckCircle, AlertCircle, X, FileText } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { ModoConsolidacion, CargaMasivaResponse } from '../types';

// ========== TYPES & CONSTANTS ==========

type CargaMode = 'individual' | 'masivo';

interface CargaEntregaModalProps {
  isOpen: boolean;
  onClose: () => void;
  comisionId: number;
  rubricaId: number;
}

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB

const ACCEPTED_FILE_TYPES = {
  individual: '*', // Acepta cualquier extensión
  masivo: ['.zip'],
};

const CARGA_MODES: {
  id: CargaMode;
  icon: typeof FileUp;
  label: string;
  description: string;
  activeBorder: string;
  activeText: string;
  activeBg: string;
}[] = [
    {
      id: 'individual',
      icon: FileUp,
      label: 'Entrega Individual',
      description: 'Un archivo por alumno',
      activeBorder: 'border-accent',
      activeText: 'text-accent',
      activeBg: 'bg-accent/10',
    },
    {
      id: 'masivo',
      icon: PackageOpen,
      label: 'Subir Lote',
      description: 'ZIP con múltiples entregas',
      activeBorder: 'border-success',
      activeText: 'text-success',
      activeBg: 'bg-success/10',
    },
  ];

// Schema for individual upload
const individualSchema = z.object({
  alumno_nombre: z
    .string()
    .min(1, 'El nombre del alumno es requerido')
    .max(100, 'Máximo 100 caracteres'),
  archivo: z
    .instanceof(File)
    .refine((file) => file.size <= MAX_FILE_SIZE, 'El archivo excede los 100 MB'),
  modo_consolidacion: z.enum(['SOLO_CODIGO', 'WEB_COMPLETO', 'PROYECTO_COMPLETO', 'PERSONALIZADO']),
  sobrescribir: z.boolean().default(false),
});

// Schema for bulk upload
const masivoSchema = z.object({
  archivo_zip: z
    .instanceof(File)
    .refine((file) => file.size <= MAX_FILE_SIZE, 'El archivo excede los 100 MB')
    .refine(
      (file) => file.name.toLowerCase().endsWith('.zip'),
      'Solo se aceptan archivos .zip'
    ),
  modo_consolidacion: z.enum(['SOLO_CODIGO', 'WEB_COMPLETO', 'PROYECTO_COMPLETO', 'PERSONALIZADO']),
  sobrescribir: z.boolean().default(false),
});

type IndividualFormData = z.infer<typeof individualSchema>;
type MasivoFormData = z.infer<typeof masivoSchema>;

const MODO_OPTIONS: { value: ModoConsolidacion; label: string; description: string }[] = [
  {
    value: 'SOLO_CODIGO',
    label: 'Solo código',
    description: '.py, .java, .js, .ts, .c, .cpp, .go',
  },
  {
    value: 'WEB_COMPLETO',
    label: 'Web completo',
    description: 'Código + .html, .css, .json',
  },
  {
    value: 'PROYECTO_COMPLETO',
    label: 'Proyecto completo',
    description: 'Código + .md, .txt, .yml, .xml',
  },
  {
    value: 'PERSONALIZADO',
    label: 'Personalizado',
    description: 'Define tus propias extensiones',
  },
];

// ========== UPLOAD RESULT VIEW ==========

function UploadResultView({
  uploadResult,
  onClose,
}: {
  uploadResult: CargaMasivaResponse;
  onClose: () => void;
}) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-muted p-4 rounded-lg text-center">
          <div className="text-2xl font-bold text-foreground">
            {uploadResult.total_procesadas}
          </div>
          <div className="text-sm text-muted-foreground">Procesadas</div>
        </div>
        <div className="bg-success/10 p-4 rounded-lg text-center">
          <div className="text-2xl font-bold text-success">
            {uploadResult.total_exitosas}
          </div>
          <div className="text-sm text-success">Exitosas</div>
        </div>
        <div className="bg-destructive/10 p-4 rounded-lg text-center">
          <div className="text-2xl font-bold text-destructive">
            {uploadResult.total_errores}
          </div>
          <div className="text-sm text-destructive">Errores</div>
        </div>
      </div>

      {/* Successful uploads */}
      {uploadResult.exitosas.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-foreground mb-2">
            Entregas exitosas ({uploadResult.exitosas.length})
          </h4>
          <div className="max-h-40 overflow-y-auto space-y-1">
            {uploadResult.exitosas.map((entrega, index) => (
              <div
                key={index}
                className="flex items-center gap-2 text-sm text-foreground bg-success/10 px-3 py-2 rounded"
              >
                <CheckCircle className="w-4 h-4 text-success flex-shrink-0" />
                <span className="flex-1">{entrega.alumno_nombre}</span>
                <span className="text-xs text-muted-foreground">{entrega.archivo_nombre}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Errors */}
      {uploadResult.errores.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-foreground mb-2">
            Errores ({uploadResult.errores.length})
          </h4>
          <div className="max-h-40 overflow-y-auto space-y-1">
            {uploadResult.errores.map((error, index) => (
              <div
                key={index}
                className="flex items-start gap-2 text-sm text-foreground bg-destructive/10 px-3 py-2 rounded"
              >
                <AlertCircle className="w-4 h-4 text-destructive flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="font-medium">{error.alumno_nombre}</div>
                  <div className="text-xs text-destructive">{error.error}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex justify-end pt-4 border-t">
        <Button onClick={onClose} variant="primary" className="w-full sm:w-auto">
          Cerrar
        </Button>
      </div>
    </div>
  );
}

// ========== CARGA FORM ==========
// Isolated in its own component so that key={cargaMode} remounts it on mode
// switch, giving useForm a fresh schema and clearing all local state.

// ========== CARGA FORM ==========
// Isolated in its own component so that key={cargaMode} remounts it on mode
// switch, giving useForm a fresh schema and clearing all local state.

function CargaEntregaForm({
  mode,
  comisionId,
  rubricaId,
  onClose,
  onResult,
}: {
  mode: CargaMode;
  comisionId: number;
  rubricaId: number;
  onClose: () => void;
  onResult: (result: CargaMasivaResponse) => void;
}) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  // Local state for custom extensions (separate from RHF because it's an array)
  const [extensionesPersonalizadas, setExtensionesPersonalizadas] = useState<string[]>([]);

  const createMutation = useCreateEntrega();
  const createMasivaMutation = useCreateEntregaMasiva();

  const schema = mode === 'individual' ? individualSchema : masivoSchema;

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
    control,
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      ...(mode === 'individual'
        ? { alumno_nombre: '', sobrescribir: false }
        : { sobrescribir: false }),
      modo_consolidacion: 'WEB_COMPLETO' as ModoConsolidacion,
    },
  });

  const modoConsolidacion = watch('modo_consolidacion');
  const isAlreadyConsolidated = mode === 'individual' && selectedFile?.name.toLowerCase().endsWith('.txt');
  const isZipFile = selectedFile?.name.toLowerCase().endsWith('.zip');
  const isPdfFile = mode === 'individual' && (selectedFile?.name.toLowerCase().endsWith('.pdf') ?? false);
  // Show processing mode selector only when the file will actually be consolidated
  const shouldShowModoProcessing =
    mode === 'masivo' ||
    (mode === 'individual' && isZipFile) ||
    (mode === 'individual' && !isPdfFile && !isAlreadyConsolidated && !!selectedFile);

  const handleFileChange = (file: File | null) => {
    setSelectedFile(file);
    if (file) {
      if (mode === 'individual') {
        setValue('archivo', file);
      } else {
        setValue('archivo_zip', file);
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileChange(files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileChange(files[0]);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const onSubmit = async (data: IndividualFormData | MasivoFormData) => {
    // Validate custom extensions when PERSONALIZADO is selected
    if (data.modo_consolidacion === 'PERSONALIZADO' && extensionesPersonalizadas.length === 0) {
      toast.error('Debes agregar al menos una extensión personalizada.');
      return;
    }

    try {
      if (mode === 'individual') {
        const individualData = data as IndividualFormData;
        await createMutation.mutateAsync({
          comision_id: comisionId,
          rubrica_id: rubricaId,
          alumno_nombre: individualData.alumno_nombre,
          archivo: individualData.archivo,
          modo_consolidacion: individualData.modo_consolidacion,
          extensiones_personalizadas:
            individualData.modo_consolidacion === 'PERSONALIZADO'
              ? extensionesPersonalizadas
              : undefined,
          sobrescribir: individualData.sobrescribir,
        });
        onClose();
      } else {
        const masivoData = data as MasivoFormData;
        const result = await createMasivaMutation.mutateAsync({
          comision_id: comisionId,
          rubrica_id: rubricaId,
          archivo_zip: masivoData.archivo_zip,
          modo_consolidacion: masivoData.modo_consolidacion,
          extensiones_personalizadas:
            masivoData.modo_consolidacion === 'PERSONALIZADO'
              ? extensionesPersonalizadas
              : undefined,
          sobrescribir: masivoData.sobrescribir,
        });
        onResult(result);
      }
    } catch {
      // Error handled by mutation onError
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Student name (individual only) */}
      {mode === 'individual' && (
        <div>
          <Input
            label="Nombre del Alumno"
            placeholder="Pérez, Juan"
            {...register('alumno_nombre')}
            error={(errors as any).alumno_nombre?.message}
            tooltip="Ingresa el nombre como aparecerá en los reportes"
            required
          />
        </div>
      )}

      {/* File upload dropzone */}
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">
          Archivo{mode === 'masivo' ? ' ZIP' : ''} *
        </label>
        <div
          className={`
            relative border-2 border-dashed rounded-lg p-6 text-center
            ${isDragging ? 'border-accent bg-accent/10' : 'border-input bg-muted'}
            ${selectedFile ? 'bg-card' : ''}
            hover:border-ring transition-colors cursor-pointer
          `}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input')?.click()}
        >
          <input
            id="file-input"
            type="file"
            accept={mode === 'individual' ? ACCEPTED_FILE_TYPES[mode] : ACCEPTED_FILE_TYPES[mode].join(',')}
            onChange={handleFileInputChange}
            className="hidden"
          />

          {selectedFile ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileUp className="w-8 h-8 text-accent" />
                <div className="text-left">
                  <div className="text-sm font-medium text-foreground">
                    {selectedFile.name}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatFileSize(selectedFile.size)}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleFileChange(null);
                }}
                className="p-1 hover:bg-muted rounded"
              >
                <X className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>
          ) : (
            <div>
              <Upload className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground mb-1">
                Arrastra un archivo aquí o haz clic
              </p>
              <p className="text-xs text-muted-foreground">
                {mode === 'individual'
                  ? 'Cualquier formato: .zip, .txt, .py, .java, .pdf, etc. (máx 100MB)'
                  : 'Formato: .zip (máx 100MB)'}
              </p>
            </div>
          )}
        </div>
        {(errors as any).archivo?.message && (
          <p className="mt-1 text-sm text-destructive">{(errors as any).archivo.message}</p>
        )}
        {(errors as any).archivo_zip?.message && (
          <p className="mt-1 text-sm text-destructive">{(errors as any).archivo_zip.message}</p>
        )}
      </div>

      {/* Consolidation mode or PDF notice */}
      {isAlreadyConsolidated ? (
        <div className="flex items-start gap-2 bg-success/10 border border-success/30 rounded-lg p-3">
          <CheckCircle className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-success">Archivo ya procesado</p>
            <p className="text-xs text-success mt-0.5">
              Este archivo TXT ya contiene el código procesado. No se requiere seleccionar modo de procesamiento.
            </p>
          </div>
        </div>
      ) : isPdfFile ? (
        <div className="flex items-start gap-2 bg-info/10 border border-info/30 rounded-lg p-3">
          <FileText className="w-5 h-5 text-info flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-info">Entrega en formato PDF</p>
            <p className="text-xs text-info mt-0.5">
              Este PDF se enviará directamente al flujo de corrección especializado. No se requiere modo de procesamiento.
            </p>
          </div>
        </div>
      ) : shouldShowModoProcessing ? (
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Modo de Procesamiento *
          </label>
          <Controller
            name="modo_consolidacion"
            control={control}
            render={({ field }) => (
              <div className="space-y-2">
                {MODO_OPTIONS.map((option) => (
                  <Radio
                    key={option.value}
                    id={`modo-${option.value}`}
                    label={option.label}
                    description={option.description}
                    value={option.value}
                    checked={field.value === option.value}
                    onChange={() => field.onChange(option.value)}
                  />
                ))}
              </div>
            )}
          />

          {/* Custom extensions input — only shown when PERSONALIZADO is selected */}
          {modoConsolidacion === 'PERSONALIZADO' && (
            <div className="mt-3 p-3 bg-muted border border-border rounded-lg">
              <label className="block text-sm font-medium text-foreground mb-1.5">
                Extensiones permitidas *
              </label>
              <ExtensionTagInput
                value={extensionesPersonalizadas}
                onChange={setExtensionesPersonalizadas}
                error={
                  extensionesPersonalizadas.length === 0
                    ? 'Agrega al menos una extensión para continuar'
                    : undefined
                }
              />
            </div>
          )}
        </div>
      ) : null}

      {/* Overwrite checkbox */}
      <div>
        <Checkbox
          label={
            mode === 'individual'
              ? 'Sobrescribir si ya existe una entrega del alumno'
              : 'Sobrescribir entregas existentes'
          }
          {...register('sobrescribir')}
        />
        <p className="mt-1 text-xs text-muted-foreground">
          {mode === 'individual'
            ? 'Si ya existe una entrega del mismo alumno, será reemplazada'
            : 'Las entregas de alumnos que ya subieron serán reemplazadas'}
        </p>
      </div>

      {/* Info alert for bulk upload */}
      {mode === 'masivo' && (
        <Alert variant="default">
          <p className="text-sm">
            <strong>Estructura esperada del ZIP:</strong> Una carpeta por alumno, donde el
            nombre de la carpeta es el nombre del alumno. Cada carpeta puede contener:
          </p>
          <ul className="text-sm mt-2 ml-4 list-disc space-y-1">
            <li>Un archivo ZIP con el proyecto (se descomprimirá y consolidará)</li>
            <li>Archivos sueltos (se consolidarán directamente según el modo seleccionado)</li>
          </ul>
        </Alert>
      )}

      {/* Footer */}
      <div className="flex flex-col-reverse gap-2 pt-4 border-t sm:flex-row sm:justify-end sm:gap-3">
        <Button type="button" variant="secondary" onClick={onClose} className="w-full sm:w-auto">
          Cancelar
        </Button>
        <Button
          type="submit"
          variant="primary"
          isLoading={createMutation.isPending || createMasivaMutation.isPending}
          disabled={!selectedFile}
          className="w-full sm:w-auto"
        >
          {mode === 'individual' ? 'Subir Entrega' : 'Subir Lote'}
        </Button>
      </div>
    </form>
  );
}

// ========== MAIN MODAL ==========

export const CargaEntregaModal = ({
  isOpen,
  onClose,
  comisionId,
  rubricaId,
}: CargaEntregaModalProps) => {
  const [cargaMode, setCargaMode] = useState<CargaMode>('individual');
  const [uploadResult, setUploadResult] = useState<CargaMasivaResponse | null>(null);

  const handleClose = () => {
    setCargaMode('individual');
    setUploadResult(null);
    onClose();
  };

  // Result screen after bulk upload
  if (uploadResult) {
    return (
      <Modal isOpen={isOpen} onClose={handleClose} title="Resultado de la carga">
        <UploadResultView uploadResult={uploadResult} onClose={handleClose} />
      </Modal>
    );
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Subir Entregas">
      {/* Modo de Carga — card picker (same pattern as RubricaEditor CREATION_MODES) */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-foreground mb-3">Modo de Carga</h3>
        <div className="grid grid-cols-2 gap-3">
          {CARGA_MODES.map((m) => {
            const Icon = m.icon;
            const isActive = cargaMode === m.id;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => setCargaMode(m.id)}
                className={cn(
                  'flex flex-col items-center p-4 rounded-lg transition-colors',
                  isActive
                    ? cn('border-2', m.activeBorder, m.activeBg)
                    : 'border border-border bg-card hover:bg-muted'
                )}
              >
                <Icon className={cn('h-6 w-6 mb-2', isActive ? m.activeText : 'text-muted-foreground')} />
                <span className={cn('text-sm font-medium', isActive ? m.activeText : 'text-foreground')}>
                  {m.label}
                </span>
                <span className="text-xs mt-0.5 text-center text-muted-foreground">
                  {m.description}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Form — key={cargaMode} remounts on switch, resetting form + file state */}
      <CargaEntregaForm
        key={cargaMode}
        mode={cargaMode}
        comisionId={comisionId}
        rubricaId={rubricaId}
        onClose={handleClose}
        onResult={setUploadResult}
      />
    </Modal>
  );
};
