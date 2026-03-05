# EdgeTrack - Environment initialization script (Windows PowerShell)
# Usage: .\init.ps1

$ErrorActionPreference = "Stop"

$envFile = Join-Path $PSScriptRoot ".env"
$exampleFile = Join-Path $PSScriptRoot ".env.example"

if (Test-Path $envFile) {
    Write-Host "[!] .env file already exists." -ForegroundColor Yellow
    $confirm = Read-Host "Overwrite? (y/N)"
    if ($confirm -ne "y") {
        Write-Host "Aborted." -ForegroundColor Red
        exit 0
    }
}

if (-not (Test-Path $exampleFile)) {
    Write-Host "[ERROR] .env.example not found in $PSScriptRoot" -ForegroundColor Red
    exit 1
}

# --- Helper functions ---

function New-RandomPassword {
    param([int]$Length = 32)
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    # URL-safe base64: replace +/ with -_ and remove padding
    $b64 = [Convert]::ToBase64String($bytes)
    return ($b64 -replace '\+','-' -replace '/','_' -replace '=','').Substring(0, $Length)
}

function New-FernetKey {
    # Fernet key = URL-safe base64 encoding of 32 random bytes (keep padding for valid Fernet)
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $b64 = [Convert]::ToBase64String($bytes)
    return $b64 -replace '\+','-' -replace '/','_'
}

function New-UrlSafeToken {
    param([int]$ByteLength = 32)
    $bytes = New-Object byte[] $ByteLength
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $b64 = [Convert]::ToBase64String($bytes)
    return $b64 -replace '\+','-' -replace '/','_' -replace '=',''
}

# --- Generate secrets ---

$postgresPassword = New-RandomPassword -Length 24
$pgadminPassword = New-RandomPassword -Length 16
$secretKey = New-UrlSafeToken -ByteLength 48
$encryptionKey = New-FernetKey
$emailEncryptionKey = New-UrlSafeToken -ByteLength 32
$emailHashPepper = New-UrlSafeToken -ByteLength 32

# --- Read template and replace ---

$content = Get-Content $exampleFile -Raw

$content = $content -replace 'POSTGRES_PASSWORD=postgres', "POSTGRES_PASSWORD=$postgresPassword"
$content = $content -replace 'PGADMIN_DEFAULT_PASSWORD=admin', "PGADMIN_DEFAULT_PASSWORD=$pgadminPassword"
$content = $content -replace 'SECRET_KEY=change-me-in-production-use-a-long-random-string', "SECRET_KEY=$secretKey"
$content = $content -replace 'ENCRYPTION_KEY=change-me-in-production-use-fernet-key', "ENCRYPTION_KEY=$encryptionKey"
$content = $content -replace 'EMAIL_ENCRYPTION_KEY=change-me-in-production-32-bytes!', "EMAIL_ENCRYPTION_KEY=$emailEncryptionKey"
$content = $content -replace 'EMAIL_HASH_PEPPER=change-me-in-production-pepper', "EMAIL_HASH_PEPPER=$emailHashPepper"

# Write .env file (UTF-8 without BOM, LF line endings)
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($envFile, $content.Replace("`r`n", "`n"), $utf8NoBom)

Write-Host ""
Write-Host "=== EdgeTrack .env initialized ===" -ForegroundColor Green
Write-Host ""
Write-Host "Generated secrets:" -ForegroundColor Cyan
Write-Host "  POSTGRES_PASSWORD    = $postgresPassword"
Write-Host "  PGADMIN_PASSWORD     = $pgadminPassword"
Write-Host "  SECRET_KEY           = $($secretKey.Substring(0,12))..."
Write-Host "  ENCRYPTION_KEY       = $($encryptionKey.Substring(0,12))..."
Write-Host "  EMAIL_ENCRYPTION_KEY = $($emailEncryptionKey.Substring(0,12))..."
Write-Host "  EMAIL_HASH_PEPPER    = $($emailHashPepper.Substring(0,12))..."
Write-Host ""
Write-Host "File created: $envFile" -ForegroundColor Green
Write-Host ""
Write-Host "[!] WARNING: Keep these keys safe. If you lose ENCRYPTION_KEY or" -ForegroundColor Yellow
Write-Host "    EMAIL_ENCRYPTION_KEY, encrypted data cannot be recovered." -ForegroundColor Yellow
Write-Host ""
