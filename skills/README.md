# Skills - Active-IA

Sistema de skills modulares para agentes de IA trabajando en el proyecto Active-IA.

## Concepto

Los skills son unidades de conocimiento que los agentes de IA cargan según el contexto del trabajo que están realizando. Cada skill contiene:

- Patrones y convenciones específicas
- Reglas críticas (ALWAYS/NEVER)
- Ejemplos de código
- Decision trees

## Skills Disponibles

| Skill | Descripción | Scope |
|-------|-------------|-------|
| [python-fastapi](python-fastapi/SKILL.md) | Patrones FastAPI + Clean Architecture | root, backend |
| [react-typescript](react-typescript/SKILL.md) | Patrones React + TypeScript + Tailwind | root, frontend |
| [correccion-ia](correccion-ia/SKILL.md) | Flujo de corrección automática con Gemini | root, backend |
| [rubricas](rubricas/SKILL.md) | Gestión de rúbricas y criterios | root, backend |
| [skill-sync](skill-sync/SKILL.md) | Sincroniza metadata a AGENTS.md | root |
| [skill-creator](skill-creator/SKILL.md) | Crea nuevos skills desde template | root |

## Estructura de un Skill

```
skills/{skill-name}/
├── SKILL.md              # REQUERIDO - Instrucciones del skill
└── assets/               # OPCIONAL - Templates, scripts, ejemplos
    └── ...
```

## Crear un Nuevo Skill

1. Crear directorio:
   ```bash
   mkdir -p skills/mi-skill/assets
   ```

2. Copiar template:
   ```bash
   cp skills/skill-creator/assets/SKILL-TEMPLATE.md skills/mi-skill/SKILL.md
   ```

3. Editar `SKILL.md` con el contenido específico

4. Sincronizar:
   ```bash
   ./skills/skill-sync/assets/sync.sh
   ```

## Configurar AI Assistants

```bash
./setup.sh --all        # Todos los assistants
./setup.sh --claude     # Solo Claude Code
./setup.sh --codex      # Solo Codex
./setup.sh --copilot    # Solo GitHub Copilot
./setup.sh --gemini     # Solo Gemini CLI
```

## Frontmatter YAML

Cada `SKILL.md` debe comenzar con:

```yaml
---
name: skill-name
description: >
  Qué hace este skill.
  Trigger: Cuándo debe cargarse.
metadata:
  scope: [root, frontend, backend]
  auto_invoke:
    - "Action that triggers this skill"
---
```

### Campos

| Campo | Requerido | Descripción |
|-------|-----------|-------------|
| `name` | Sí | Identificador único |
| `description` | Sí | Qué hace + cuándo usarlo |
| `metadata.scope` | Sí | Array: `root`, `frontend`, `backend` |
| `metadata.auto_invoke` | Sí | Acciones que activan el skill |
