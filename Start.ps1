param(
    [ValidateSet('view', 'image', 'render', 'clips', 'plots')]
    [string]$Mode = 'view',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ApplicationArguments
)

$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $projectPython)) {
        throw 'Bitte zuerst die Python-Umgebung nach README.md einrichten.'
    }
    & $projectPython -m bohr_atom $Mode @ApplicationArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'bohr-atom wurde mit einem Fehler beendet.'
    }
}
finally {
    Pop-Location
}
