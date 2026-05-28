# CRT - VS Code bovitmenyek telepitese
# Futtatas: powershell -ExecutionPolicy Bypass -File _setup\setup_vscode.ps1

Write-Host ""
Write-Host "  CRT - VS Code bovitmenyek telepitese"
Write-Host ""

# VS Code elerheto-e?
$code = $null
foreach ($c in @("code", "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd")) {
    try {
        & cmd /c "$c --version" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $code = $c; break }
    } catch {}
}

if (-not $code) {
    Write-Host "  HIBA: VS Code nem talalhato!" -ForegroundColor Red
    Write-Host "  Telepites: https://code.visualstudio.com/download" -ForegroundColor Yellow
    exit 1
}

Write-Host "  VS Code megvan. Bovitmenyek telepitese..." -ForegroundColor Green
Write-Host ""

$extensions = @(
    @{ id = "anthropic.claude-code";                    nev = "Claude Code (AI asszisztens)" },
    @{ id = "ms-python.python";                         nev = "Python" },
    @{ id = "ms-python.pylint";                         nev = "Python Linter" },
    @{ id = "ms-python.black-formatter";                nev = "Black formatter" },
    @{ id = "ms-python.debugpy";                        nev = "Python Debugger" },
    @{ id = "humao.rest-client";                        nev = "REST Client (API teszteles)" },
    @{ id = "mhutchie.git-graph";                       nev = "Git Graph" },
    @{ id = "eamodio.gitlens";                          nev = "GitLens" },
    @{ id = "yzhang.markdown-all-in-one";               nev = "Markdown" },
    @{ id = "bierner.markdown-mermaid";                 nev = "Markdown Mermaid (diagram)" },
    @{ id = "ecmel.vscode-html-css";                    nev = "HTML/CSS" },
    @{ id = "esbenp.prettier-vscode";                   nev = "Prettier formatter" },
    @{ id = "streetsidesoftware.code-spell-checker";    nev = "Helyesiras ellenorzo" },
    @{ id = "streetsidesoftware.code-spell-checker-hungarian"; nev = "Magyar szotar" }
)

$ok = 0
$err = 0
foreach ($ext in $extensions) {
    Write-Host "  Telepites: $($ext.nev)..." -NoNewline
    & cmd /c "$code --install-extension $($ext.id) --force" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        $ok++
    } else {
        Write-Host " HIBA" -ForegroundColor Yellow
        $err++
    }
}

Write-Host ""
Write-Host "  =============================================="
Write-Host "  Kesz! $ok bovitmeny telepitve" -ForegroundColor Cyan
if ($err -gt 0) {
    Write-Host "  $err sikertelen - internet kapcsolat?" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Kovetkezo lepesek:" -ForegroundColor White
Write-Host "  1. Nyisd meg VS Code-ban: H:\Sajat meghajto\CRT\" -ForegroundColor White
Write-Host "  2. VS Code ajanlani fogja a tobbi bovitmenyt - fogadd el" -ForegroundColor White
Write-Host "  3. Claude Code: bal oldalt a kis C ikon - bejelentkezes" -ForegroundColor White
Write-Host "  4. Terminal (Ctrl+') -> CRT: Backend inditas (Ctrl+Shift+B)" -ForegroundColor White
Write-Host "  =============================================="
Write-Host ""
