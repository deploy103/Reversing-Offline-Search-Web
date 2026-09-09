<#
.SYNOPSIS
    tools/manifest.json 을 읽어서 release_url이 있는 항목을 다운로드하고 SHA256을 검증한다.

.DESCRIPTION
    - release_url이 없는 항목(PyPI/apt/수동 설치형)은 건너뛰고 안내 메시지를 출력한다.
    - Windows PowerShell 5.1 이상(내장 Invoke-WebRequest, Get-FileHash)만으로 동작하며
      외부 모듈/의존성이 필요 없다.

.PARAMETER Only
    이름에 이 문자열이 포함된 항목만 처리한다 (선택 사항).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\fetch-tools.ps1
    powershell -ExecutionPolicy Bypass -File scripts\fetch-tools.ps1 -Only "Ghidra"
#>

param(
    [string]$Only = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir
$Manifest  = Join-Path $RepoRoot "tools\manifest.json"

if (-not (Test-Path $Manifest)) {
    Write-Error "manifest를 찾을 수 없음: $Manifest"
    exit 1
}

$entries = Get-Content -Raw -Path $Manifest -Encoding UTF8 | ConvertFrom-Json

$total = 0
$downloaded = 0
$verifiedOk = 0
$verifiedFail = 0
$skipped = 0

foreach ($e in $entries) {
    $total++

    $name       = [string]$e.name
    $releaseUrl = [string]$e.release_url
    $sha256     = [string]$e.sha256
    $localPath  = [string]$e.local_path

    if ($Only -ne "" -and $name -notlike "*$Only*") {
        continue
    }

    if ([string]::IsNullOrWhiteSpace($releaseUrl)) {
        Write-Host "[SKIP] $name : release_url 없음 (PyPI/apt/수동 설치 안내형 항목)"
        if ($name -match "\(PyPI") {
            $pkg = ($name -replace " ?\(PyPI.*\)", "")
            Write-Host "        -> pip download $pkg -d offline-kit/wheels/  로 오프라인 준비 가능"
        }
        elseif ($localPath -match "apt|-debs") {
            Write-Host "        -> apt-get download <패키지명>  으로 오프라인 준비 (offline_install 필드 참고, Linux 전용)"
        }
        else {
            Write-Host "        -> tools/manifest.json 의 offline_install 필드를 참고해 수동으로 준비하세요"
        }
        $skipped++
        continue
    }

    $dest = Join-Path $RepoRoot $localPath
    $destDir = Split-Path -Parent $dest
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    Write-Host "[GET ] $name"
    Write-Host "        $releaseUrl"
    Write-Host "        -> $localPath"

    try {
        Invoke-WebRequest -Uri $releaseUrl -OutFile $dest -UseBasicParsing
    }
    catch {
        Write-Warning "다운로드 실패: $name ($releaseUrl) - $($_.Exception.Message)"
        continue
    }
    $downloaded++

    if ([string]::IsNullOrWhiteSpace($sha256)) {
        Write-Host "[WARN] $name : manifest에 sha256 값이 없어 검증을 건너뜁니다 (다운로드는 완료됨)"
        continue
    }

    $actualHash = (Get-FileHash -Path $dest -Algorithm SHA256).Hash.ToLower()
    $expectedHash = $sha256.ToLower()

    if ($actualHash -eq $expectedHash) {
        Write-Host "[ OK ] $name : SHA256 일치"
        $verifiedOk++
    }
    else {
        Write-Host "[FAIL] $name : SHA256 불일치!" -ForegroundColor Red
        Write-Host "        기대값: $sha256" -ForegroundColor Red
        Write-Host "        실제값: $actualHash" -ForegroundColor Red
        Write-Host "        손상되었거나 변조된 파일일 수 있습니다. 삭제 후 다시 시도하세요." -ForegroundColor Red
        Remove-Item -Path $dest -Force -ErrorAction SilentlyContinue
        $verifiedFail++
        Write-Host ""
        Write-Error "[STOP] 체크섬 불일치로 중단합니다."
        exit 1
    }
}

Write-Host ""
Write-Host "==================== 요약 ===================="
Write-Host "전체 항목:            $total"
Write-Host "다운로드 시도:         $downloaded"
Write-Host "체크섬 일치(OK):       $verifiedOk"
Write-Host "체크섬 불일치:         $verifiedFail"
Write-Host "스킵(수동/PyPI/apt):   $skipped"
Write-Host "================================================"
