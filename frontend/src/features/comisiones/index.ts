// features/comisiones/index.ts
/**
 * Public API for comisiones feature
 */

// Types
export type {
  Comision,
  ComisionDetail,
  ComisionListItem,
  ComisionList,
  ComisionCreate,
  ComisionUpdate,
  TutorInfo,
  MateriaInfo,
  TutoresAssign,
  TutoresResponse,
  ComisionesFilters,
} from './types';

// Hooks
export {
  useComisiones,
  useComision,
  useCreateComision,
  useUpdateComision,
  useDeleteComision,
  useRestoreComision,
  useAssignTutores,
} from './hooks';

// Services (usually not exported, but available if needed)
export { comisionesService } from './services';

// Pages
export { ComisionesPage } from './pages';

// Components
export { ComisionForm } from './components';
