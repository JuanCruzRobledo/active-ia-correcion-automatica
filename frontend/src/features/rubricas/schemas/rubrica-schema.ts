// features/rubricas/schemas/rubrica-schema.ts
/**
 * Zod validation schemas for Rubricas.
 *
 * Validates the structure of rubricas including:
 * - Sum of pesos = 100
 * - Unique IDs at all levels
 * - Non-empty evidencias
 * - Valid descuento_porcentaje (0-100)
 *
 * Ref: docs/specs/Rubrica.md
 */

import { z } from 'zod';

// ============================================================================
// Schema Validators
// ============================================================================

export const subcriterioSchema = z.object({
  id: z
    .string()
    .min(1, 'ID del subcriterio es requerido')
    .regex(/^[A-Z0-9]+\.[0-9]+$/, 'ID debe tener formato C1.1, C2.3, etc.'),
  descripcion: z.string().min(1, 'Descripción es requerida'),
  evidencias: z
    .array(z.string().min(1, 'Evidencia no puede estar vacía'))
    .min(1, 'Debe haber al menos una evidencia'),
});

export const criterioSchema = z.object({
  id: z
    .string()
    .min(1, 'ID del criterio es requerido')
    .regex(/^[A-Z0-9]+$/, 'ID debe tener formato C1, C2, etc.'),
  nombre: z.string().min(1, 'Nombre es requerido').max(100),
  descripcion: z.string().min(1, 'Descripción es requerida').max(500),
  peso: z
    .number()
    .min(1, 'Peso debe ser al menos 1')
    .max(100, 'Peso no puede exceder 100'),
  instrucciones_puntuacion: z.string().max(500).optional(),
  subcriterios: z
    .array(subcriterioSchema)
    .min(1, 'Debe haber al menos un subcriterio'),
});

export const penalizacionSchema = z.object({
  id: z
    .string()
    .min(1, 'ID de penalización es requerido')
    .regex(/^P[0-9]+$/, 'ID debe tener formato P1, P2, etc.'),
  descripcion: z.string().min(1, 'Descripción es requerida').max(500),
  descuento_porcentaje: z
    .number()
    .min(0, 'Descuento no puede ser negativo')
    .max(100, 'Descuento no puede exceder 100'),
});

export const condicionDesaprobacionSchema = z.object({
  id: z
    .string()
    .min(1, 'ID de condición es requerido')
    .regex(/^CD[0-9]+$/, 'ID debe tener formato CD1, CD2, etc.'),
  condicion: z.string().min(1, 'Condición es requerida').max(500),
  nota_final: z
    .number()
    .min(0, 'Nota final no puede ser negativa')
    .max(100, 'Nota final no puede exceder 100'),
});

export const criteriosStructureSchema = z
  .object({
    titulo: z.string().min(1, 'Título es requerido').max(200),
    descripcion: z.string().min(1, 'Descripción es requerida'),
    puntaje_maximo: z
      .number()
      .int()
      .refine(
        (val) => val === 100,
        { message: 'El puntaje máximo debe ser exactamente 100' }
      ),
    metadata: z.record(z.string(), z.any()).default({}),
    criterios: z.array(criterioSchema).min(1, 'Debe haber al menos un criterio'),
    penalizaciones: z.array(penalizacionSchema).default([]),
    condiciones_desaprobacion: z
      .array(condicionDesaprobacionSchema)
      .default([]),
  })
  .superRefine((data, ctx) => {
    // Validar suma de pesos = 100
    const sumaPesos = data.criterios.reduce((sum, c) => sum + c.peso, 0);
    if (sumaPesos !== 100) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `La suma de pesos de criterios (${sumaPesos}) debe ser exactamente 100`,
        path: ['criterios'],
      });
    }

    // Validar IDs únicos de criterios
    const criterioIds = data.criterios.map((c) => c.id);
    const uniqueCriterioIds = new Set(criterioIds);
    if (criterioIds.length !== uniqueCriterioIds.size) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Los IDs de criterios deben ser únicos',
        path: ['criterios'],
      });
    }

    // Validar IDs únicos de subcriterios dentro de cada criterio
    data.criterios.forEach((criterio, idx) => {
      const subcriterioIds = criterio.subcriterios.map((s) => s.id);
      const uniqueSubIds = new Set(subcriterioIds);
      if (subcriterioIds.length !== uniqueSubIds.size) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Los IDs de subcriterios en ${criterio.id} deben ser únicos`,
          path: ['criterios', idx, 'subcriterios'],
        });
      }
    });

    // Validar IDs únicos de penalizaciones
    if (data.penalizaciones && data.penalizaciones.length > 0) {
      const penIds = data.penalizaciones.map((p) => p.id);
      const uniquePenIds = new Set(penIds);
      if (penIds.length !== uniquePenIds.size) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Los IDs de penalizaciones deben ser únicos',
          path: ['penalizaciones'],
        });
      }
    }

    // Validar IDs únicos de condiciones
    if (
      data.condiciones_desaprobacion &&
      data.condiciones_desaprobacion.length > 0
    ) {
      const condIds = data.condiciones_desaprobacion.map((c) => c.id);
      const uniqueCondIds = new Set(condIds);
      if (condIds.length !== uniqueCondIds.size) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Los IDs de condiciones de desaprobación deben ser únicos',
          path: ['condiciones_desaprobacion'],
        });
      }
    }
  });

// ============================================================================
// Rubrica Create/Update Validators
// ============================================================================

export const rubricaCreateSchema = z.object({
  materia_id: z.number().int().positive('Materia ID es requerido'),
  tipo: z.enum([
    'TP',
    'PARCIAL_1',
    'PARCIAL_2',
    'RECUPERATORIO_1',
    'RECUPERATORIO_2',
    'FINAL',
    'GLOBAL',
  ]),
  numero: z.number().int().min(1, 'Número debe ser al menos 1'),
  anio: z
    .number()
    .int()
    .min(2020, 'Año debe ser al menos 2020')
    .max(2100, 'Año no puede exceder 2100'),
  titulo: z.string().min(1, 'Título es requerido').max(200),
  descripcion: z.string().min(1, 'Descripción es requerida'),
  puntaje_maximo: z.number().int().default(100),
  metadata_json: z.record(z.string(), z.any()).default({}),
  criterios_json: z
    .array(criterioSchema)
    .min(1, 'Debe haber al menos un criterio'),
  penalizaciones_json: z.array(penalizacionSchema).default([]),
  condiciones_desaprobacion_json: z
    .array(condicionDesaprobacionSchema)
    .default([]),
  fuente: z.enum(['manual', 'pdf']).default('manual'),
  archivo_original: z.string().optional(),
});

export const rubricaUpdateSchema = z.object({
  titulo: z.string().min(1).max(200).optional(),
  descripcion: z.string().min(1).optional(),
  metadata_json: z.record(z.string(), z.any()).optional(),
  criterios_json: z.array(criterioSchema).min(1).optional(),
  penalizaciones_json: z.array(penalizacionSchema).optional(),
  condiciones_desaprobacion_json: z.array(condicionDesaprobacionSchema).optional(),
});

export const rubricaDuplicarSchema = z.object({
  nuevo_anio: z
    .number()
    .int()
    .min(2020, 'Año debe ser al menos 2020')
    .max(2100, 'Año no puede exceder 2100'),
  nuevo_titulo: z.string().min(1).max(200).optional(),
});

// ============================================================================
// Type exports for form validation
// ============================================================================

export type SubcriterioFormData = z.infer<typeof subcriterioSchema>;
export type CriterioFormData = z.infer<typeof criterioSchema>;
export type PenalizacionFormData = z.infer<typeof penalizacionSchema>;
export type CondicionDesaprobacionFormData = z.infer<
  typeof condicionDesaprobacionSchema
>;
export type CriteriosStructureFormData = z.infer<typeof criteriosStructureSchema>;
export type RubricaCreateFormData = z.infer<typeof rubricaCreateSchema>;
export type RubricaUpdateFormData = z.infer<typeof rubricaUpdateSchema>;
export type RubricaDuplicarFormData = z.infer<typeof rubricaDuplicarSchema>;
