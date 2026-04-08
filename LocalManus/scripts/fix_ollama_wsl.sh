#!/usr/bin/env bash
# =============================================================================
# ManusLocal — Fix Ollama WSL Accessibility
# Configures Ollama on Windows to listen on 0.0.0.0 so WSL can reach it.
# Run this ONCE from WSL. It uses PowerShell to set Windows env vars.
# =============================================================================

echo "Configuring Ollama to be accessible from WSL..."
echo "This requires setting OLLAMA_HOST=0.0.0.0 on Windows."
echo ""

# Set OLLAMA_HOST via PowerShell (Windows user environment variable)
powershell.exe -Command "[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0', 'User'); Write-Host 'OLLAMA_HOST set to 0.0.0.0 for Windows user'"

# Also set OLLAMA_ORIGINS to allow WSL requests
powershell.exe -Command "[System.Environment]::SetEnvironmentVariable('OLLAMA_ORIGINS', '*', 'User'); Write-Host 'OLLAMA_ORIGINS set to * for Windows user'"

echo ""
echo "Done. You must RESTART Ollama on Windows for this to take effect:"
echo "  1. Right-click Ollama in the system tray → Quit"
echo "  2. Relaunch Ollama"
echo ""
echo "After restarting, verify with:"
echo "  WINHOST=\$(cat /etc/resolv.conf | grep nameserver | awk '{print \$2}')"
echo "  curl http://\$WINHOST:11434/"
echo ""
echo "Or from WSL:"
echo "  curl http://\$(ip route | grep default | awk '{print \$3}'):11434/"
