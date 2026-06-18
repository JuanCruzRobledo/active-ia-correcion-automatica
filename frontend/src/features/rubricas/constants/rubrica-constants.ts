import { PenLine, FileText, Code } from 'lucide-react';
import type { TipoRubrica } from '../types';

export const TIPO_LABELS: Record<TipoRubrica, string> = {
  TP: 'Trabajo Práctico',
  TPI: 'Trabajo Práctico Integrador',
  PARCIAL_1: 'Parcial 1',
  PARCIAL_2: 'Parcial 2',
  RECUPERATORIO_1: 'Recuperatorio 1',
  RECUPERATORIO_2: 'Recuperatorio 2',
  FINAL: 'Final',
  GLOBAL: 'Global',
};

export type CreationMode = 'manual' | 'pdf' | 'json';

export const CREATION_MODES: {
  id: CreationMode;
  icon: typeof PenLine;
  label: string;
  description: string;
  activeBorder: string;
  activeText: string;
  activeBg: string;
}[] = [
  {
    id: 'pdf',
    icon: FileText,
    label: 'Desde PDF',
    description: 'Extrae criterios con IA',
    activeBorder: 'border-success',
    activeText: 'text-success',
    activeBg: 'bg-success/10',
  },
  {
    id: 'json',
    icon: Code,
    label: 'Desde JSON',
    description: 'Carga desde archivo JSON',
    activeBorder: 'border-warning',
    activeText: 'text-warning',
    activeBg: 'bg-warning/10',
  },
  {
    id: 'manual',
    icon: PenLine,
    label: 'Manual',
    description: 'Define criterios manualmente',
    activeBorder: 'border-accent',
    activeText: 'text-accent',
    activeBg: 'bg-accent/10',
  },
];

export const JSON_EXAMPLE = `{
  "titulo": "Nombre corto que identifica la rúbrica",
  "descripcion": "Qué tipo de trabajo evalúa y con qué objetivo",
  "puntaje_maximo": 100,

  "metadata": {
    "campoLibre": "Información contextual útil para entender el trabajo",
    "otroCampoOpcional": "La metadata es libre y puede tener cualquier clave necesaria"
  },

  // La suma de criterios[].peso debe ser 100
  "criterios": [
    {
      "id": "Identificador único del criterio (ej: C1)",
      "nombre": "Nombre breve del criterio evaluado",
      "descripcion": "Qué aspecto general del trabajo se evalúa",
      "peso": 100,

      "subcriterios": [
        {
          "id": "Identificador del subcriterio (ej: C1.1)",
          "descripcion": "Aspecto específico y verificable",
          "evidencias": [
            "Condición concreta que la IA debe comprobar"
          ]
        }
      ]
    }
  ],

  "penalizaciones": [
    {
      "id": "Identificador de la penalización",
      "descripcion": "Situación que genera un descuento automático",
      "descuento_porcentaje": 0
    }
  ],

  "condiciones_desaprobacion": [
    {
      "id": "Identificador de la condición",
      "condicion": "Regla que provoca desaprobación directa",
      "nota_maxima": 0
    }
  ]
}`;
