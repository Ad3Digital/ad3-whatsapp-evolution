[CmdletBinding()]
param(
    [ValidateSet('demo','remote','local')] [string] $Mode = 'demo',
    [string] $Destination = "$env:LOCALAPPDATA\AD3Evolution",
    [string] $PackageRoot = (Split-Path -Parent $PSScriptRoot),
    [string] $PackageArchive,
    [string] $ExpectedPackageSha256,
    [switch] $Diagnose,
    [switch] $Apply,
    [switch] $InstallWSL,
    [switch] $InstallDocker,
    [switch] $AcceptTerms,
    [switch] $Elevate,
    [switch] $Resume,
    [switch] $NonInteractive,
    [switch] $ProvisionInstance,
    [string] $ProvisionInstanceName = 'creator',
    [string] $RemoteUrl,
    [string] $RemoteInstance,
    [string] $RemoteApiKey
)

$ErrorActionPreference = 'Stop'
$MarkerRoot = Join-Path $env:LOCALAPPDATA 'AD3EvolutionInstaller'
$MarkerPath = Join-Path $MarkerRoot 'install-resume.json'
$RequiredPackageItems = @('ad3-evolution.exe','AD3-WATERMARK.json','LICENSE-MANIFEST.json','LICENSE-MANIFEST.sig','CHECKSUMS.sha256','LICENSE.md','THIRD_PARTY_NOTICES.md','skill','install','deploy','docs')

function Write-Next([string] $Message) { Write-Host "Next: $Message" -ForegroundColor Yellow }
function Fail([string] $Message, [string] $Next) { Write-Error "AD3 Evolution installer: $Message"; if ($Next) { Write-Next $Next }; throw $Message }
function Is-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal] $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Get-Secret {
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','A').Replace('/','B')
}
function Convert-SecureToPlain([Security.SecureString] $Value) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
function Get-WslVersion {
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) { return $null }
    $line = (& wsl --version 2>$null | Where-Object { $_ -match '\d+\.\d+\.\d+' } | Select-Object -First 1)
    if ($line -match '(\d+\.\d+\.\d+)') { return [version] $Matches[1] }
    return $null
}
function Assert-RemoteUrl {
    if(!$RemoteUrl){return}; try {$u=[Uri]$RemoteUrl} catch {Fail 'RemoteUrl is invalid.' 'Use http://localhost or HTTPS without credentials/query/fragment.'}
    if(!$u.Host -or $u.UserInfo -or $u.Query -or $u.Fragment -or -not (($u.Scheme -eq 'https') -or ($u.Scheme -eq 'http' -and $u.Host -eq 'localhost'))){Fail 'RemoteUrl is not allowed.' 'Use http://localhost or HTTPS without credentials/query/fragment.'}
    $script:RemoteUrl=$u.GetLeftPart([UriPartial]::Path).TrimEnd('/')
}
function Test-UserPath([string] $Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $roots = @([IO.Path]::GetFullPath($env:USERPROFILE), [IO.Path]::GetFullPath($env:LOCALAPPDATA))
    if (-not ($roots | Where-Object { $full -eq $_ -or $full.StartsWith($_ + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) })) { Fail 'Destination must be inside the current user profile or LOCALAPPDATA.' 'Choose a folder under %LOCALAPPDATA%.' }
    return $full
}
function Test-Package([string] $Root) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    foreach ($item in $RequiredPackageItems) {
        if (-not (Test-Path (Join-Path $rootFull $item))) { Fail "Package item missing: $item" 'Obtain a complete signed student package.' }
    }
    return $rootFull
}
function Test-TrustedArchive([string] $Archive, [string] $ExpectedHash, [string] $Root) {
    if (-not $Archive -or -not $ExpectedHash) { Fail 'Apply requires the original ZIP and its SHA-256 received through the trusted AD3 delivery channel.' 'Pass -PackageArchive and -ExpectedPackageSha256; verify the hash before extraction.' }
    if ($ExpectedHash -notmatch '^[A-Fa-f0-9]{64}$') { Fail 'Expected package SHA-256 is invalid.' 'Copy the 64-character SHA-256 from the separate AD3 delivery message.' }
    $archiveFull=[IO.Path]::GetFullPath($Archive)
    if (-not (Test-Path -LiteralPath $archiveFull -PathType Leaf)) { Fail 'Original package ZIP was not found.' 'Keep the downloaded ZIP and pass its absolute path.' }
    $archiveHash=(Get-FileHash -LiteralPath $archiveFull -Algorithm SHA256).Hash
    if ($archiveHash -ne $ExpectedHash.ToUpperInvariant()) { Fail 'Original package ZIP does not match the trusted delivery SHA-256.' 'Do not extract or execute it; request a new individual package from AD3.' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($archiveFull)
    $seen=@{}
    try {
        foreach($entry in $zip.Entries) {
            if($entry.FullName.EndsWith('/')){continue}
            $name=$entry.FullName.Replace('\','/')
            if($name -match '(^/|(^|/)\.\.(/|$)|(^|/)\.(/|$)|\\|:|[\x00-\x1F])' -or $seen.ContainsKey($name)){Fail 'Trusted ZIP has an unsafe or duplicate path.' 'Request a new package from AD3.'}
            $path=Join-Path $Root $name.Replace('/',[IO.Path]::DirectorySeparatorChar)
            if(-not (Test-Path -LiteralPath $path -PathType Leaf)){Fail "Extracted package is missing: $name" 'Extract the verified ZIP again into a new empty folder.'}
            $stream=$entry.Open();$sha=[Security.Cryptography.SHA256]::Create()
            try{$entryHash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','')}finally{$sha.Dispose();$stream.Dispose()}
            if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $entryHash){Fail "Extracted file differs from trusted ZIP: $name" 'Delete the extracted folder and extract the verified ZIP again.'}
            $seen[$name]=$true
        }
    } finally {$zip.Dispose()}
    $actual=@(Get-ChildItem -LiteralPath $Root -Recurse -File|ForEach-Object {$_.FullName.Substring($Root.Length).TrimStart('\','/').Replace('\','/')})
    if(@($actual|Where-Object {!$seen.ContainsKey($_)}).Count -or @($seen.Keys|Where-Object {$actual -notcontains $_}).Count){Fail 'Extracted folder inventory differs from the trusted ZIP.' 'Use a new empty extraction folder.'}
}
function Get-Checks {
    $wsl=Get-WslVersion; $daemon=$false; $compose=$false; $cli=[bool](Get-Command docker -ErrorAction SilentlyContinue)
    if($cli){
        try { & docker info 2>$null | Out-Null; $daemon=($LASTEXITCODE -eq 0) } catch { $daemon=$false }
        if($daemon){
            try { & docker compose version 2>$null | Out-Null; $compose=($LASTEXITCODE -eq 0) } catch { $compose=$false }
        }
    }
    return @([pscustomobject]@{check='Windows';ok=($env:OS -eq 'Windows_NT')},[pscustomobject]@{check='x64/ARM64';ok=($env:PROCESSOR_ARCHITECTURE -match 'AMD64|ARM64')},[pscustomobject]@{check='RAM >= 8 GB';ok=((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB -ge 8)},[pscustomobject]@{check='Disk >= 15 GB';ok=((Get-PSDrive -Name C).Free/1GB -ge 15)},[pscustomobject]@{check='Virtualization firmware';ok=[bool]((Get-CimInstance Win32_Processor|Select-Object -First 1).VirtualizationFirmwareEnabled)},[pscustomobject]@{check='WSL >= 2.1.5';ok=([bool]$wsl -and $wsl -ge [version]'2.1.5')},[pscustomobject]@{check='Docker CLI';ok=$cli},[pscustomobject]@{check='Docker daemon';ok=$daemon},[pscustomobject]@{check='Docker Compose';ok=$compose},[pscustomobject]@{check='Port 8080 free';ok=(-not(Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue))})
}
function Test-Checksums([string] $Root) {
    $file=Join-Path $Root 'CHECKSUMS.sha256'; if(!(Test-Path $file)){Fail 'CHECKSUMS.sha256 missing.' 'Obtain a complete signed package.'}
    $seen=@{}; foreach($line in Get-Content -LiteralPath $file){if($line -notmatch '^([a-fA-F0-9]{64})  ([^\\/][^\\]*?)$'){Fail 'Invalid checksum line.' 'Obtain a new package.'};$hash=$Matches[1].ToLower();$name=$Matches[2];if($name -match '(^|/)\.(/|$)|(^|/)\.\.(/|$)|\\|^/|:|[\x00-\x1F]' -or $seen.ContainsKey($name)){Fail 'Unsafe or duplicate checksum path.' 'Obtain a new package.'};$path=Join-Path $Root $name.Replace('/',[IO.Path]::DirectorySeparatorChar);if(!(Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() -ne $hash){Fail 'Checksum mismatch.' 'Do not install this package.'};$seen[$name]=$true}
    $actual=@(Get-ChildItem -LiteralPath $Root -Recurse -File|Where-Object {$_.Name -ne 'CHECKSUMS.sha256'}|ForEach-Object {$_.FullName.Substring($Root.Length).TrimStart('\','/').Replace('\','/')});if(@($actual|Where-Object {!$seen.ContainsKey($_)}).Count -or @($seen.Keys|Where-Object {$actual -notcontains $_}).Count){Fail 'Checksum inventory differs.' 'Do not install this package.'}
}
function Set-RestrictedEnv([string] $File, [string[]] $Lines) {
    [IO.File]::WriteAllLines($File, $Lines, [Text.Encoding]::UTF8)
    & icacls $File /inheritance:r /grant:r "$env:USERNAME`:F" | Out-Null
    if ($LASTEXITCODE) { Fail 'Could not restrict .env ACL.' 'Check NTFS permissions then rerun -Apply.' }
}
function Wait-Docker([int] $Seconds = 120) {
    $until = (Get-Date).AddSeconds($Seconds)
    do {
        & docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { & docker compose version 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { return } }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $until)
    Fail "Docker daemon/Compose was not ready within $Seconds seconds." 'Start Docker Desktop, wait for it to finish, then rerun -Resume.'
}
function Write-Marker {
    New-Item -ItemType Directory -Force -Path $MarkerRoot | Out-Null
    @{ schema=1; created=(Get-Date).ToUniversalTime().ToString('o'); mode=$Mode; destination=$Destination; packageRoot=$PackageRoot; packageArchive=$PackageArchive; expectedPackageSha256=$ExpectedPackageSha256; installWSL=[bool]$InstallWSL; installDocker=[bool]$InstallDocker; acceptTerms=[bool]$AcceptTerms; nonInteractive=[bool]$NonInteractive; provisionInstance=[bool]$ProvisionInstance; provisionInstanceName=$ProvisionInstanceName; remoteUrl=$RemoteUrl; remoteInstance=$RemoteInstance } | ConvertTo-Json | Set-Content -LiteralPath $MarkerPath -Encoding UTF8
}
function Read-Marker {
    if (-not (Test-Path $MarkerPath)) { Fail 'Resume marker not found.' 'Rerun the original installer command.' }
    $marker = Get-Content -Raw -LiteralPath $MarkerPath | ConvertFrom-Json
    if ($marker.schema -ne 1 -or -not $marker.created) { Fail 'Resume marker is invalid.' 'Delete the marker and rerun the original installer command.' }
    if (((Get-Date).ToUniversalTime() - [datetime]$marker.created.ToUniversalTime()).TotalHours -gt 24) { Fail 'Resume marker expired.' 'Rerun the original installer command within 24 hours.' }
    $script:Mode=$marker.mode; $script:Destination=$marker.destination; $script:PackageRoot=$marker.packageRoot; $script:PackageArchive=$marker.packageArchive; $script:ExpectedPackageSha256=$marker.expectedPackageSha256; $script:InstallWSL=[bool]$marker.installWSL; $script:InstallDocker=[bool]$marker.installDocker; $script:AcceptTerms=[bool]$marker.acceptTerms; $script:NonInteractive=[bool]$marker.nonInteractive; $script:ProvisionInstance=[bool]$marker.provisionInstance; $script:ProvisionInstanceName=$marker.provisionInstanceName; $script:RemoteUrl=$marker.remoteUrl; $script:RemoteInstance=$marker.remoteInstance
}
function Install-Prerequisites {
    if (($InstallWSL -or $InstallDocker) -and -not $AcceptTerms) { Fail 'Prerequisite installation requires -AcceptTerms.' 'Review vendor terms and rerun with explicit flags.' }
    if (($InstallWSL -or $InstallDocker) -and -not (Get-Command winget -ErrorAction SilentlyContinue)) { Fail 'winget is required for requested prerequisite installation.' 'Install App Installer or prepare prerequisites manually.' }
    if ($InstallWSL -and ((Get-WslVersion) -lt [version]'2.1.5')) {
        Write-Marker
        if (-not (Is-Admin)) { if (-not $Elevate) { Fail 'WSL installation needs elevation.' 'Rerun with -Elevate -InstallWSL -AcceptTerms.' }; Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Resume"; exit }
        & wsl --install
        if ($LASTEXITCODE) { Fail 'WSL installation command failed.' 'Review Windows Features/WSL output and rerun -Resume.' }
        Fail 'WSL installation may require reboot.' 'Reboot if requested, then run: powershell -File Install-AD3Evolution.ps1 -Resume'
    }
    if ($InstallDocker -and -not (Get-Command docker -ErrorAction SilentlyContinue)) {
        & winget install --id Docker.DockerDesktop --exact --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE) { Fail 'Docker Desktop installation failed.' 'Install Docker Desktop manually, start it, then rerun -Resume.' }
    }
}
function Install-Package([string] $Source, [string] $Target) {
    if ((Test-Path -LiteralPath $Target) -and @(Get-ChildItem -LiteralPath $Target -Force).Count) { Fail 'Destination is not empty.' 'Choose a new empty destination; do not overwrite an existing installation.' }
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    foreach ($item in $RequiredPackageItems) {
        $sourceItem=Join-Path $Source $item; $targetItem=Join-Path $Target $item
        if(Test-Path -LiteralPath $sourceItem -PathType Container){New-Item -ItemType Directory -Force -Path $targetItem|Out-Null;Get-ChildItem -LiteralPath $sourceItem -Force|Copy-Item -Destination $targetItem -Recurse -Force}
        else{Copy-Item -LiteralPath $sourceItem -Destination $targetItem -Force}
    }
    $skillTarget = Join-Path ($(if ($env:CODEX_HOME) {$env:CODEX_HOME} else {Join-Path $env:USERPROFILE '.codex'})) 'skills'
    New-Item -ItemType Directory -Force -Path $skillTarget | Out-Null
    $installedSkill=Join-Path $skillTarget 'ad3-whatsapp-evolution';New-Item -ItemType Directory -Force -Path $installedSkill|Out-Null;Get-ChildItem -LiteralPath (Join-Path $Target 'skill\ad3-whatsapp-evolution') -Force|Copy-Item -Destination $installedSkill -Recurse -Force
}

if ($RemoteApiKey) { Fail 'RemoteApiKey parameter is intentionally refused.' 'Use AD3_REMOTE_API_KEY or the secure prompt; never put keys in command history.' }
if ($RemoteUrl) { try {$uri=[Uri]$RemoteUrl} catch {Fail 'RemoteUrl is invalid.' 'Use http://localhost or an https URL without credentials/query/fragment.'}; if(($uri.UserInfo) -or $uri.Query -or $uri.Fragment -or -not (($uri.Scheme -eq 'https') -or ($uri.Scheme -eq 'http' -and $uri.Host -eq 'localhost'))){Fail 'RemoteUrl is not allowed.' 'Use http://localhost or HTTPS without credentials/query/fragment.'} }
if ($Resume) { Read-Marker }
Assert-RemoteUrl
if($ProvisionInstanceName -notmatch '^[A-Za-z0-9_-]{1,64}$'){Fail 'ProvisionInstanceName is unsafe.' 'Use 1-64 letters, numbers, underscore or hyphen.'}
$Destination = Test-UserPath $Destination
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$checks=Get-Checks
$checks | Format-Table | Out-Host
if ($Diagnose -or -not $Apply) { Write-Host 'Diagnose/dry-run: zero writes; only read-only WSL/Docker/port checks were performed.'; exit 0 }
$PackageRoot = Test-Package $PackageRoot
Test-TrustedArchive $PackageArchive $ExpectedPackageSha256 $PackageRoot
Test-Checksums $PackageRoot
& (Join-Path $PackageRoot 'ad3-evolution.exe') verify-package --root $PackageRoot; if($LASTEXITCODE){Fail 'Signed package verification failed.' 'Obtain a new verified package before any installation step.'}
Install-Prerequisites
 $checks=Get-Checks
if ($Mode -eq 'local' -and ($checks | Where-Object {-not $_.ok})) {Write-Marker;Fail 'Local prerequisites remain incomplete; installation stopped.' 'Start/reboot prerequisites if needed, then rerun -Resume.'}
if ($Mode -eq 'local') { if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue }; Wait-Docker }
Install-Package $PackageRoot $Destination
Test-Checksums $Destination
& (Join-Path $Destination 'ad3-evolution.exe') verify-package --root $Destination; if($LASTEXITCODE){Fail 'Copied package verification failed.' 'Delete only the incomplete destination and obtain a verified package.'}
$envFile=Join-Path $Destination '.env'; $state=Join-Path $Destination 'state'
if ($Mode -eq 'demo') { Set-RestrictedEnv $envFile @('AD3_EVOLUTION_MODE=demo',"AD3_EVOLUTION_STATE_DIR=$state") }
elseif ($Mode -eq 'remote') { if (-not $RemoteUrl -or -not $RemoteInstance) { Fail 'Remote URL and instance are required.' 'Use -RemoteUrl and -RemoteInstance.' }; $key=$env:AD3_REMOTE_API_KEY; if (-not $key -and $NonInteractive) { Fail 'Non-interactive remote install requires AD3_REMOTE_API_KEY.' 'Set it only for this process then rerun.' }; if (-not $key) {$key=Convert-SecureToPlain (Read-Host 'Evolution API key' -AsSecureString)}; Set-RestrictedEnv $envFile @('AD3_EVOLUTION_MODE=remote',"EVOLUTION_BASE_URL=$RemoteUrl","EVOLUTION_API_KEY=$key","AD3_EVOLUTION_INSTANCE=$RemoteInstance","AD3_EVOLUTION_STATE_DIR=$state") }
else { Set-RestrictedEnv $envFile @('AD3_EVOLUTION_MODE=local','EVOLUTION_BASE_URL=http://127.0.0.1:8080','AD3_EVOLUTION_INSTANCE=creator',"AD3_EVOLUTION_STATE_DIR=$state","EVOLUTION_API_KEY=$(Get-Secret)","POSTGRES_PASSWORD=$(Get-Secret)","REDIS_PASSWORD=$(Get-Secret)"); & docker compose --env-file $envFile -f (Join-Path $Destination 'deploy\local\compose.yaml') up -d; if ($LASTEXITCODE) { Fail 'Compose startup failed.' 'Run docker compose logs after correcting Docker.' }; $until=(Get-Date).AddSeconds(90); do { try {$health=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/ -TimeoutSec 3; $ready=$health.StatusCode -lt 500} catch {$ready=$false}; if(-not $ready){Start-Sleep 2} } while(-not $ready -and (Get-Date)-lt $until); if(-not $ready){Fail 'Evolution health did not become ready.' 'Run docker compose logs evolution; service was not declared successful.'} }
$exe=Join-Path $Destination 'ad3-evolution.exe'; $prior=$env:AD3_EVOLUTION_CONFIG; $env:AD3_EVOLUTION_CONFIG=$envFile; & $exe --mode $Mode doctor; if($LASTEXITCODE){Fail 'Protected executable license/doctor failed.' 'Verify manifest/signature beside the executable.'}; $env:AD3_EVOLUTION_CONFIG=$prior
if($Mode -eq 'local' -and $ProvisionInstance){New-Item -ItemType Directory -Force $state|Out-Null;$qr=Join-Path $state "qr-$ProvisionInstanceName.png"; $existing=& $exe --mode local instance list | ConvertFrom-Json; if($existing | Where-Object {$_.name -eq $ProvisionInstanceName}){$plan=& $exe --mode local instance connect-plan --instance $ProvisionInstanceName --qr-file $qr | ConvertFrom-Json}else{$plan=& $exe --mode local instance create-plan --instance $ProvisionInstanceName --qr-file $qr | ConvertFrom-Json}; & $exe --mode local apply --plan-id $plan.id --confirm $plan.id; if($LASTEXITCODE){Fail 'QR provision plan failed.' 'Check instance status; do not retry blindly.'}; Write-Host "Scan authorized QR at: $qr"}
if($Mode -eq 'local' -and $NonInteractive -and -not $ProvisionInstance){Write-Host 'Noninteractive local install did not provision a QR; pass -ProvisionInstance only with explicit consent.'}
if (Test-Path $MarkerPath) { Remove-Item -LiteralPath $MarkerPath -Force }
Write-Host 'Package installed. Keep the PC powered and awake for local operation.'
