# Active-IA → AI-Native: las cuentas están, faltan tres cosas

**Fecha:** 28 de agosto de 2026
**Asunto:** cuentas de coordinador entregadas · qué necesitamos para encender

---

> **Las dos cuentas de coordinador ya están entregadas.** Son **dos**, una por universidad, y no
> una sola como habíamos hablado: el motivo está en el §1 y les afecta directamente el cliente.
>
> Para que puedan publicar y corregir nos faltan **tres cosas de ustedes**, y una es un dato que
> sólo existe en su base.

---

## 1. Por qué son dos cuentas y no una

Pidieron una cuenta para las dos universidades. La probamos y **no funciona**, por algo que está
de nuestro lado y que conviene que sepan porque el síntoma cae en su cliente.

Nuestro `/auth/login` **cambia de forma** según cuántas membresías tenga la cuenta:

| Membresías | Qué devuelve |
|---|---|
| 1 | `TokenResponse` con `access_token` |
| **2 o más** | `{universidades: [...], token_transicion: ...}` — **sin `access_token`** |

Y su cliente hace esto (`activeia_client.py`):

```python
token = resp.json().get("access_token")
if not token:
    raise ...("Active-IA aceptó el login pero no devolvió token", es_infraestructura=True)
```

**Lo clasifican como falla de infraestructura**, o sea reintentable. Pero esa infraestructura no
se recupera nunca: el login va a seguir devolviendo la selección de universidad. Reintento
indefinido, con la causa equivocada.

### Y lo peor no es eso

**No se rompería al momento de agregar la segunda membresía.** El token ya emitido lleva adentro
la universidad activa y sigue funcionando. Anda todo bien hasta que ese token expire (7 días) o
se coma un 401 — ahí su cliente hace re-login y entra en el loop.

O sea: funciona una semana y revienta un martes a la madrugada sin que nadie haya tocado nada.

### Por qué dos cuentas es además la opción correcta

No es sólo esquivar el bug. Con **una** cuenta y dos membresías, que no se crucen las
universidades depende de que ustedes llamen a `/auth/switch-universidad` en el momento justo.
Con **dos** cuentas, un token **no puede** alcanzar la otra universidad ni con un error de ruteo
de su lado. El aislamiento deja de depender de la disciplina.

Si prefieren igual la cuenta única, se puede: implican manejar `requiere_seleccion` y llamar a
`/auth/seleccionar-universidad`. Es código nuevo en su camino de autenticación, y nos parece mal
momento — todavía no lograron correr una corrección punta a punta.

---

## 2. Lo que necesitamos: el `materia_id` de la materia del piloto

**Este es el bloqueante.** Sin él, su `PUT /trabajos-practicos/by-ref/{ref}` devuelve **404**.

Fuimos a su código antes de preguntar. En `activeia_sync.py`:

```python
"materia_external_ref": str(tp["materia_id"]) if tp["materia_id"] else None,
```

Es el id interno de la materia en **su** base. Y el motivo que documentaron nos parece correcto:

> pedir un `materia_id` de Active-IA obligaría a mantener acá un mapeo de ids ajenos que vencen
> sin avisar

De acuerdo. Pero la consecuencia es que ese valor **no lo podemos elegir ni adivinar**: tenemos
que crear la materia de nuestro lado con exactamente el string que ustedes van a mandar. Si no
coincide, su PUT sigue dando 404 y desde acá se ve idéntico a "no configuramos nada".

**Lo que les pedimos:** el `materia_id` de la materia del piloto (hablaron de *Paradigmas*, TP1
E1-E3 y TP2 E1-E4). **Uno por universidad**, si de su lado son materias distintas. Si es la misma
materia sirviendo a las dos, mándenlo una vez y avísennos: nuestro modelo lo soporta, porque la
unicidad del `external_ref` es por universidad.

---

## 3. Verifiquen el login de las dos cuentas

Un `POST /auth/login` con cada una, y miren la respuesta:

- Viene `access_token` → esa cuenta está bien.
- Viene `universidades[]` → esa cuenta quedó con las dos membresías. Avísennos y la corregimos
  **antes** de que entren en el loop del §1.

Es un minuto y evita el martes a la madrugada.

---

## 4. Sigue sin respuesta: `entrada` en los casos ocultos

Del documento de ayer, §3. Lo repetimos porque es su camino de publicación y no queremos
endurecer un validador que les rompa la publicación en medio de la integración.

Nuestro schema rechaza `salida_esperada` y `asercion` en un caso oculto, **pero permite
`entrada`**. Y una entrada como `cupo=-1` revela qué prueba el caso igual que la salida.

**¿Hoy publican casos ocultos con `entrada`?** Si es no, lo cerramos y listo.

---

## 5. Qué queda de cada lado

| Quién | Qué |
|---|---|
| **Active-IA** | Hecho: dos cuentas de coordinador entregadas |
| **Active-IA** | Configurar materia, vínculo, comisión de integración — **en cuanto tengamos el §2** |
| **AI-Native** | El `materia_id` del piloto, por universidad (§2) |
| **AI-Native** | Verificar el login de las dos cuentas (§3) |
| **AI-Native** | Responder lo de `entrada` en casos ocultos (§4) |
| **AI-Native** | **No** construir el token opaco — sigue en pie lo de ayer |

Con el §2 en la mano, la configuración de nuestro lado es una corrida de script por universidad.
El mismo día que lo manden pueden publicar.
