import { useTheme } from '../hooks/useTheme'

export function ThemeToggle() {
  const { theme, toggle } = useTheme()

  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      style={{
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        color: 'var(--text-muted)',
        fontSize: 14,
        padding: 4,
        borderRadius: 'var(--r-sm)',
        transition: 'color var(--t-fast)',
      }}
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
