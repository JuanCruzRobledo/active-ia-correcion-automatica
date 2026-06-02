import type { ReactNode } from 'react';

/**
 * Contenido de ayuda por página (centralizado).
 * Se consume con <HelpButton content={helpContent.<clave>} />.
 */
export const helpContent: Record<string, ReactNode> = {
  gestion: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Gestión</p>

      <p>
        Esta pantalla te deja consultar los alumnos de un curso de Moodle y descargar
        reportes en Excel. Primero elegí un curso; recién ahí se habilitan los filtros y
        las descargas.
      </p>

      <p className="font-medium text-foreground">Filtros</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Rol:</strong> Estudiante, Profesor o Profesor sin permiso de edición.</li>
        <li><strong className="text-foreground">Estatus:</strong> Activo o Inactivo (matriculación suspendida).</li>
        <li><strong className="text-foreground">Regional / Comisión:</strong> se arman solas con los grupos reales del curso; podés elegir varias.</li>
        <li>
          <strong className="text-foreground">Inactividad:</strong> por <em>bandas cerradas</em> sobre el último acceso al curso.
          "1 mes" trae 30-59 días; "2 meses" 60 o más; "Nunca" = jamás ingresó. No es acumulativo.
        </li>
      </ul>

      <p className="font-medium text-foreground">Acciones</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Consultar:</strong> muestra en pantalla los alumnos que cumplen los filtros.</li>
        <li><strong className="text-foreground">Excel para Nexos:</strong> una hoja por <em>Regional</em> (ordenado por comisión).</li>
        <li><strong className="text-foreground">Excel para Tutores:</strong> una hoja por <em>Comisión</em> (ordenado por regional).</li>
        <li><strong className="text-foreground">Pendientes por Práctico:</strong> entregas hechas en Moodle sin corregir, una hoja por trabajo.</li>
        <li><strong className="text-foreground">Pendientes por Comisión:</strong> lo mismo, una hoja por comisión, con el <strong className="text-foreground">tutor</strong> a cargo.</li>
      </ul>

      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Tip:</p>
        <p className="mt-1 text-sm">
          Mientras una descarga o consulta está en curso, los botones se deshabilitan: es a
          propósito, para no saturar Moodle con muchas consultas a la vez. Esperá a que el
          botón deje de estar en "Generando…" antes de pedir otro reporte.
        </p>
      </div>
    </div>
  ),

  dashboard: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Dashboard</p>
      <p>Tu panel de inicio con métricas y accesos rápidos según tu rol.</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Estadísticas:</strong> un resumen de lo tuyo (sistema, materias o comisiones según el rol).</li>
        <li><strong className="text-foreground">Accesos rápidos:</strong> atajos a las acciones más frecuentes.</li>
        <li><strong className="text-foreground">Actividad reciente:</strong> últimas acciones registradas.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Nota:</p>
        <p className="mt-1 text-sm">El contenido cambia según tu rol (Administrador, Coordinador o Tutor).</p>
      </div>
    </div>
  ),

  usuarios: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Usuarios</p>
      <p>Administrá las cuentas del sistema y sus roles.</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Crear / editar:</strong> alta de usuarios y cambio de nombre o rol.</li>
        <li><strong className="text-foreground">Roles:</strong> Admin, Coordinador, Tutor o Gestor — definen a qué accede cada uno.</li>
        <li><strong className="text-foreground">Activar / desactivar:</strong> baja lógica (no se borra; se puede restaurar).</li>
        <li><strong className="text-foreground">Reset de contraseña:</strong> genera una contraseña temporal.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Nota:</p>
        <p className="mt-1 text-sm">Asigná el rol "Gestor" a quienes necesiten la pantalla de Gestión.</p>
      </div>
    </div>
  ),

  materias: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Materias</p>
      <p>Las materias (cursos) de la institución y su vínculo con Moodle.</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Crear / editar:</strong> código y nombre de la materia.</li>
        <li><strong className="text-foreground">Vincular a Moodle:</strong> el "ID del curso de Moodle" conecta la materia con sus entregas.</li>
        <li><strong className="text-foreground">Activar / desactivar:</strong> baja lógica reversible.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Importante:</p>
        <p className="mt-1 text-sm">El ID del curso de Moodle se guarda al EDITAR la materia, no al crearla.</p>
      </div>
    </div>
  ),

  comisiones: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Comisiones</p>
      <p>Las comisiones de cada materia y los tutores a cargo.</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Crear / editar:</strong> nombre, año y estado de la comisión.</li>
        <li><strong className="text-foreground">Tutores:</strong> asignás uno o varios tutores a cada comisión.</li>
        <li><strong className="text-foreground">Grupo de Moodle:</strong> vincula la comisión con su grupo para traer entregas y pendientes.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Nota:</p>
        <p className="mt-1 text-sm">Sin el grupo de Moodle vinculado, la comisión no aparece en Pendientes.</p>
      </div>
    </div>
  ),

  rubricas: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Rúbricas</p>
      <p>Los criterios de evaluación por materia (TP, parciales, recuperatorios).</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Crear / editar:</strong> criterios, puntajes, tipo y número.</li>
        <li><strong className="text-foreground">Generar por PDF o manual:</strong> cargás la consigna o la armás a mano.</li>
        <li><strong className="text-foreground">Vincular assignment de Moodle:</strong> conecta la rúbrica con las entregas a corregir.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Nota:</p>
        <p className="mt-1 text-sm">El assignment de Moodle es lo que permite importar y corregir las entregas de esa rúbrica.</p>
      </div>
    </div>
  ),

  entregas: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Entregas</p>
      <p>Las entregas de los alumnos y su corrección con IA.</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Filtrar:</strong> por comisión, rúbrica y estado.</li>
        <li><strong className="text-foreground">Corregir con IA:</strong> evalúa la entrega contra la rúbrica.</li>
        <li><strong className="text-foreground">Ver y subir:</strong> revisás el código/PDF y subís la nota a Moodle.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Tip:</p>
        <p className="mt-1 text-sm">Configurá tu API key de Google Gemini en tu perfil para poder corregir.</p>
      </div>
    </div>
  ),

  pendientes: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Pendientes Moodle</p>
      <p>Lo que falta corregir en Moodle, agrupado por materia y comisión.</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Esperando / Corregidos / Sin entrega:</strong> el estado de cada comisión.</li>
        <li><strong className="text-foreground">Importar:</strong> trae las entregas pendientes a Active-IA para corregirlas.</li>
        <li><strong className="text-foreground">Solo con pendientes:</strong> filtra para ver únicamente lo que falta.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Nota:</p>
        <p className="mt-1 text-sm">Consulta Moodle en vivo: necesitás tus credenciales Moodle configuradas en el perfil.</p>
      </div>
    </div>
  ),

  porEntregar: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Por entregar</p>
      <p>Correcciones hechas en Active-IA que todavía no subiste a Moodle.</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Entregar todo:</strong> sube en bloque las TP (comentario automático).</li>
        <li><strong className="text-foreground">Subir individual:</strong> desde cada fila, con vista previa de la nota.</li>
        <li><strong className="text-foreground">Requieren comentario:</strong> las no-TP se suben a mano con el texto del tutor.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Nota:</p>
        <p className="mt-1 text-sm">Esta lista es local (instantánea); solo se consulta Moodle al subir.</p>
      </div>
    </div>
  ),

  perfil: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Mi Perfil</p>
      <p>Tu configuración personal e integraciones.</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">API key de Gemini:</strong> necesaria para corregir entregas con IA.</li>
        <li><strong className="text-foreground">Credenciales Moodle:</strong> host, usuario y contraseña para Pendientes y Gestión.</li>
        <li><strong className="text-foreground">Cambiar contraseña:</strong> de tu cuenta de Active-IA.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Importante:</p>
        <p className="mt-1 text-sm">Tus credenciales se guardan encriptadas. Sin Gemini no podés corregir; sin Moodle no ves pendientes.</p>
      </div>
    </div>
  ),
};
