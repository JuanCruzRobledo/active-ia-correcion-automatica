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
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useCreateEntrega, useCreateEntregaMasiva } from '../hooks';
import { Modal } from '@/shared/components/ui/Modal';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { Radio } from '@/shared/components/ui/Radio';
import { Checkbox } from '@/shared/components/ui/Checkbox';
import { Alert } from '@/shared/components/ui/Alert';
import { FileUp, Upload, PackageOpen, CheckCircle, AlertCircle, X } from 'lucide-react';
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
  individual: ['.zip', '.txt'],
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
    .refine((file) => file.size <= MAX_FILE_SIZE, 'El archivo excede los 100 MB')
    .refine(
      (file) =>
        ACCEPTED_FILE_TYPES.individual.some((ext) => file.name.toLowerCase().endsWith(ext)),
      'Solo se aceptan archivos .zip o .txt'
    ),
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
        <div className="bg-gray-50 p-4 rounded-lg text-center">
          <div className="text-2xl font-bold text-gray-900">
            {uploadResult.total_procesadas}
          </div>
          <div className="text-sm text-gray-600">Procesadas</div>
        </div>
        <div className="bg-green-50 p-4 rounded-lg text-center">
          <div className="text-2xl font-bold text-green-700">
            {uploadResult.total_exitosas}
          </div>
          <div className="text-sm text-green-600">Exitosas</div>
        </div>
        <div className="bg-red-50 p-4 rounded-lg text-center">
          <div className="text-2xl font-bold text-red-700">
            {uploadResult.total_errores}
          </div>
          <div className="text-sm text-red-600">Errores</div>
        </div>
      </div>

      {/* Successful uploads */}
      {uploadResult.exitosas.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-900 mb-2">
            Entregas exitosas ({uploadResult.exitosas.length})
          </h4>
          <div className="max-h-40 overflow-y-auto space-y-1">
            {uploadResult.exitosas.map((entrega, index) => (
              <div
                key={index}
                className="flex items-center gap-2 text-sm text-gray-700 bg-green-50 px-3 py-2 rounded"
              >
                <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
                <span className="flex-1">{entrega.alumno_nombre}</span>
                <span className="text-xs text-gray-500">{entrega.archivo_nombre}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Errors */}
      {uploadResult.errores.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-900 mb-2">
            Errores ({uploadResult.errores.length})
          </h4>
          <div className="max-h-40 overflow-y-auto space-y-1">
            {uploadResult.errores.map((error, index) => (
              <div
                key={index}
                className="flex items-start gap-2 text-sm text-gray-700 bg-red-50 px-3 py-2 rounded"
              >
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="font-medium">{error.alumno_nombre}</div>
                  <div className="text-xs text-red-600">{error.error}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex justify-end pt-4 border-t">
        <Button onClick={onClose} variant="primary">
          Cerrar
        </Button>
      </div>
    </div>
  );
}

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

  const createMutation = useCreateEntrega();
  const createMasivaMutation = useCreateEntregaMasiva();

  const schema = mode === 'individual' ? individualSchema : masivoSchema;

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
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
    try {
      if (mode === 'individual') {
        const individualData = data as IndividualFormData;
        await createMutation.mutateAsync({
          comision_id: comisionId,
          rubrica_id: rubricaId,
          alumno_nombre: individualData.alumno_nombre,
          archivo: individualData.archivo,
          modo_consolidacion: individualData.modo_consolidacion,
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
        <label className="block text-sm font-medium text-gray-700 mb-1.5">
          Archivo{mode === 'masivo' ? ' ZIP' : ''} *
        </label>
        <div
          className={`
            relative border-2 border-dashed rounded-lg p-6 text-center
            ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'}
            ${selectedFile ? 'bg-white' : ''}
            hover:border-gray-400 transition-colors cursor-pointer
          `}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input')?.click()}
        >
          <input
            id="file-input"
            type="file"
            accept={ACCEPTED_FILE_TYPES[mode].join(',')}
            onChange={handleFileInputChange}
            className="hidden"
          />

          {selectedFile ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileUp className="w-8 h-8 text-blue-600" />
                <div className="text-left">
                  <div className="text-sm font-medium text-gray-900">
                    {selectedFile.name}
                  </div>
                  <div className="text-xs text-gray-500">
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
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>
          ) : (
            <div>
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <p className="text-sm font-medium text-gray-700 mb-1">
                Arrastra un archivo aquí o haz clic
              </p>
              <p className="text-xs text-gray-500">
                {mode === 'individual'
                  ? 'Formatos: .zip, .txt (máx 100MB)'
                  : 'Formato: .zip (máx 100MB)'}
              </p>
            </div>
          )}
        </div>
        {(errors as any).archivo?.message && (
          <p className="mt-1 text-sm text-red-600">{(errors as any).archivo.message}</p>
        )}
        {(errors as any).archivo_zip?.message && (
          <p className="mt-1 text-sm text-red-600">{(errors as any).archivo_zip.message}</p>
        )}
      </div>

      {/* Consolidation mode */}
      {isAlreadyConsolidated ? (
        <div className="flex items-start gap-2 bg-green-50 border border-green-200 rounded-lg p-3">
          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-green-800">Archivo ya consolidado</p>
            <p className="text-xs text-green-600 mt-0.5">
              Este archivo TXT ya contiene el código consolidado. No se requiere seleccionar modo de consolidación.
            </p>
          </div>
        </div>
      ) : (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Modo de Consolidación *
          </label>
          <div className="space-y-2">
            {MODO_OPTIONS.map((option) => (
              <Radio
                key={option.value}
                label={option.label}
                description={option.description}
                value={option.value}
                checked={modoConsolidacion === option.value}
                {...register('modo_consolidacion')}
              />
            ))}
          </div>
        </div>
      )}

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
        <p className="mt-1 text-xs text-gray-500">
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
            nombre de la carpeta es el nombre del alumno. Cada carpeta puede contener un ZIP
            con el proyecto o archivos sueltos.
          </p>
        </Alert>
      )}

      {/* Footer */}
      <div className="flex justify-end gap-3 pt-4 border-t">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancelar
        </Button>
        <Button
          type="submit"
          variant="primary"
          isLoading={createMutation.isPending || createMasivaMutation.isPending}
          disabled={!selectedFile}
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
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Modo de Carga</h3>
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
