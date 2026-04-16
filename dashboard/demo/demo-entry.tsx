import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import JustAiDemo from './JustAiDemo'
import '../src/styles/theme.css'
import './styles/demo-theme.css'

createRoot(document.getElementById('demo-root')!).render(
  <StrictMode>
    <JustAiDemo />
  </StrictMode>
)
