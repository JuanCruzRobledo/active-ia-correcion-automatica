"""
IA-011: OpenRouter parsea con json.loads directo, sin limpiar los fences de markdown.
Muchos modelos vía OpenRouter devuelven el JSON envuelto en ```json ... ```; el parse
falla, se lanza N8NError y se REINTENTA (duplicando el costo de tokens). Se limpia el
fence como red de seguridad antes de json.loads.
"""

import json

from app.integrations.openrouter_client import _strip_json_fences


def test_json_plano_no_cambia():
    txt = '{"nota": 90}'
    assert json.loads(_strip_json_fences(txt)) == {"nota": 90}


def test_fence_json_se_limpia():
    txt = '```json\n{"nota": 90}\n```'
    assert json.loads(_strip_json_fences(txt)) == {"nota": 90}


def test_fence_sin_lenguaje_se_limpia():
    txt = '```\n{"nota": 85}\n```'
    assert json.loads(_strip_json_fences(txt)) == {"nota": 85}


def test_texto_con_espacios_alrededor():
    txt = '  \n```json\n{"nota": 70}\n```  \n'
    assert json.loads(_strip_json_fences(txt)) == {"nota": 70}


def test_texto_con_prosa_antes_del_json():
    """Algunos modelos anteponen 'Aquí está la corrección:' antes del bloque."""
    txt = 'Aquí está la corrección:\n```json\n{"nota": 60}\n```'
    assert json.loads(_strip_json_fences(txt)) == {"nota": 60}
