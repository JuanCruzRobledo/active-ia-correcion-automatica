# Bugfix Requirements Document

## Introduction

Las comisiones se ordenan y agrupan por **orden alfabético (lexicográfico)** en lugar de por
**orden numérico natural**. Los nombres de comisión siguen el patrón `<prefijo>-<número>`
(por ejemplo `COMI-1`, `COMI-2`, … `COMI-27`), y al ordenarlos como texto los números con
distinta cantidad de dígitos quedan intercalados de forma incorrecta.

Comportamiento observado (incorrecto):

```
COMI-1, COMI-10, COMI-11, …, COMI-2, COMI-20, COMI-21, …, COMI-3
```

Comportamiento esperado (correcto):

```
COMI-1, COMI-2, COMI-3, …, COMI-10, …, COMI-20, …, COMI-27
```

El defecto se origina en un mismo tipo de raíz —ordenar el nombre de comisión como cadena de
texto— y se manifiesta en las superficies donde las comisiones se listan o se agrupan por
nombre:

- **Excel de cierre de cursada:** los bloques por comisión se agrupan/ordenan alfabéticamente
  por nombre de comisión (superficie principal reportada por el usuario: "agrupando").
- **Listado / gestión de comisiones:** el listado de comisiones se ordena alfabéticamente por
  nombre.
- **Corrida de cierre de cursada:** el detalle de alumnos se ordena por nombre de comisión como
  texto.
- **Reporte de avance:** las filas se ordenan por nombre de comisión como texto.

El impacto es de presentación/usabilidad: las comisiones aparecen desordenadas para el usuario,
dificultando la lectura de listados y reportes cuando hay más de 9 comisiones.

> **Contexto:** La spec previa `cierre-cursada-comision-nota-fix` (Bug 3) fijó deliberadamente el
> orden de los bloques de comisión del Excel como **alfabético**. Ese orden alfabético es
> justamente el que produce este defecto para nombres con sufijo numérico de distinta longitud
> (`COMI-10` antes que `COMI-2`). Este fix reemplaza el criterio alfabético por un orden natural
> numérico, manteniendo intactas las demás garantías de aquel fix (bloque "Sin comisión asignada"
> al final y orden intra-bloque de alumnos por Apellido, Nombre).

## Bug Analysis

### Current Behavior (Defect)

Lo que ocurre hoy cuando se dispara el bug.

1.1 WHEN se listan comisiones cuyos nombres terminan en un número y esos números tienen distinta cantidad de dígitos (ej. `COMI-2` y `COMI-10`) THEN el sistema las ordena lexicográficamente, ubicando `COMI-10`, `COMI-11`, … antes de `COMI-2`.

1.2 WHEN se genera el Excel de cierre de cursada con comisiones cuyos nombres tienen sufijo numérico de distinta longitud THEN el sistema agrupa/ordena los bloques por comisión alfabéticamente, ubicando el bloque `COMI-10` antes del bloque `COMI-2`.

1.3 WHEN se listan los alumnos de una corrida de cierre de cursada THEN el sistema los ordena por nombre de comisión como texto, agrupando `COMI-10` antes de `COMI-2`.

1.4 WHEN se genera el reporte de avance THEN el sistema ordena las filas por nombre de comisión como texto, ubicando `COMI-10` antes de `COMI-2`.

### Expected Behavior (Correct)

Lo que debería ocurrir en cada una de las condiciones anteriores.

2.1 WHEN se listan comisiones cuyos nombres terminan en un número THEN el sistema SHALL ordenarlas por el valor numérico natural de ese sufijo (`COMI-1, COMI-2, COMI-3, …, COMI-10, …, COMI-27`), no por su representación textual.

2.2 WHEN se genera el Excel de cierre de cursada con varias comisiones THEN el sistema SHALL agrupar/ordenar los bloques por comisión según el orden numérico natural del nombre de comisión (`COMI-1` … `COMI-27`).

2.3 WHEN se listan los alumnos de una corrida de cierre de cursada THEN el sistema SHALL ordenarlos agrupando las comisiones por orden numérico natural del nombre de comisión.

2.4 WHEN se genera el reporte de avance THEN el sistema SHALL ordenar las filas agrupando las comisiones por orden numérico natural del nombre de comisión.

### Unchanged Behavior (Regression Prevention)

Comportamiento existente que debe preservarse.

3.1 WHEN los nombres de comisión NO contienen un sufijo numérico (nombres puramente alfabéticos) THEN el sistema SHALL CONTINUE TO ordenarlos alfabéticamente como hoy.

3.2 WHEN dos comisiones comparten el mismo prefijo y el mismo número (o nombres idénticos) THEN el sistema SHALL CONTINUE TO resolver el desempate con el criterio secundario existente (ej. año) sin alterar el resultado actual.

3.3 WHEN se listan comisiones en el listado general THEN el sistema SHALL CONTINUE TO usar el año descendente (`anio desc`) como criterio de orden primario, aplicando el orden numérico natural del nombre únicamente como criterio secundario.

3.4 WHEN se genera el Excel de cierre de cursada y existe el bloque "Sin comisión asignada" THEN el sistema SHALL CONTINUE TO ubicarlo SIEMPRE al final, después de todos los bloques de comisiones reales.

3.5 WHEN se escriben los alumnos DENTRO de un bloque de comisión del Excel o en un reporte THEN el sistema SHALL CONTINUE TO ordenarlos alfabéticamente por (Apellido, Nombre) como hoy.

3.6 WHEN una comisión o alumno no tiene nombre de comisión asignado (valor nulo) THEN el sistema SHALL CONTINUE TO ubicarlo al final (`nulls last`) sin interrumpir el listado ni la generación del reporte.

3.7 WHEN el usuario aplica filtros o paginación en el listado de comisiones (materia, año, tutor, coordinador, página) THEN el sistema SHALL CONTINUE TO respetarlos sin cambios; sólo cambia el criterio de orden por nombre.
