# CSS Patterns

## Table of Contents
- [CSS Variables](#css-variables)
- [Spacing Variables](#spacing-variables)
- [Component SCSS Structure](#component-scss-structure)

## CSS Variables

### Content Colors
```scss
color: var(--content-primary);
color: var(--content-secondary);
color: var(--content-disabled);
```

### Background Colors
```scss
background: var(--bg-light-primary);
background: var(--bg-light-secondary);
background: var(--bg-light-tertiary);
background: var(--bg-light-disabled);
background: var(--bg-dark-tertiary);
```

### Border
```scss
border: 1px solid var(--border-color);
```

### Accent Colors
```scss
// Green
color: var(--green-50);
background: var(--green-10);

// Red
color: var(--red-50);
background: var(--red-10);

// Yellow
color: var(--yellow-50);
background: var(--yellow-10);
```

### Level-specific (Log Entries)
```scss
.log-entry-header-error { background-color: var(--content-danger); }
.log-entry-header-warning { background-color: var(--content-warning-dark); }
.log-entry-header-success { background-color: var(--green-50); }
.log-entry-header-info { background-color: var(--bg-dark-tertiary); }
```

## Spacing Variables

```scss
padding: var(--spacing-02);  // 4px
padding: var(--spacing-03);  // 6px
padding: var(--spacing-04);  // 8px
gap: var(--spacing-04);
```

## Component SCSS Structure

```scss
// Container
.my-component {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-light-secondary);
  overflow: hidden;
}

// Header
.my-component-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-light-primary);
}

// Title with icon
.my-component-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--content-primary);

  .material-symbols {
    font-size: 20px;
    color: var(--content-secondary);
  }
}

// Scrollable content
.my-component-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

// State variations
.my-component-loading,
.my-component-error,
.my-component-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: var(--content-secondary);

  .material-symbols {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.3;
  }
}

// Interactive items
.my-component-item {
  background: var(--bg-light-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  transition: box-shadow 0.15s ease;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }
}
```
