---
name: help-system-content
description: >
  Ensures inline help is always present in application pages and that help content
  follows a consistent, reusable structure.
  Trigger: When adding help content to any page, creating a new page with user-facing documentation, or adding form-level help.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "2.0"
---

## When to Use

- Creating a new page that needs inline help or documentation
- Adding a form modal that needs field-level guidance
- Any time a page layout wrapper is used without help content
- Any time a create/edit modal is added without help guidance inside it

---

## Critical Patterns

### Rule 1: Help Content is MANDATORY in ALL pages

Every page MUST provide help content to its layout wrapper. No exceptions.

```tsx
// CORRECT
<PageLayout
  title="My Page"
  description="..."
  helpContent={helpContent.myPage}   // <-- always present
>

// WRONG - missing helpContent
<PageLayout title="My Page" description="...">
```

### Rule 2: Page-level content lives in a dedicated help file — NEVER inline

All page-level help content goes in a centralized file (e.g., `src/utils/helpContent.tsx` or `src/content/help.tsx`).
Import it in the page, never write JSX inline for page-level help.

```tsx
// In the page file
import { helpContent } from '@/utils/helpContent'

<PageLayout helpContent={helpContent.categories} ...>
```

### Rule 3: Form modals get an inline HelpButton (size="sm")

Every create/edit modal includes a help trigger at the top of the form that explains the fields. This content IS inline (not in the help file) because it describes the form, not the page.

```tsx
<Modal isOpen={modal.isOpen} onClose={modal.close} title="New Item" ...>
  <form id="my-form" action={formAction} className="space-y-4">
    <div className="flex items-center gap-2 mb-2">
      <HelpButton
        title="Item Form"
        size="sm"
        content={
          <div className="space-y-3">
            <p><strong>Fill in the following fields</strong> to create or edit an item:</p>
            <ul className="list-disc pl-5 space-y-2">
              <li><strong>Name:</strong> Field description. Required.</li>
            </ul>
            <div className="bg-zinc-800 p-3 rounded-lg mt-3">
              <p className="text-orange-400 font-medium text-sm">Tip:</p>
              <p className="text-sm mt-1">Helpful tip text.</p>
            </div>
          </div>
        }
      />
      <span className="text-sm text-[var(--text-tertiary)]">Form help</span>
    </div>
    {/* form fields */}
  </form>
</Modal>
```

---

## Help Content Entry Structure

Every entry follows this exact JSX structure:

```tsx
myPage: (
  <div className="space-y-4 text-zinc-300">
    {/* 1. Page title */}
    <p className="text-lg font-medium text-[var(--text-inverse)]">Page Title</p>

    {/* 2. One-sentence intro */}
    <p>Brief description of what this page is for.</p>

    {/* 3. Feature list */}
    <ul className="list-disc list-inside space-y-2 ml-4">
      <li><strong>Main action:</strong> Description of the action.</li>
      <li><strong>Another action:</strong> Description.</li>
    </ul>

    {/* 4. Tip/note box — use one of these variants: */}

    {/* Variant A — neutral tip (Tip / Note / Important) */}
    <div className="bg-zinc-800 p-4 rounded-lg mt-4">
      <p className="text-orange-400 font-medium">Tip:</p>
      <p className="text-sm mt-1">Helpful tip text.</p>
    </div>

    {/* Variant B — danger warning (cascade deletes, irreversible actions) */}
    <div className="bg-red-900/50 p-4 rounded-lg mt-4 border border-red-700">
      <p className="text-[var(--danger-text)] font-medium">Warning:</p>
      <p className="text-sm mt-1">This action cannot be undone.</p>
    </div>
  </div>
),
```

**Rules for the tip box:**
- Use `bg-zinc-800` + `text-orange-400` for: Tip, Note, Important, general guidance
- Use `bg-red-900/50 border border-red-700` + `text-[var(--danger-text)]` only when the action causes irreversible data loss (cascade deletes)
- Always include exactly one tip box per entry (can add a second only if a page warrants both a tip and a warning)

---

## Adding a New Entry — Checklist

1. Add a key to the help content record in the centralized help file
2. Use the JSX structure above (title -> intro -> list -> tip box)
3. Write content in the project's language, keeping it concise
4. Import the help content in the new page and pass the key to the layout wrapper
5. Add an inline help trigger inside each create/edit modal in that page

---

## Tone Guidelines

- Style: Instructive and concise — "Click X to Y"
- Feature list items: `<strong>Label:</strong> one-sentence explanation`
- Tip box label examples: "Tip", "Note", "Important", "Warning"
- No marketing language — just functional guidance
