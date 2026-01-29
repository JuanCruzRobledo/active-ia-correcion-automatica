// shared/utils/date.ts
/**
 * Date formatting utilities
 */

/**
 * Format ISO date string to readable format
 * @param isoDate - ISO 8601 date string
 * @returns Formatted date string (DD/MM/YYYY)
 */
export const formatDate = (isoDate: string): string => {
  const date = new Date(isoDate);
  
  if (isNaN(date.getTime())) {
    return 'Fecha inválida';
  }

  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();

  return `${day}/${month}/${year}`;
};

/**
 * Format ISO date string to readable datetime format
 * @param isoDate - ISO 8601 date string
 * @returns Formatted datetime string (DD/MM/YYYY HH:MM)
 */
export const formatDateTime = (isoDate: string): string => {
  const date = new Date(isoDate);
  
  if (isNaN(date.getTime())) {
    return 'Fecha inválida';
  }

  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');

  return `${day}/${month}/${year} ${hours}:${minutes}`;
};

/**
 * Get relative time string (e.g., "hace 2 horas")
 * @param isoDate - ISO 8601 date string
 * @returns Relative time string
 */
export const getRelativeTime = (isoDate: string): string => {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'hace un momento';
  if (diffMins < 60) return `hace ${diffMins} minuto${diffMins > 1 ? 's' : ''}`;
  if (diffHours < 24) return `hace ${diffHours} hora${diffHours > 1 ? 's' : ''}`;
  if (diffDays < 7) return `hace ${diffDays} día${diffDays > 1 ? 's' : ''}`;
  
  return formatDate(isoDate);
};
