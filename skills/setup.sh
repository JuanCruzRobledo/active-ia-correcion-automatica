#!/bin/bash

# Setup script for AI assistants
# Creates necessary symlinks and config files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}!${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

setup_claude() {
    echo "Setting up Claude Code..."
    mkdir -p "$PROJECT_ROOT/.claude"

    if [ -L "$PROJECT_ROOT/.claude/skills" ]; then
        rm "$PROJECT_ROOT/.claude/skills"
    fi

    ln -s "$SCRIPT_DIR" "$PROJECT_ROOT/.claude/skills"
    print_success "Claude Code configured (.claude/skills -> skills/)"
}

setup_codex() {
    echo "Setting up Codex..."
    mkdir -p "$PROJECT_ROOT/.codex"

    if [ -L "$PROJECT_ROOT/.codex/skills" ]; then
        rm "$PROJECT_ROOT/.codex/skills"
    fi

    ln -s "$SCRIPT_DIR" "$PROJECT_ROOT/.codex/skills"
    print_success "Codex configured (.codex/skills -> skills/)"
}

setup_gemini() {
    echo "Setting up Gemini CLI..."
    mkdir -p "$PROJECT_ROOT/.gemini"

    if [ -L "$PROJECT_ROOT/.gemini/skills" ]; then
        rm "$PROJECT_ROOT/.gemini/skills"
    fi

    ln -s "$SCRIPT_DIR" "$PROJECT_ROOT/.gemini/skills"
    print_success "Gemini CLI configured (.gemini/skills -> skills/)"
}

setup_copilot() {
    echo "Setting up GitHub Copilot..."
    mkdir -p "$PROJECT_ROOT/.github"

    cat > "$PROJECT_ROOT/.github/copilot-instructions.md" << 'EOF'
# GitHub Copilot Instructions - Active-IA

## Project Context

Active-IA es una plataforma de corrección automática de trabajos prácticos con IA.

## Key Files

- `AGENTS.md` - Instrucciones globales
- `frontend/AGENTS.md` - Instrucciones frontend
- `backend/AGENTS.md` - Instrucciones backend

## Skills

Consultar los archivos SKILL.md en la carpeta `skills/` para patrones específicos.

## Critical Rules

### Backend (FastAPI + Clean Architecture)
- Router → Service → Repository
- Validar con Pydantic
- Permisos en cada endpoint
- Soft delete siempre

### Frontend (React + TypeScript)
- Componentes funcionales
- Props tipadas con interface
- React Query para estado servidor
- Tailwind para estilos

## Commit Format

```
<type>(<scope>): <description>
```

Types: feat, fix, refactor, docs, test, chore
EOF

    print_success "GitHub Copilot configured (.github/copilot-instructions.md)"
}

show_help() {
    echo "Usage: ./setup.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --all       Setup all AI assistants"
    echo "  --claude    Setup Claude Code only"
    echo "  --codex     Setup Codex only"
    echo "  --copilot   Setup GitHub Copilot only"
    echo "  --gemini    Setup Gemini CLI only"
    echo "  --help      Show this help"
    echo ""
    echo "Without options, runs in interactive mode."
}

interactive_mode() {
    echo "Active-IA - AI Assistant Setup"
    echo "=============================="
    echo ""
    echo "Which AI assistants do you want to configure?"
    echo ""
    echo "1) All"
    echo "2) Claude Code"
    echo "3) Codex (OpenAI)"
    echo "4) GitHub Copilot"
    echo "5) Gemini CLI"
    echo "6) Exit"
    echo ""
    read -p "Select option (1-6): " choice

    case $choice in
        1) setup_claude; setup_codex; setup_copilot; setup_gemini ;;
        2) setup_claude ;;
        3) setup_codex ;;
        4) setup_copilot ;;
        5) setup_gemini ;;
        6) echo "Bye!"; exit 0 ;;
        *) print_error "Invalid option"; exit 1 ;;
    esac
}

# Main
case "${1:-}" in
    --all)
        setup_claude
        setup_codex
        setup_copilot
        setup_gemini
        ;;
    --claude)
        setup_claude
        ;;
    --codex)
        setup_codex
        ;;
    --copilot)
        setup_copilot
        ;;
    --gemini)
        setup_gemini
        ;;
    --help|-h)
        show_help
        ;;
    "")
        interactive_mode
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac

echo ""
print_success "Setup complete!"
