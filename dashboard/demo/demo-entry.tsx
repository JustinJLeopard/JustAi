import { createRoot } from 'react-dom/client'
import JustAiDemo from './JustAiDemo'
import '../src/styles/theme.css'
import './styles/demo-theme.css'

// Note: StrictMode intentionally omitted — the simulation engine uses
// a mutable ref (processedRef) to track timeline events, which StrictMode's
// double-invocation of setState callbacks corrupts.
createRoot(document.getElementById('demo-root')!).render(<JustAiDemo />)
