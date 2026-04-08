# WSL command executor for Desktop Commander
# Usage: powershell -File wsl_exec.ps1 -Cmd "echo hello"
# Writes output to wsl_result.txt in the relay-room project dir

param(
    [Parameter(Mandatory=$true)]
    [string]$Cmd
)

$outFile = "C:\home\justinleopard\projects\relay-room\wsl_result.txt"

# Use Start-Process with -UseNewEnvironment to get a fresh console session
$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = "C:\WINDOWS\system32\wsl.exe"
$pinfo.Arguments = "-d Ubuntu-24.04 -- bash -c `"$Cmd`""
$pinfo.RedirectStandardOutput = $true
$pinfo.RedirectStandardError = $true
$pinfo.UseShellExecute = $false
$pinfo.CreateNoWindow = $false

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $pinfo
$process.Start() | Out-Null

$stdout = $process.StandardOutput.ReadToEnd()
$stderr = $process.StandardError.ReadToEnd()
$process.WaitForExit()

$result = "EXIT:$($process.ExitCode)`n---STDOUT---`n$stdout`n---STDERR---`n$stderr"
[System.IO.File]::WriteAllText($outFile, $result, [System.Text.Encoding]::UTF8)

Write-Host $result