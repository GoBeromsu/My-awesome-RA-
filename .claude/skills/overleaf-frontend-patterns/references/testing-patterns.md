# Testing Patterns

## Table of Contents
- [Test File Structure](#test-file-structure)
- [Test Helper Pattern](#test-helper-pattern)
- [Running Tests](#running-tests)

## Test File Structure

```typescript
import { expect } from 'chai'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import sinon from 'sinon'
import fetchMock from 'fetch-mock'
import React from 'react'

import {
  renderWithContext,
  createMockData,
} from '../helpers/test-providers'
import { MyComponent } from '../../../../frontend/js/components/my-component'

describe('MyComponent', function () {
  beforeEach(function () {
    fetchMock.removeRoutes().clearHistory()
  })

  afterEach(function () {
    fetchMock.removeRoutes().clearHistory()
    sinon.restore()
  })

  describe('Feature Group', function () {
    it('does something expected', function () {
      const onAction = sinon.stub()
      renderWithContext(<MyComponent onAction={onAction} />)

      expect(screen.getByRole('button')).to.exist
      fireEvent.click(screen.getByRole('button'))
      expect(onAction.calledOnce).to.be.true
    })
  })

  describe('Accessibility', function () {
    it('has proper ARIA attributes', function () {
      renderWithContext(<MyComponent />)
      expect(screen.getByLabelText('Expected label')).to.exist
    })
  })
})
```

## Test Helper Pattern

```typescript
import React, { ReactNode } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import {
  MyContext,
  MyContextValue,
} from '../../../../frontend/js/context/my-context'

const defaultContextValue: MyContextValue = {
  state: { status: 'idle', data: [] },
  setState: () => {},
  doAction: async () => {},
}

interface ProviderWrapperProps {
  children: ReactNode
  value?: Partial<MyContextValue>
}

export function ProviderWrapper({ children, value = {} }: ProviderWrapperProps) {
  const contextValue = { ...defaultContextValue, ...value }
  return (
    <MyContext.Provider value={contextValue}>
      {children}
    </MyContext.Provider>
  )
}

export function renderWithContext(
  component: React.ReactElement,
  options: { contextValue?: Partial<MyContextValue>; renderOptions?: RenderOptions } = {}
) {
  const { contextValue = {}, renderOptions = {} } = options
  return render(component, {
    wrapper: ({ children }) => (
      <ProviderWrapper value={contextValue}>{children}</ProviderWrapper>
    ),
    ...renderOptions,
  })
}

export function createMockItem(overrides = {}) {
  return {
    id: 'item_1',
    title: 'Test Item',
    ...overrides,
  }
}

export function createMockResults(count: number) {
  return Array.from({ length: count }, (_, i) =>
    createMockItem({
      id: `item_${i + 1}`,
      title: `Item ${i + 1}`,
    })
  )
}
```

## Running Tests

**Always run tests inside Docker container:**

```bash
# Run specific tests by name
docker exec develop-web-1 sh -c \
  "cd /overleaf/services/web && npm run test:frontend -- --grep 'MyFeature'"

# Run all tests for a module
docker exec develop-web-1 sh -c \
  "cd /overleaf/services/web && npm run test:frontend -- --grep 'Evidence'"

# Run with verbose output
docker exec develop-web-1 sh -c \
  "cd /overleaf/services/web && npm run test:frontend -- --reporter spec --grep 'MyTest'"
```

### Test Location

```
modules/your-module/
├── frontend/js/components/     # Source files
└── test/frontend/js/
    ├── components/             # Test files (*.test.tsx)
    └── helpers/                # Test utilities
```
