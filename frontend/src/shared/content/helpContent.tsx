import type { ReactNode } from 'react';

/**
 * Contenido de ayuda por página (centralizado).
 * Se consume con <HelpButton content={helpContent.<clave>} />.
 */
export const helpContent: Record<string, ReactNode> = {
  notificaciones: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Notificaciones por email</p>
      <p>
        Una vez por semana, de forma automática, se envían las actividades faltantes a tres
        destinatarios distintos:
      </p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Alumno:</strong> una tabla en el cuerpo del email con sus materias.</li>
        <li><strong className="text-foreground">Tutor académico:</strong> un PDF con los alumnos de sus comisiones.</li>
        <li><strong className="text-foreground">Tutor nexo:</strong> un Excel con los alumnos de su regional.</li>
      </ul>
      <p>
        El cron refresca los snapshots (con el usuario de servicio) y después envía los 3 tipos
        en cadena. Antes de activarlo, usá <strong className="text-foreground">Enviar prueba</strong> y la{' '}
        <strong className="text-foreground">vista previa</strong> para revisar los formatos, y{' '}
        <strong className="text-foreground">Disparar ahora</strong> para una corrida manual de control.
      </p>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Ojo:</p>
        <p className="mt-1 text-sm">
          En modo sandbox (sin dominio verificado) Resend solo entrega a la casilla de tu cuenta.
          Para enviar a todos, primero hay que verificar el dominio.
        </p>
      </div>
    </div>
  ),

  tutoresNexo: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Tutores Nexo</p>
      <p>
        El tutor nexo recibe semanalmente, por email, un{' '}
        <strong className="text-foreground">Excel</strong> con los alumnos de su{' '}
        <strong className="text-foreground">regional</strong> y las actividades que les faltan
        (una hoja por materia).
      </p>
      <ul className="ml-4 list-disc space-y-2">
        <li>
          <strong className="text-foreground">Regional:</strong> escribila como aparece en
          Moodle pero <strong className="text-foreground">sin el prefijo "R-"</strong>. Ej: el
          grupo <em>R-Mendoza</em> → cargás <em>Mendoza</em>.
        </li>
        <li>
          <strong className="text-foreground">Email:</strong> casilla donde recibe el Excel.
        </li>
        <li>
          <strong className="text-foreground">Activo:</strong> solo los activos reciben el envío
          semanal.
        </li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Ojo:</p>
        <p className="mt-1 text-sm">
          La regional debe coincidir exactamente con el nombre del grupo de Moodle (sin "R-"),
          o no se le asignará ningún alumno.
        </p>
      </div>
    </div>
  ),

  cohortes: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Cohortes</p>
      <p>
        Las cohortes (ej. <strong className="text-foreground">M26</strong> = marzo 2026,
        <strong className="text-foreground"> A25</strong> = agosto 2025) agrupan a los alumnos
        por su ingreso. Cada cohorte tiene cuatrimestres, y a cada cuatrimestre se le vinculan
        materias. El <strong className="text-foreground">dashboard de gestores</strong> usa esta
        estructura para sus selectores.
      </p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Nueva cohorte:</strong> definí el código (no se cambia después) y un nombre opcional.</li>
        <li><strong className="text-foreground">Cuatrimestres:</strong> agregá del 1 al 4 con el botón "Agregar"; quitalos con la ✕.</li>
        <li><strong className="text-foreground">Vincular materias:</strong> eso se hace desde cada materia (config de dashboard), no acá.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Ojo:</p>
        <p className="mt-1 text-sm">
          No se puede eliminar una cohorte o un cuatrimestre que tenga materias vinculadas.
          Primero desvinculá las materias.
        </p>
      </div>
    </div>
  ),

  dashboardGestor: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Avance académico</p>
      <p>
        Muestra cómo vienen los alumnos respecto a la unidad que se está cursando. Elegí
        cohorte, cuatrimestre y (opcional) una materia; el gráfico de torta refleja el estado.
      </p>
      <p className="font-medium text-foreground">Estados</p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-success">Al día:</strong> alcanzó (o superó) la unidad actual.</li>
        <li><strong className="text-warning">Riesgo medio:</strong> una unidad atrás.</li>
        <li><strong className="text-destructive">Riesgo alto:</strong> dos o más unidades atrás.</li>
        <li><strong className="text-foreground">Sin actividad:</strong> no completó ninguna actividad.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Tips:</p>
        <p className="mt-1 text-sm">
          Hacé clic en una porción para ver el detalle de esos alumnos (con su actividad actual).
          Los datos vienen de un snapshot diario; la fecha de actualización se muestra arriba del gráfico.
        </p>
      </div>
    </div>
  ),

  cronConfig: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Snapshots / Cron</p>
      <p>
        El dashboard de gestores lee una "foto" (snapshot) del avance de los alumnos, no
        consulta Moodle en vivo. Esa foto se genera 1×/día con el cron, o a mano con el botón.
      </p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Usuario:</strong> de quién se usan las credenciales de Moodle para consultar. Debe tenerlas configuradas en su perfil.</li>
        <li><strong className="text-foreground">Hora:</strong> a qué hora (Argentina) corre el cron, una vez por día.</li>
        <li><strong className="text-foreground">Cron activo:</strong> prendelo solo cuando el usuario y las materias estén configurados.</li>
        <li><strong className="text-foreground">Generar ahora:</strong> dispara el cálculo a mano (con tus credenciales). Puede tardar varios minutos.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Ojo:</p>
        <p className="mt-1 text-sm">
          No se puede activar el cron sin un usuario con credenciales de Moodle. El botón
          manual es temporal (para pruebas).
        </p>
      </div>
    </div>
  ),

  materiaDashboard: (
    <div className="space-y-4 text-sm text-muted-foreground">
      <p className="text-lg font-semibold text-foreground">Configuración del dashboard</p>
      <p>
        Acá preparás una materia para que aparezca en el dashboard de gestores: la vinculás a
        un cuatrimestre, definís en qué unidad se está cursando y mapeás sus unidades a las
        secciones de Moodle.
      </p>
      <ul className="ml-4 list-disc space-y-2">
        <li><strong className="text-foreground">Cohorte + Cuatrimestre:</strong> a qué grupo pertenece la materia.</li>
        <li><strong className="text-foreground">Unidad actual:</strong> la unidad que se está dictando hoy (con esto se calcula el riesgo).</li>
        <li><strong className="text-foreground">Detectar desde Moodle:</strong> trae TODAS las secciones del curso con un check cada una. Tildá las que son unidades reales (descartá "Actividades", "Práctica", etc.); el orden de arriba hacia abajo define el número de unidad. "Guardar unidades" reemplaza el set.</li>
        <li><strong className="text-foreground">Tope:</strong> la sección donde terminan las unidades de contenido — lo posterior (parciales, integrador) no cuenta para el avance.</li>
      </ul>
      <div className="mt-4 rounded-lg bg-muted/50 p-4">
        <p className="font-medium text-warning">Para que la materia aparezca en el dashboard:</p>
        <p className="mt-1 text-sm">
          necesita curso de Moodle vinculado, cuatrimestre, unidad actual y al menos una unidad mapeada.
        </p>
      </div>
    </div>
  ),

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
