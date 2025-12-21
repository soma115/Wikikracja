# Build Docker image locally on Windows
# Usage: .\scripts\build_docker_local_windows.ps1
# docker run -p 8000:8000 --env-file .env wikikracja:local

param(
    [string]$Tag = "local",
    [string]$ImageName = "wikikracja"
)

# Check if Docker is running
$dockerRunning = docker info 2>$null
if (-not $?) {
    Write-Host "Error: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

Write-Host "Building Docker image: ${ImageName}:${Tag}" -ForegroundColor Green

# Build the image using local Dockerfile
docker build -f Dockerfile.local_windows -t "${ImageName}:${Tag}" .

if ($?) {
    Write-Host "`nSuccess! Image built: ${ImageName}:${Tag}" -ForegroundColor Green
    Write-Host "`nUseful commands:" -ForegroundColor Cyan
    Write-Host "  - List images:        docker images" -ForegroundColor White
    Write-Host "  - Run container:      docker run -p 8000:8000 ${ImageName}:${Tag}" -ForegroundColor White
    Write-Host "  - Run with env file:  docker run -p 8000:8000 --env-file .env ${ImageName}:${Tag}" -ForegroundColor White
    Write-Host "  - Remove image:       docker rmi ${ImageName}:${Tag}" -ForegroundColor White
} else {
    Write-Host "`nError: Build failed!" -ForegroundColor Red
    exit 1
}
