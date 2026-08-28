# Respuesta de Active-IA a AI-Native

**Fecha:** 28 de agosto de 2026
**Responde a:** su documento del 28/08

---

> **Lo más importante primero:** el token opaco **no lo construyan**. No nos serviría, y el
> motivo es de nuestro lado — está en el §2. Correlacionamos sólo los públicos, que es lo que
> ustedes ya mandan hoy sin tocar nada.

---

## 1. Su bug del `_mapear`: gracias por decirlo, y nos hizo encontrar uno nuestro

Que lo hayan informado sin que nadie lo pidiera vale más que el arreglo.

Y confirma algo incómodo: **el mismo camino estaba roto de los dos lados, al mismo tiempo, con los
tests en verde de los dos lados.** Ustedes mandaban un objeto vacío; nosotros descartábamos en
silencio el único campo que importaba. Ninguno de los dos bugs producía un error.

### Lo que su bug destapó de nuestro lado

Fuimos a ver qué hacíamos nosotros con ese payload
(`{compila: true, error_compilacion: null, total: 0, pasados: 0, casos: []}`). Esto le mandábamos
al motor, bajo un encabezado que dice HECHO ESTABLECIDO:

```
## RESULTADO DE EJECUCIÓN (HECHO ESTABLECIDO)
...NO vuelvas a deducir si el programa funciona: ya está respondido.

El código compila. Casos superados: 0 de 0.
```

Las dos líneas juntas son lo peor posible. **«0 de 0» se lee como que no pasó nada**, cuando en
realidad no se midió nada. Y la orden de dejar de deducir le apaga al motor el juicio propio sin
darle nada con qué reemplazarlo.

`total: 0` con `casos: []` no es una medición con resultado cero: **es la ausencia de una
medición.** Ya está corregido. Ahora esa sección declara que cubre sólo la compilación, dice
explícitamente que no se ejecutaron casos, y le devuelve la pregunta del comportamiento al motor
pidiéndole que la juzgue leyendo el código — sin interpretar la falta de casos ni como éxito ni
como fracaso.

Que **no compile** no entra en esa rama: es un hecho completo por sí solo, no necesita casos que
lo respalden, y el cierre determinístico de criterios depende de él. Hay un test que fija esa
simetría para que nadie la rompa después.

El arreglo sobrevive al de ustedes: protege contra cualquier cliente que alguna vez mande una
corrida sin evidencia, por el motivo que sea.

---

## 2. El `id`: correlacionamos sólo los públicos, y el token opaco no hace falta

Su respuesta cierra la pregunta, y la parte que agregaron sin que la preguntáramos —que
`hidden-N` es **posicional sobre el orden de corrida**— es la que decide el asunto. Coincidimos
palabra por palabra con cómo lo plantearon:

> Correlacionar por posición sería peor que no correlacionar, porque fallaría en silencio y en el
> sentido más caro: describiendo el caso equivocado en la devolución de un alumno.

**No construyan el token.** Es una oferta generosa y no la vamos a usar, por una razón que está
de nuestro lado y que no podían saber:

**Un caso oculto no tiene `salida_esperada` en nuestra base.** Nuestro schema la rechaza al
publicar — no la limpia en silencio, falla. Y `salida_esperada` era exactamente lo único que la
correlación iba a buscar: queríamos mostrarle al motor contra qué se comparaba.

O sea que el token nos permitiría llegar a un registro que, para un caso oculto, está vacío en el
campo que nos interesa. Trabajo real de su lado para abrir una puerta a un cuarto sin nada
adentro.

**Vamos con la opción que ya funciona:** correlacionar sólo los públicos, sin que ustedes toquen
nada. Los ocultos siguen aportando su veredicto a la nota y no se citan en la devolución, que es
como debe ser.

---

## 3. Un hueco nuestro que su §3 nos hizo mirar

Revisando lo anterior encontramos algo que conviene que sepan, porque es sobre la protección de
**sus** casos ocultos.

Nuestro validador rechaza `salida_esperada` y `asercion` en un caso oculto. **Pero permite
`entrada`.**

Y `entrada` revela qué prueba el caso igual que la salida: un caso oculto cuya entrada es
`cupo=-1` ya dijo qué está probando. Contradice el principio que el propio validador declara —
«lo que el motor nunca recibió no lo puede citar»— y estábamos a un cambio de volverlo un
problema real, porque la correlación por `id` es justamente lo que iba a llevar definiciones al
prompt.

Hoy no es un bug activo: nada manda `entrada` al motor. Pero queremos cerrarlo.

**La pregunta, porque es su camino de publicación:** ¿hoy publican casos ocultos con `entrada`?
Si la respuesta es no, endurecemos el validador y listo. Si es sí, coordinamos para no romperles
la publicación en medio de la integración.

---

## 4. La cuenta de coordinador: tienen razón, es nuestro freno

No vamos a discutir esto. Es nuestro y está pendiente.

Y su argumento es el correcto:

> Los dos equipos teníamos un bug en el mismo camino, los dos con los tests en verde, y ninguno de
> los dos lo vio hasta que el otro miró.

Un doble HTTP escrito leyendo documentos verifica lo que el que lo escribió entendió. Los dos
bugs de este intercambio vivían exactamente ahí: en la distancia entre el documento y el
productor real. Ninguna cantidad de tests de un solo lado los encuentra.

---

## 5. Qué queda de cada lado

| Quién | Qué |
|---|---|
| **Active-IA** | Corrida sin evidencia: ya no se afirma como hecho establecido |
| **Active-IA** | Correlación por `id` sólo de casos públicos |
| **Active-IA** | La cuenta de coordinador para staging — pendiente, es el freno |
| **AI-Native** | **No** construir el token opaco (§2) |
| **AI-Native** | Responder si publican casos ocultos con `entrada` (§3) |
