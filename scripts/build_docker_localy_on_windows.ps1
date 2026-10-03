# Build and run the local Docker Compose application; Redis is managed separately.
# Usage:
#   Start:   .\scripts\build_docker_localy_on_windows.ps1 [-Detached] [-ResetDb]
#   Stop:    .\scripts\build_docker_localy_on_windows.ps1 -Stop
#   Restart: .\scripts\build_docker_localy_on_windows.ps1 -Restart
#   Reset DB: .\scripts\build_docker_localy_on_windows.ps1 -ResetDb

param(
    [switch]$Detached,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$ResetDb
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).ProviderPath
$legacyDbFile = Join-Path $repoRoot "db\db.sqlite3"
$dataDbPath = Join-Path $repoRoot "data\db"

function Invoke-Compose {
    param([string[]]$Arguments)

    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
    }
}

if ($Stop -and ($Restart -or $ResetDb -or $Detached)) {
    throw "-Stop cannot be combined with -Restart, -ResetDb or -Detached."
}
if ($Restart -and $ResetDb) {
    throw "Use -ResetDb without -Restart; starting the stack already rebuilds and restarts services."
}

Push-Location $repoRoot
try {
    if (-not (Test-Path ".env")) {
        if (-not (Test-Path ".env.example")) {
            throw "Missing .env and .env.example. Create .env before continuing."
        }
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example; verify REDIS_HOST before starting."
    }

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is not running. Start Docker Desktop and try again."
    }
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose v2 (docker compose) is required."
    }

    if ($Stop) {
        Invoke-Compose @("down")
        return
    }

    if ($ResetDb) {
        $confirmation = Read-Host "This deletes the local SQLite database. Type RESET to continue"
        if ($confirmation -cne "RESET") {
            Write-Host "Database reset cancelled."
            return
        }
    }

    Invoke-Compose @("down")

    if ($ResetDb) {
        foreach ($legacyPath in @($legacyDbFile, "$legacyDbFile-wal", "$legacyDbFile-shm")) {
            if (Test-Path $legacyPath) {
                Remove-Item $legacyPath -Force
            }
        }
        if (Test-Path $dataDbPath) {
            Remove-Item $dataDbPath -Recurse -Force
        }
    }

    New-Item -ItemType Directory -Path $dataDbPath -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $repoRoot "data\media") -Force | Out-Null

    Write-Host "Building the application image..."
    Invoke-Compose @("build")

    Write-Host "Applying database migrations..."
    Invoke-Compose @("run", "--rm", "web", "python", "manage.py", "migrate", "--noinput")

    Write-Host "Redis is external to this Compose stack; verify REDIS_HOST in .env."
    Write-Host "Application URL: http://localhost:8000"
    if ($Detached) {
        Invoke-Compose @("up", "-d")
        Write-Host "Containers started in the background. View logs with: docker compose logs -f"
    } else {
        Invoke-Compose @("up")
    }
}
finally {
    Pop-Location
}
