---
name: skill-creator
description: >
  Crea nuevos skills desde un template estandarizado.
  Trigger: Cuando necesites crear un nuevo skill para el proyecto.
metadata:
  author: Active-IA Team
  version: "1.0"
  scope: [root]
  auto_invoke:
    - "Creating new skills"
---

# Skill Creator

## When to Use

- Creando un nuevo skill para el proyecto
- Necesitas agregar patrones específicos para una tecnología
- Quieres documentar convenciones de un módulo

## Step by Step

### 1. Crear directorio

```bash
mkdir -p skills/{skill-name}/assets
```

### 2. Copiar template

```bash
cp skills/skill-creator/assets/SKILL-TEMPLATE.md skills/{skill-name}/SKILL.md
```

### 3. Editar SKILL.md

Completar:
- Frontmatter YAML (name, description, scope, auto_invoke)
- When to Use
- Critical Patterns (ALWAYS/NEVER)
- Decision Trees
- Code Examples
- Commands
- Resources

### 4. Agregar assets (opcional)

Si el skill necesita templates o ejemplos:
```bash
# Agregar archivos a assets/
skills/{skill-name}/assets/template.ts
skills/{skill-name}/assets/example.json
```

### 5. Sincronizar

```bash
./skills/skill-sync/assets/sync.sh --dry-run  # Preview
./skills/skill-sync/assets/sync.sh            # Ejecutar
```

### 6. Verificar

Verificar que el skill aparece en los AGENTS.md correspondientes según su scope.

## Naming Conventions

| Tipo | Patrón | Ejemplo |
|------|--------|---------|
| Tecnología genérica | `{technology}` | `typescript`, `react`, `fastapi` |
| Módulo del proyecto | `{module}` | `correccion-ia`, `rubricas` |
| Workflow/Acción | `{action}-{target}` | `skill-sync`, `skill-creator` |

## Template Structure

Un buen skill tiene estas secciones:

1. **Frontmatter YAML** - Metadata obligatoria
2. **When to Use** - Cuándo cargar este skill
3. **Critical Patterns** - ALWAYS/NEVER rules
4. **Decision Trees** - Tablas de decisión
5. **Code Examples** - Ejemplos mínimos y claros
6. **Commands** - Comandos útiles
7. **Resources** - Links a documentación externa

## Critical Rules

### ALWAYS
- Incluir frontmatter YAML válido
- Definir scope (qué AGENTS.md actualizar)
- Definir auto_invoke (qué acciones lo activan)
- Incluir al menos una regla ALWAYS y una NEVER
- Incluir al menos un ejemplo de código
- Mantener skills enfocados (una responsabilidad)

### NEVER
- Duplicar información que ya existe en otros skills
- Crear skills demasiado genéricos
- Incluir tutoriales completos (solo patrones)
- Omitir el frontmatter YAML
- Usar nombres de skill duplicados
