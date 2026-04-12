import { useEffect } from 'react'
import type { View } from '../components/Sidebar'

const VIEW_KEYS: Record<string, View> = {
  '1': 'mission-control',
  '2': 'task-board',
  '3': 'runs',
  '4': 'trajectories',
  '5': 'memory',
  '6': 'observability',
  '7': 'agents',
}

export function useKeyboard(onNavigate: (view: View) => void, onBack?: () => void) {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      const view = VIEW_KEYS[e.key]
      if (view) {
        e.preventDefault()
        onNavigate(view)
        return
      }

      if (e.key === 'Escape' && onBack) {
        e.preventDefault()
        onBack()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onNavigate, onBack])
}
