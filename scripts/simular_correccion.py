#!/usr/bin/env python3
"""
Simulador de corrección — espejo en Python del nodo "Construir Body Gemini"
del workflow n8n `correccion-workflow.json` (estado YA CORREGIDO).

Sirve para:
  1. Ver el PROMPT exacto que el nodo arreglado le manda a Gemini
     (con subcriterios + evidencias + instrucciones_puntuación + metadata +
      penalizaciones + condiciones de desaprobación).
  2. Opcionalmente llamar a Gemini y obtener la corrección, para comparar
     contra la corrección real que produce n8n sobre la misma entrega.

Es deliberadamente self-contained: solo usa la stdlib (urllib + json + argparse).
No importa nada del backend ni necesita la DB.

Ref: n8n/workflows/correccion-workflow.json (nodo "Construir Body Gemini")
Ref: fix-workflow-correccion-active-ia.md

Uso:
  # Solo imprimir el prompt (sin llamar a Gemini):
  python scripts/simular_correccion.py --rubrica rub.json --codigo entrega.txt --print-prompt

  # Correr la corrección de verdad (necesita API key de Gemini):
  export GEMINI_API_KEY=...            # o pasar --api-key
  python scripts/simular_correccion.py --rubrica rub.json --codigo entrega.txt \
      --materia "Programación 1" --alumno "Juan Pérez"

  # Smoke test con datos de ejemplo embebidos:
  python scripts/simular_correccion.py --ejemplo --print-prompt
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# Modelo por defecto. OJO: el nodo n8n usa otro nombre de modelo (al momento de
# escribir esto, producción usa "gemini-3.5-flash" y el archivo versionado
# "gemini-3.1-flash-lite-preview"). Para que la comparación contra n8n sea justa,
# alineá este valor con el modelo que tenga el nodo "Gemini: Corregir".
DEFAULT_MODEL = "gemini-2.5-flash"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


# ============================================================================
# Construcción del prompt — espejo EXACTO del nodo "Construir Body Gemini"
# ============================================================================


def _criterios_texto(rubrica: dict[str, Any]) -> str:
    """Criterios con subcriterios + evidencias + instrucciones de puntuación."""
    texto = ""
    for criterio in rubrica.get("criterios", []):
        texto += (
            f"- ID: {criterio.get('id')}\n"
            f"  Nombre: {criterio.get('nombre')}\n"
            f"  Peso: {criterio.get('peso')} pts\n"
            f"  Descripción: {criterio.get('descripcion')}\n"
        )
        if criterio.get("instrucciones_puntuacion"):
            texto += f"  Instrucciones de puntuación: {criterio['instrucciones_puntuacion']}\n"
        subcriterios = criterio.get("subcriterios") or []
        if subcriterios:
            texto += "  Evidencias esperadas (checklist verificable en la entrega):\n"
            for sub in subcriterios:
                if sub.get("descripcion"):
                    texto += f"  - {sub['descripcion']}\n"
                for evidencia in sub.get("evidencias") or []:
                    texto += f"    * {evidencia}\n"
        texto += "\n"
    return texto


def _metadata_texto(rubrica: dict[str, Any]) -> str:
    """Contexto de metadata de la rúbrica (lenguaje, framework, formato, etc.)."""
    texto = ""
    metadata = rubrica.get("metadata")
    if isinstance(metadata, dict):
        for clave, valor in metadata.items():
            texto += f"- {clave}: {valor}\n"
    return texto


def _penalizaciones_texto(rubrica: dict[str, Any]) -> str:
    texto = ""
    for p in rubrica.get("penalizaciones") or []:
        texto += (
            f"- ID: {p.get('id')}\n"
            f"  Descripción: {p.get('descripcion')}\n"
            f"  Descuento: {p.get('descuento_porcentaje')}%\n\n"
        )
    return texto


def _nota_maxima_cd(cd: dict[str, Any]) -> Any:
    """La rúbrica nueva usa `nota_maxima`; versiones viejas usan `nota_final`."""
    return cd.get("nota_maxima", cd.get("nota_final", 0))


def _condiciones_texto(rubrica: dict[str, Any]) -> str:
    texto = ""
    for cd in rubrica.get("condiciones_desaprobacion") or []:
        texto += (
            f"- ID: {cd.get('id')}\n"
            f"  Condición: {cd.get('condicion')}\n"
            f"  Nota máxima permitida: {_nota_maxima_cd(cd)}\n\n"
        )
    return texto


def build_prompt(codigo: str, rubrica: dict[str, Any], contexto: dict[str, Any]) -> str:
    """Arma el prompt completo, espejando el nodo n8n arreglado."""
    criterios_texto = _criterios_texto(rubrica)
    metadata_texto = _metadata_texto(rubrica)
    penalizaciones_texto = _penalizaciones_texto(rubrica)
    condiciones_texto = _condiciones_texto(rubrica)

    cds = rubrica.get("condiciones_desaprobacion") or []
    pens = rubrica.get("penalizaciones") or []

    cd_lista = (
        "\n".join(
            f"   - {cd.get('id')}: {cd.get('condicion')} → Si se cumple, nota máxima = {_nota_maxima_cd(cd)}"
            for cd in cds
        )
        if cds
        else "   Ninguna."
    )
    pen_lista = (
        "\n".join(
            f"   - {p.get('id')}: {p.get('descripcion')} → Descuento del {p.get('descuento_porcentaje')}% sobre la nota"
            for p in pens
        )
        if pens
        else "   Ninguna."
    )

    puntaje_maximo = rubrica.get("puntaje_maximo", 100)

    return f"""Eres un evaluador experto de trabajos prácticos de programación para la materia "{contexto.get('materia')}".

Tu tarea es evaluar el siguiente código del alumno "{contexto.get('alumno')}" según la rúbrica proporcionada.

## RÚBRICA DE EVALUACIÓN

Título: {rubrica.get('titulo')}
Tipo: {rubrica.get('tipo')}
Puntaje máximo: {puntaje_maximo}

Criterios:
{criterios_texto}

## CONTEXTO ADICIONAL

{metadata_texto or 'Sin metadata adicional.'}

## PENALIZACIONES

Estas penalizaciones se aplican SOBRE el puntaje obtenido en los criterios. Evalúa si alguna aplica al código entregado.
{penalizaciones_texto or 'Ninguna definida.'}

## CONDICIONES DE DESAPROBACIÓN

IMPORTANTE: Estas condiciones establecen un TECHO (nota máxima) para la calificación. Si CUALQUIERA de ellas se cumple, la nota final NO PUEDE SUPERAR el máximo indicado. La nota final será el MÍNIMO entre la suma de criterios y la nota máxima de la condición. Evalúa cada condición cuidadosamente.
{condiciones_texto or 'Ninguna definida.'}

## CÓDIGO DEL ALUMNO

```
{codigo}
```

## INSTRUCCIONES DE EVALUACIÓN

1. Primero, evalúa cada criterio de la rúbrica normalmente (puntaje y feedback), verificando las evidencias esperadas de cada criterio contra el código entregado.
2. Luego, verifica si alguna CONDICIÓN DE DESAPROBACIÓN se cumple:
{cd_lista}
3. Luego, verifica si alguna PENALIZACIÓN aplica:
{pen_lista}
4. Calcula la nota final:
   - Calcula nota_antes_penalizaciones = suma de puntajes de los criterios.
   - Si aplica alguna condición de desaprobación → nota = min(nota_antes_penalizaciones, nota_maxima_de_la_condicion). Es decir, la nota no puede superar el techo.
   - Si aplica alguna penalización → aplica el descuento porcentual sobre nota_antes_penalizaciones.
   - Si no aplica nada → nota = nota_antes_penalizaciones.

Para cada criterio:
1. DEBES incluir el ID exacto del criterio de la rúbrica
2. Asigna un puntaje entre 0 y el peso del criterio
3. Determina el estado:
   - "OK" si logra ≥80% del peso del criterio
   - "WARNING" si logra 40-79% del peso
   - "ERROR" si logra <40% del peso
4. Proporciona feedback específico y constructivo

Además:
- Lista 2-4 fortalezas del código (array de strings)
- Lista 2-4 recomendaciones de mejora específicas (array de strings)
- Escribe un comentario general de 2-3 oraciones

## FORMATO DE RESPUESTA OBLIGATORIO

Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:

{{
  "nota": <número entre 0 y {puntaje_maximo}>,
  "condicion_desaprobacion_aplicada": <null si no aplica, o el ID de la condición que aplica (ej: "CD1")>,
  "penalizaciones_aplicadas": [<array de IDs de penalizaciones aplicadas, vacío si ninguna>],
  "nota_antes_penalizaciones": <número: suma de criterios antes de aplicar condiciones o penalizaciones>,
  "criterios": [
    {{
      "id": "<ID exacto del criterio de la rúbrica>",
      "nombre": "<nombre exacto del criterio de la rúbrica>",
      "puntaje_obtenido": <número>,
      "puntaje_maximo": <número igual al peso del criterio>,
      "estado": "<OK|WARNING|ERROR>",
      "feedback": "<feedback específico>"
    }}
  ],
  "fortalezas": ["<fortaleza 1>", "<fortaleza 2>"],
  "recomendaciones": ["<recomendación 1>", "<recomendación 2>"],
  "comentario_general": "<comentario de 2-3 oraciones>"
}}

IMPORTANTE:
- CADA criterio debe tener su ID exacto de la rúbrica
- Si aplica una condición de desaprobación, "nota" debe ser min(suma_criterios, nota_maxima_de_la_condicion), pero IGUAL debes evaluar todos los criterios con su puntaje real para dar feedback
- Si aplica una penalización, "nota" debe reflejar el descuento aplicado sobre "nota_antes_penalizaciones"
- Si no aplica ni condición ni penalización, "nota" = "nota_antes_penalizaciones" = suma de puntajes
- Cada criterio de la rúbrica debe aparecer en la respuesta
- NO incluyas texto antes o después del JSON"""


# ============================================================================
# Body de Gemini + responseSchema — espejo del nodo
# ============================================================================


def build_gemini_body(prompt: str) -> dict[str, Any]:
    """Body de la request a Gemini, con el mismo responseSchema que el nodo."""
    return {
        "generationConfig": {
            "temperature": 0,
            "topK": 1,
            "topP": 1,
            "candidateCount": 1,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "object",
                "properties": {
                    "nota": {"type": "number"},
                    "condicion_desaprobacion_aplicada": {"type": "string", "nullable": True},
                    "penalizaciones_aplicadas": {"type": "array", "items": {"type": "string"}},
                    "nota_antes_penalizaciones": {"type": "number"},
                    "criterios": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "nombre": {"type": "string"},
                                "puntaje_obtenido": {"type": "number"},
                                "puntaje_maximo": {"type": "number"},
                                "estado": {"type": "string", "enum": ["OK", "WARNING", "ERROR"]},
                                "feedback": {"type": "string"},
                            },
                            "required": [
                                "id",
                                "nombre",
                                "puntaje_obtenido",
                                "puntaje_maximo",
                                "estado",
                                "feedback",
                            ],
                        },
                    },
                    "fortalezas": {"type": "array", "items": {"type": "string"}},
                    "recomendaciones": {"type": "array", "items": {"type": "string"}},
                    "comentario_general": {"type": "string"},
                },
                "required": [
                    "nota",
                    "condicion_desaprobacion_aplicada",
                    "penalizaciones_aplicadas",
                    "nota_antes_penalizaciones",
                    "criterios",
                    "fortalezas",
                    "recomendaciones",
                    "comentario_general",
                ],
            },
        },
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }


# ============================================================================
# Llamada a Gemini + parseo — espejo del nodo "Parsear Respuesta"
# ============================================================================


def call_gemini(body: dict[str, Any], api_key: str, model: str) -> dict[str, Any]:
    """POST a la API de Gemini. Devuelve el JSON crudo de la respuesta."""
    url = GEMINI_URL.format(model=model, key=api_key)
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        cuerpo = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(cuerpo)
        except json.JSONDecodeError:
            return {"error": {"code": exc.code, "message": cuerpo}}


def parse_response(gemini_response: dict[str, Any]) -> dict[str, Any]:
    """Parsea la respuesta de Gemini espejando el nodo 'Parsear Respuesta'."""
    if gemini_response.get("error"):
        err = gemini_response["error"]
        return {
            "success": False,
            "error": {
                "code": "GEMINI_ERROR",
                "message": f"Error de Gemini [{err.get('code', 'UNKNOWN')}]: {err.get('message', err)}",
            },
        }

    candidate = (gemini_response.get("candidates") or [{}])[0]
    text_content = (candidate.get("content", {}).get("parts") or [{}])[0].get("text")
    if not text_content:
        return {"success": False, "error": {"code": "PARSING_ERROR", "message": "Sin texto en la respuesta"}}

    try:
        parsed = json.loads(text_content)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": {"code": "PARSING_ERROR", "message": f"JSON inválido: {exc}"}}

    # Validación de consistencia (igual que el nodo):
    suma = sum(c.get("puntaje_obtenido", 0) for c in parsed.get("criterios", []))
    parsed["nota_antes_penalizaciones"] = suma

    cd_aplicada = parsed.get("condicion_desaprobacion_aplicada")
    pens_aplicadas = parsed.get("penalizaciones_aplicadas") or []

    if cd_aplicada and parsed.get("nota", 0) > suma:
        parsed["nota"] = suma
    if not cd_aplicada and not pens_aplicadas:
        parsed["nota"] = suma

    return {"success": True, "correccion": parsed}


# ============================================================================
# Datos de ejemplo (smoke test)
# ============================================================================

RUBRICA_EJEMPLO: dict[str, Any] = {
    "titulo": "TP2 - API REST de Productos",
    "descripcion": "API REST con Express.js y validaciones",
    "tipo": "TP",
    "puntaje_maximo": 100,
    "metadata": {"materia": "Programación Backend", "lenguaje": "JavaScript", "framework": "Express.js"},
    "criterios": [
        {
            "id": "C1",
            "nombre": "Estructura del proyecto",
            "descripcion": "Organización de archivos y configuración inicial",
            "peso": 40,
            "instrucciones_puntuacion": "Dividir proporcionalmente entre subcriterios",
            "subcriterios": [
                {
                    "id": "C1.1",
                    "descripcion": "package.json con dependencias correctas",
                    "evidencias": ["Archivo package.json existe", "Dependencia express presente"],
                }
            ],
        },
        {
            "id": "C2",
            "nombre": "Endpoints CRUD",
            "descripcion": "Implementación de endpoints REST",
            "peso": 60,
            "subcriterios": [
                {
                    "id": "C2.1",
                    "descripcion": "Endpoint de creación",
                    "evidencias": ["POST /productos retorna 201", "Valida body de entrada"],
                }
            ],
        },
    ],
    "penalizaciones": [
        {"id": "P1", "descripcion": "Repositorio privado o inaccesible", "descuento_porcentaje": 100}
    ],
    "condiciones_desaprobacion": [
        {"id": "CD1", "condicion": "No implementa al menos 3 endpoints CRUD", "nota_maxima": 30}
    ],
}

CODIGO_EJEMPLO = """// index.js
const express = require('express');
const app = express();
app.use(express.json());

const productos = [];

app.post('/productos', (req, res) => {
  const { nombre } = req.body;
  if (!nombre) return res.status(400).json({ error: 'nombre requerido' });
  const producto = { id: productos.length + 1, nombre };
  productos.push(producto);
  res.status(201).json(producto);
});

app.listen(3000);
"""


# ============================================================================
# CLI
# ============================================================================


def _leer_archivo_o_texto(valor: str) -> str:
    """Si `valor` es un path existente, lee el archivo; si no, lo trata como texto."""
    if os.path.isfile(valor):
        with open(valor, encoding="utf-8") as fh:
            return fh.read()
    return valor


def main() -> int:
    # La consola de Windows (cp1252) no traga caracteres como → o ≥; forzamos UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Simulador de corrección (espejo del nodo n8n)")
    parser.add_argument("--rubrica", help="Path a un JSON con la rúbrica (estructura de RubricaResponse/criterios)")
    parser.add_argument("--codigo", help="Path al código de la entrega, o el texto directo")
    parser.add_argument("--materia", default="Materia de prueba")
    parser.add_argument("--alumno", default="Alumno de prueba")
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY"))
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Modelo Gemini (default: {DEFAULT_MODEL})")
    parser.add_argument("--print-prompt", action="store_true", help="Solo imprime el prompt; no llama a Gemini")
    parser.add_argument("--ejemplo", action="store_true", help="Usa rúbrica + código de ejemplo embebidos")
    parser.add_argument("--out", help="Path donde guardar la corrección JSON resultante")
    args = parser.parse_args()

    # Resolver rúbrica + código
    if args.ejemplo:
        rubrica = RUBRICA_EJEMPLO
        codigo = CODIGO_EJEMPLO
    else:
        if not args.rubrica or not args.codigo:
            parser.error("Se requieren --rubrica y --codigo (o usá --ejemplo)")
        with open(args.rubrica, encoding="utf-8") as fh:
            rubrica = json.load(fh)
        # Una RubricaResponse del backend trae los campos como *_json; normalizamos.
        rubrica = _normalizar_rubrica(rubrica)
        codigo = _leer_archivo_o_texto(args.codigo)

    contexto = {"materia": args.materia, "alumno": args.alumno}
    prompt = build_prompt(codigo, rubrica, contexto)

    if args.print_prompt:
        print(prompt)
        return 0

    if not args.api_key:
        print(
            "ERROR: falta la API key de Gemini. Pasá --api-key o seteá GEMINI_API_KEY.\n"
            "       (o usá --print-prompt para solo ver el prompt sin llamar a la API)",
            file=sys.stderr,
        )
        return 2

    print(f"→ Llamando a Gemini (modelo: {args.model})...", file=sys.stderr)
    inicio = time.time()
    body = build_gemini_body(prompt)
    respuesta_cruda = call_gemini(body, args.api_key, args.model)
    resultado = parse_response(respuesta_cruda)
    resultado.setdefault("metadata", {})["tiempo_ms"] = int((time.time() - inicio) * 1000)
    resultado["metadata"]["modelo"] = args.model

    salida = json.dumps(resultado, ensure_ascii=False, indent=2)
    print(salida)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(salida)
        print(f"\n✓ Guardado en {args.out}", file=sys.stderr)

    return 0 if resultado.get("success") else 1


def _normalizar_rubrica(rubrica: dict[str, Any]) -> dict[str, Any]:
    """Acepta tanto el formato del payload n8n como una RubricaResponse del backend.

    El backend expone los campos como `*_json` (criterios_json, metadata_json, etc.);
    el payload a n8n usa los nombres pelados. Acá los unificamos a los pelados.
    """
    return {
        "titulo": rubrica.get("titulo"),
        "descripcion": rubrica.get("descripcion") or "",
        "tipo": rubrica.get("tipo"),
        "puntaje_maximo": rubrica.get("puntaje_maximo", 100),
        "metadata": rubrica.get("metadata") or rubrica.get("metadata_json") or {},
        "criterios": rubrica.get("criterios") or rubrica.get("criterios_json") or [],
        "penalizaciones": rubrica.get("penalizaciones") or rubrica.get("penalizaciones_json") or [],
        "condiciones_desaprobacion": (
            rubrica.get("condiciones_desaprobacion")
            or rubrica.get("condiciones_desaprobacion_json")
            or []
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
