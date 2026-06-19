# CRT - Claude Code Stop hook beallitas uj gepen
# Hozzaadja a CRT_Chat.md autosave hookot a helyi Claude settings.json-hoz

$settingsPath = "$env:USERPROFILE\.claude\settings.json"
$chatScript = "H:\Saját meghajtó\CRT\scripts\chat_autosave.ps1"

# Meglevo settings beolvasasa vagy ures objektum
if (Test-Path $settingsPath) {
    $settings = [System.IO.File]::ReadAllText($settingsPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path $settingsPath) | Out-Null
    $settings = [PSCustomObject]@{}
}

# Stop hook hozzaadasa ha meg nincs
if (-not $settings.hooks) {
    $settings | Add-Member -NotePropertyName "hooks" -NotePropertyValue ([PSCustomObject]@{})
}
if (-not $settings.hooks.Stop) {
    $hookCmd = "powershell -File \"$chatScript\""
    $hookObj = [PSCustomObject]@{
        hooks = @(
            [PSCustomObject]@{
                type          = "command"
                command       = $hookCmd
                shell         = "powershell"
                timeout       = 10
                statusMessage = "CRT chat mentese..."
            }
        )
    }
    $settings.hooks | Add-Member -NotePropertyName "Stop" -NotePropertyValue @($hookObj)
    $json = $settings | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($settingsPath, $json, (New-Object System.Text.UTF8Encoding($true)))
    Write-Host "OK  Stop hook beallitva: $settingsPath" -ForegroundColor Green
} else {
    Write-Host "OK  Stop hook mar be van allitva, semmi teendo." -ForegroundColor Cyan
}
Write-Host "Indits uj Claude Code sessiont a hook aktivalasahoz."