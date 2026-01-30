# Overleaf Project Architecture

## Table of Contents
- [Top-level Structure](#top-level-structure)
- [Microservices Overview](#microservices-overview)
- [services/web/ Deep Dive](#servicesweb-deep-dive)
- [Frontend Architecture](#frontend-architecture)
- [Module System](#module-system)
- [Build Pipeline](#build-pipeline)
- [Context & State Management](#context--state-management)
- [Adding New Features Checklist](#adding-new-features-checklist)

---

## Top-level Structure

```
overleaf/
├── services/           # Microservices (main focus)
│   ├── web/           # Main web app (React + Node.js)
│   ├── clsi/          # LaTeX compilation service
│   ├── chat/          # Real-time chat
│   ├── document-updater/  # OT document sync
│   ├── real-time/     # WebSocket connections
│   └── ...            # 7 more services
├── libraries/         # Shared Node.js packages
│   ├── logger/        # Structured logging
│   ├── metrics/       # Prometheus metrics
│   └── ...
├── develop/           # Docker dev environment
│   ├── bin/           # CLI tools (dev, build)
│   └── docker-compose.yml
└── server-ce/         # Community Edition config
```

## Microservices Overview

| Service | Port | Purpose |
|---------|------|---------|
| **web** | 3000 | Main app: UI, auth, projects |
| clsi | 3013 | LaTeX → PDF compilation |
| document-updater | 3003 | OT (Operational Transform) sync |
| real-time | 3026 | WebSocket connections |
| chat | 3010 | Project comments |
| filestore | 3009 | File storage (S3-compatible) |
| project-history | 3054 | Version history |
| docstore | 3016 | Document storage |
| contacts | 3036 | User contacts |
| notifications | 3042 | User notifications |
| git-bridge | 8000 | Git integration |
| history-v1 | 3100 | History API v1 |

**Key point**: For frontend development, focus on `services/web/`.

---

## services/web/ Deep Dive

```
services/web/
├── app/                    # Backend (Node.js/Express)
│   └── src/
│       ├── Features/       # 58 domain modules
│       │   ├── Authentication/
│       │   ├── Compile/
│       │   ├── Editor/
│       │   ├── Project/
│       │   └── ...
│       ├── infrastructure/ # Cross-cutting concerns
│       │   ├── Express.mjs
│       │   ├── Mongodb.js
│       │   └── ...
│       └── router.mjs      # Route definitions
│
├── frontend/               # Frontend (React/TypeScript)
│   ├── js/
│   │   ├── features/       # 45+ UI feature modules
│   │   ├── shared/         # Reusable components
│   │   ├── infrastructure/ # Core utilities
│   │   ├── pages/          # Entry points
│   │   └── utils/          # Helper functions
│   └── stylesheets/        # SCSS styles
│
├── modules/                # Custom plugins (your code here!)
│   ├── evidence-panel/     # Example module
│   ├── full-project-search/
│   └── ...
│
├── locales/                # i18n translations
│   └── en.json             # English (alphabetically sorted!)
│
├── config/                 # Environment configs
├── macros/                 # Webpack macros
└── types/                  # TypeScript types
```

---

## Frontend Architecture

### Feature Modules (frontend/js/features/)

41 feature directories, each self-contained:

| Category | Features |
|----------|----------|
| **IDE Core** | `ide-react`, `ide-redesign`, `source-editor` |
| **PDF** | `pdf-preview`, `preview` |
| **Files** | `file-tree`, `file-view` |
| **Collaboration** | `chat`, `review-panel`, `share-project-modal` |
| **Project** | `project-list`, `clone-project-modal` |
| **Settings** | `settings`, `editor-left-menu` |
| **Utilities** | `history`, `outline`, `dictionary`, `hotkeys-modal` |

### Shared Components (frontend/js/shared/)

```
shared/
├── components/           # Reusable UI
│   ├── material-icon.tsx
│   ├── loading-spinner.tsx
│   └── ol-*.tsx          # Overleaf component library
├── context/              # Global contexts
│   ├── layout-context.tsx
│   ├── project-context.tsx
│   └── user-context.tsx
└── hooks/                # Shared hooks
```

### Import Path Aliases

```typescript
// Feature imports (with slash after @)
import X from '@/features/pdf-preview/components/...'
import X from '@/shared/components/material-icon'
import X from '@/infrastructure/error-boundary'
import X from '@/utils/meta'

// Module imports (NO slash after @)
import X from '@modules/evidence-panel/frontend/js/...'
```

---

## Module System

### Module Structure

```
modules/my-module/
├── index.mjs              # WebModule interface (required)
├── frontend/
│   └── js/
│       ├── components/    # React components
│       ├── context/       # Module contexts
│       ├── hooks/         # Custom hooks
│       └── pages/         # Entry points (auto-bundled)
└── test/
    └── frontend/js/       # Tests (Mocha/Chai)
```

### Module Entry (index.mjs)

```javascript
/** @import { WebModule } from "../../types/web-module" */

/** @type {WebModule} */
const MyModule = {
  // Optional: Backend router
  router: myRouter,

  // Optional: Pug templates
  viewIncludes: {},

  // Optional: Middleware
  middleware: {}
}

export default MyModule
```

### Module Integration Flow

1. **Create module** in `modules/my-module/`
2. **Add index.mjs** with WebModule interface
3. **Create frontend components** in `frontend/js/`
4. **Register context provider** in `react-context-root.tsx`
5. **Import via** `@modules/my-module/frontend/js/...`

---

## Build Pipeline

### Webpack Entry Points

Entry points are auto-discovered:

```javascript
// Core entries
entryPoints = {
  bootstrap: './frontend/js/bootstrap.ts',
  devToolbar: './frontend/js/dev-toolbar.ts',
  'ide-detached': './frontend/js/ide-detached.ts',
  marketing: './frontend/js/marketing.ts',
  'main-style': './frontend/stylesheets/main-style.scss',
}

// Auto-add from frontend/js/pages/**/*.tsx
// Auto-add from modules/*/frontend/js/pages/**/*.tsx
```

### Output

```
public/
├── js/
│   ├── bootstrap-[hash].js
│   ├── pages/marketing/homepage-[hash].js
│   └── modules/evidence-panel/pages/...-[hash].js
└── stylesheets/
    └── main-style-[hash].css
```

### Dev Server

```bash
cd overleaf/develop
bin/dev web webpack

# Hot reload:
# - webpack: Frontend changes → instant
# - web: Backend changes → auto-restart
```

---

## Context & State Management

### Provider Hierarchy (react-context-root.tsx)

Providers are nested from outermost (global) to innermost (specific):

```
SplitTestProvider
└── ModalsContextProvider
    └── ConnectionProvider
        └── ProjectProvider
            └── UserSettingsProvider
                └── IdeReactProvider
                    └── UserProvider
                        └── ... (30+ providers)
                            └── LocalCompileProvider
                                └── DetachCompileProvider
                                    └── ChatProvider
                                        └── {children}
```

### Adding a New Provider

1. **Import provider** at top of `react-context-root.tsx`:
   ```typescript
   import { MyProvider } from '@modules/my-module/frontend/js/context/my-context'
   ```

2. **Add to Providers object**:
   ```typescript
   const Providers = {
     // ... existing
     MyProvider,
   }
   ```

3. **Insert in tree** (consider dependencies):
   ```tsx
   <Providers.SomeParentProvider>
     <Providers.MyProvider>
       <Providers.SomeChildProvider>
   ```

### Key Contexts

| Context | Purpose | Hook |
|---------|---------|------|
| `ProjectContext` | Project metadata | `useProjectContext` |
| `LayoutContext` | UI layout state | `useLayoutContext` |
| `EditorContext` | Editor state | `useEditorContext` |
| `LocalCompileContext` | Compile state | `useCompileContext` |
| `UserContext` | User info | `useUserContext` |

---

## Adding New Features Checklist

### 1. Planning

- [ ] Identify where feature lives (feature vs module)
- [ ] List required contexts (check provider tree)
- [ ] Design component hierarchy
- [ ] Plan state management

### 2. Implementation

- [ ] Create directory structure
- [ ] Add context/provider (if needed)
- [ ] Register provider in `react-context-root.tsx`
- [ ] Create components with proper patterns
- [ ] Add i18n keys to `locales/en.json` (alphabetically!)
- [ ] Write SCSS styles using CSS variables

### 3. Integration

- [ ] Import using correct alias (`@/` vs `@modules/`)
- [ ] Connect to existing features via events or contexts
- [ ] Handle new/old editor variants if needed:
  ```typescript
  const newEditor = useIsNewEditorEnabled()
  return newEditor ? <NewVariant /> : <OldVariant />
  ```

### 4. Testing

- [ ] Write unit tests (Mocha/Chai)
- [ ] Run in Docker: `npm run test:frontend -- --grep 'MyFeature'`
- [ ] Manual browser testing (F12 Console check)

### 5. Verification

```bash
# Restart webpack
docker compose restart webpack

# Check compilation
docker compose logs webpack --tail 20 | grep -E "compiled|error"

# Expected: "compiled successfully"
```

---

## Quick Reference

### Common Commands

```bash
# Start dev
cd overleaf/develop && bin/dev web webpack

# Restart webpack (after new files)
docker compose restart webpack

# Check logs
docker compose logs webpack --tail 20

# Run tests
docker exec develop-web-1 sh -c \
  "cd /overleaf/services/web && npm run test:frontend -- --grep 'Pattern'"

# Production build
docker exec develop-web-1 sh -c \
  "cd /overleaf/services/web && npm run webpack:production"
```

### File Naming

| Type | Pattern | Example |
|------|---------|---------|
| Component | `kebab-case.tsx` | `pdf-preview-pane.tsx` |
| Hook | `use-*.ts` | `use-compile-triggers.ts` |
| Context | `*-context.tsx` | `evidence-context.tsx` |
| Test | `*.test.tsx` | `evidence-panel.test.tsx` |
| Constants | `*.ts` | `events.ts` |

### Key Files to Know

| File | Purpose |
|------|---------|
| `react-context-root.tsx` | Provider tree (add contexts here) |
| `locales/en.json` | i18n translations |
| `webpack.config.js` | Build configuration |
| `tsconfig.json` | TypeScript paths |
| `types/web-module.d.ts` | Module interface types |
