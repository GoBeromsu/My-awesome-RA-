# Component Patterns

## Table of Contents
- [Standard Component Structure](#standard-component-structure)
- [Context Provider Pattern](#context-provider-pattern)
- [Hook Pattern](#hook-pattern)
- [Event Communication](#event-communication)
- [Context Integration](#context-integration)
- [UI Patterns](#ui-patterns)
- [Module Integration](#module-integration)

## Standard Component Structure

```typescript
import { memo, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import classNames from 'classnames'
import MaterialIcon from '@/shared/components/material-icon'
import withErrorBoundary from '@/infrastructure/error-boundary'

interface MyComponentProps {
  prop1: string
  prop2?: number
  onAction: (value: string) => void
}

// Internal sub-components use React.memo with named function
const SubComponent = React.memo(function SubComponent() {
  return <div>...</div>
})

function MyComponent({ prop1, prop2, onAction }: MyComponentProps) {
  const { t } = useTranslation()
  const [state, setState] = useState('')

  const handleAction = useCallback(() => {
    onAction(state)
  }, [onAction, state])

  const classes = classNames('my-component', {
    'my-component--active': state,
  })

  return (
    <div className={classes}>
      <MaterialIcon type="icon_name" />
      <span>{t('translation_key')}</span>
      <SubComponent />
    </div>
  )
}

function MyComponentFallback() {
  return <div className="my-component-error">Something went wrong</div>
}

const MyComponentWithBoundary = withErrorBoundary(
  MyComponent,
  () => <MyComponentFallback />
)

export function MyComponent() {
  return <MyComponentWithBoundary />
}

export default memo(MyComponent)
```

## Context Provider Pattern

```typescript
import {
  createContext, useContext, useCallback, useMemo, useState, useRef, FC, ReactNode,
} from 'react'

export interface MyContextValue {
  state: SomeState
  setState: (s: SomeState) => void
  doAction: (param: string) => Promise<void>
}

const initialState: SomeState = { status: 'idle', data: [] }

export const MyContext = createContext<MyContextValue | undefined>(undefined)

interface MyProviderProps {
  children: ReactNode
  apiBaseUrl?: string
}

export const MyProvider: FC<MyProviderProps> = ({
  children,
  apiBaseUrl = 'http://localhost:8000',
}) => {
  const [state, setState] = useState<SomeState>(initialState)
  const abortControllerRef = useRef<AbortController | null>(null)

  const doAction = useCallback(async (param: string) => {
    if (abortControllerRef.current) abortControllerRef.current.abort()
    abortControllerRef.current = new AbortController()

    setState(prev => ({ ...prev, status: 'loading' }))

    try {
      const response = await fetch(`${apiBaseUrl}/endpoint`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ param }),
        signal: abortControllerRef.current.signal,
      })
      const data = await response.json()
      setState({ status: 'success', data })
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') return
      setState(prev => ({ ...prev, status: 'error' }))
    }
  }, [apiBaseUrl])

  const value = useMemo<MyContextValue>(
    () => ({ state, setState, doAction }),
    [state, setState, doAction]
  )

  return <MyContext.Provider value={value}>{children}</MyContext.Provider>
}

export function useMyContext() {
  const context = useContext(MyContext)
  if (!context) {
    throw new Error('useMyContext must be used within MyProvider')
  }
  return context
}
```

## Hook Pattern

```typescript
import { useEffect, useCallback, useRef } from 'react'
import { useMyContext } from '../context/my-context'

const MIN_VALUE = 20

export const useMyHook = () => {
  const { autoMode, doAction } = useMyContext()
  const lastValueRef = useRef<string>('')

  const handleEvent = useCallback(
    (event: Event) => {
      if (!autoMode) return
      const { value } = (event as CustomEvent<{ value: string }>).detail
      if (value === lastValueRef.current) return
      lastValueRef.current = value
      if (value && value.length >= MIN_VALUE) doAction(value)
    },
    [autoMode, doAction]
  )

  useEffect(() => {
    document.addEventListener('custom-event', handleEvent)
    return () => document.removeEventListener('custom-event', handleEvent)
  }, [handleEvent])

  useEffect(() => {
    if (!autoMode) lastValueRef.current = ''
  }, [autoMode])
}
```

## Event Communication

```typescript
// constants/events.ts
export const MY_EVENT = 'my-custom-event'
export interface MyEventDetail { value: string; timestamp: number }

// Dispatch
window.dispatchEvent(new CustomEvent<MyEventDetail>(MY_EVENT, {
  detail: { value: 'test', timestamp: Date.now() }
}))

// Listen
useEffect(() => {
  const handler = (e: Event) => {
    const { detail } = e as CustomEvent<MyEventDetail>
  }
  window.addEventListener(MY_EVENT, handler)
  return () => window.removeEventListener(MY_EVENT, handler)
}, [])
```

## Context Integration

Add provider to `services/web/frontend/js/features/ide-react/context/react-context-root.tsx`:

```typescript
import { YourProvider } from '@modules/your-module/frontend/js/context/your-context'

const Providers = { /* ... */ YourProvider }

// Add to provider tree
<Providers.EvidenceProvider>
  <Providers.YourProvider>
    <Providers.LocalCompileProvider>
      {children}
    </Providers.LocalCompileProvider>
  </Providers.YourProvider>
</Providers.EvidenceProvider>
```

## UI Patterns

### List Container (Logs Pane Style)
```tsx
<div className="logs-pane">
  <div className="logs-pane-content">
    {items.map(item => (
      <div key={item.id} className="log-entry">
        <div className={`log-entry-header log-entry-header-${item.level}`}>
          <MaterialIcon type={iconForLevel(item.level)} />
          <h3 className="log-entry-header-title">{item.title}</h3>
        </div>
        {item.expanded && <div className="log-entry-content">{item.content}</div>}
      </div>
    ))}
  </div>
</div>
// Level classes: error, warning, info, success, raw, typesetting
```

### Toolbar Button
```tsx
<OLTooltip id="my-tooltip" description={t('tooltip')} overlayProps={{ placement: 'bottom' }}>
  <button className="toolbar-btn" onClick={handleClick} aria-label={t('label')}>
    <MaterialIcon type="icon_name" />
  </button>
</OLTooltip>
```

### Toggle Button
```tsx
<button
  className={classNames('toolbar-toggle', { active: show })}
  onClick={onToggle}
  aria-label={t('toggle')}
  aria-pressed={show}
>
  <MaterialIcon type="icon" />
</button>
```

### Lazy Loading
```tsx
const LazyComponent = lazy(() =>
  import('@modules/my-module/frontend/js/components/my-component').then(
    module => ({ default: module.MyComponent })
  )
)

{show && (
  <Suspense fallback={<FullSizeLoadingSpinner delay={500} />}>
    <LazyComponent />
  </Suspense>
)}
```

## Module Integration

### Module Directory Structure
```
modules/my-module/
├── index.mjs              # WebModule interface (required)
├── frontend/
│   └── js/
│       ├── components/    # React components
│       │   └── my-panel.tsx
│       ├── context/       # Module contexts
│       │   └── my-context.tsx
│       ├── hooks/         # Custom hooks
│       │   └── use-my-feature.ts
│       ├── constants/     # Event names, config
│       │   └── events.ts
│       └── pages/         # Auto-bundled entry points
└── test/
    └── frontend/js/       # Tests
```

### Module Entry (index.mjs)
```javascript
/** @import { WebModule } from "../../types/web-module" */
/** @type {WebModule} */
const MyModule = {
  // Optional: Add server-side router
  // router: myRouter,
}
export default MyModule
```

### Step-by-Step Module Integration

#### 1. Create Context Provider
```typescript
// modules/my-module/frontend/js/context/my-context.tsx
import { createContext, useContext, useState, useMemo, FC, ReactNode } from 'react'

interface MyContextValue {
  isActive: boolean
  setActive: (v: boolean) => void
}

const MyContext = createContext<MyContextValue | undefined>(undefined)

export const MyProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [isActive, setActive] = useState(false)

  const value = useMemo(() => ({ isActive, setActive }), [isActive])

  return <MyContext.Provider value={value}>{children}</MyContext.Provider>
}

export function useMyContext() {
  const ctx = useContext(MyContext)
  if (!ctx) throw new Error('useMyContext must be used within MyProvider')
  return ctx
}
```

#### 2. Register Provider in react-context-root.tsx
```typescript
// frontend/js/features/ide-react/context/react-context-root.tsx

// Add import
import { MyProvider } from '@modules/my-module/frontend/js/context/my-context'

// Add to Providers object
const Providers = {
  // ... existing providers
  MyProvider,
}

// Insert in provider tree (consider dependency order)
<Providers.LocalCompileProvider>
  <Providers.MyProvider>           {/* Add here */}
    <Providers.DetachCompileProvider>
      {children}
    </Providers.DetachCompileProvider>
  </Providers.MyProvider>
</Providers.LocalCompileProvider>
```

#### 3. Create Event Constants
```typescript
// modules/my-module/frontend/js/constants/events.ts
export const MY_PANEL_SHOW = 'my-module:panel:show'
export const MY_PANEL_HIDE = 'my-module:panel:hide'

export interface MyPanelEventDetail {
  source: string
  timestamp: number
}
```

#### 4. Create Component
```typescript
// modules/my-module/frontend/js/components/my-panel.tsx
import { memo } from 'react'
import { useTranslation } from 'react-i18next'
import { useMyContext } from '../context/my-context'
import MaterialIcon from '@/shared/components/material-icon'

function MyPanel() {
  const { t } = useTranslation()
  const { isActive } = useMyContext()

  if (!isActive) return null

  return (
    <div className="my-panel">
      <div className="my-panel-header">
        <MaterialIcon type="info" />
        <span>{t('my_panel_title')}</span>
      </div>
      <div className="my-panel-content">
        {/* Content here */}
      </div>
    </div>
  )
}

export default memo(MyPanel)
```

#### 5. Integrate into Existing Feature (e.g., PDF Preview)
```typescript
// frontend/js/features/pdf-preview/components/pdf-preview-pane.tsx
import { lazy, Suspense, useState, useEffect } from 'react'
import { MY_PANEL_SHOW, MY_PANEL_HIDE } from '@modules/my-module/frontend/js/constants/events'
import FullSizeLoadingSpinner from '@/shared/components/full-size-loading-spinner'

// Lazy load module component
const MyPanel = lazy(() =>
  import('@modules/my-module/frontend/js/components/my-panel').then(
    module => ({ default: module.default })
  )
)

function PdfPreviewPane() {
  const [showMyPanel, setShowMyPanel] = useState(false)

  // Listen for show/hide events
  useEffect(() => {
    const handleShow = () => setShowMyPanel(true)
    const handleHide = () => setShowMyPanel(false)

    window.addEventListener(MY_PANEL_SHOW, handleShow)
    window.addEventListener(MY_PANEL_HIDE, handleHide)

    return () => {
      window.removeEventListener(MY_PANEL_SHOW, handleShow)
      window.removeEventListener(MY_PANEL_HIDE, handleHide)
    }
  }, [])

  return (
    <div className="pdf-preview-pane">
      {showMyPanel ? (
        <Suspense fallback={<FullSizeLoadingSpinner delay={500} />}>
          <MyPanel />
        </Suspense>
      ) : (
        <PdfViewer />
      )}
    </div>
  )
}
```
