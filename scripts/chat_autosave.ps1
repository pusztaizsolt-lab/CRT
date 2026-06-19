# CRT Chat autosave - Claude Code Stop hook
$chatFile = "H:\Saját meghajtó\CRT\CRT_Chat.md"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
$inputRaw = [Console]::In.ReadToEnd()
$sessionId = "unknown"
try {
    $data = $inputRaw | ConvertFrom-Json
    if ($data.session_id) { $sessionId = $data.session_id.Substring(0, [Math]::Min(8, $data.session_id.Length)) }
} catch {}
$entry = "`n<!-- autosave: $timestamp | session: $sessionId -->"
Add-Content -Path $chatFile -Value $entry -Encoding UTF8