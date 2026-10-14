# LinkedIn Coach - one-time setup for Windows.
# Run it by double-clicking setup.cmd. Safe to run again at any time.
#
#   -CI          automated test mode: install and configure everything, skip the LinkedIn sign-in.
#   -UnipileKey  optional Unipile API key (otherwise setup asks; Enter skips).
#
# Everything is installed inside this folder (tools\), pinned to tested versions and checked
# against published SHA-256 hashes. Nothing is added to PATH and no admin rights are needed.
#
# Keep this file ASCII-only: Windows PowerShell 5.1 misreads non-ASCII in scripts saved without a BOM.

param([switch]$CI, [string]$UnipileKey = '')

# 'Continue', not 'Stop': in Windows PowerShell 5.1, redirecting a native tool's stderr (uv prints
# progress there) turns each line into an error record, and 'Stop' would abort setup on it.
# Every native call below checks $LASTEXITCODE instead.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Kit = $PSScriptRoot
$Tools = Join-Path $Kit 'tools'
$UvVersion = '0.12.0'
$NodeVersion = '24.21.0'
$LinkedInMcp = 'mcp-server-linkedin@4.27.0'
$Arm = ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64')
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Step($n, $text) { Write-Host ""; Write-Host "[$n/8] $text" -ForegroundColor Cyan }
function Ok($text)       { Write-Host "      OK  $text" -ForegroundColor Green }
function Warn($text)     { Write-Host "      !!  $text" -ForegroundColor Yellow }
function Fail($text) {
    Write-Host ""
    Write-Host "SETUP STOPPED: $text" -ForegroundColor Red
    Write-Host "Take a screenshot of this window and send it to whoever gave you this kit."
    exit 1
}
function To-JsonPath($p) { return ($p -replace '\\', '/') }

# Download $url to $file and check it against $sha256. Retries twice on network errors.
function Get-Verified($url, $file, $sha256) {
    for ($i = 1; $i -le 3; $i++) {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $file
            break
        } catch {
            if ($i -eq 3) { Fail "Download failed: $url ($($_.Exception.Message))" }
            Start-Sleep -Seconds 3
        }
    }
    $actual = (Get-FileHash -Algorithm SHA256 -Path $file).Hash.ToLower()
    if ($actual -ne $sha256.ToLower()) { Fail "Downloaded file does not match its published hash: $url" }
}

# Unzip with the built-in tar.exe when present (much faster than Expand-Archive).
function Expand-Zip($zip, $dest) {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
    if (Test-Path $tar) {
        & $tar -xf $zip -C $dest
        if ($LASTEXITCODE -eq 0) { return }
    }
    Expand-Archive -Path $zip -DestinationPath $dest -Force
}

Write-Host "LinkedIn Coach setup" -ForegroundColor White
Write-Host "Folder: $Kit"
if ($Kit -match '[^\x00-\x7F]') {
    Warn "This folder's path contains non-English characters. If anything fails, move the folder to C:\linkedin-coach and run setup again."
}
# Files extracted from a downloaded zip carry an "from the internet" mark; clear it for the kit.
Get-ChildItem -Path $Kit -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Tools | Out-Null
$tmp = Join-Path $Tools '_download'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# ---------------------------------------------------------------- 1. uv (runs the LinkedIn reader)
Step 1 "Installing uv $UvVersion"
$uvDir = Join-Path $Tools 'uv'
$uvx = Join-Path $uvDir 'uvx.exe'
$haveUv = (Test-Path $uvx) -and ((& (Join-Path $uvDir 'uv.exe') --version) -match [regex]::Escape($UvVersion))
if (-not $haveUv) {
    $target = 'x86_64-pc-windows-msvc'
    if ($Arm) { $target = 'aarch64-pc-windows-msvc' }
    $name = "uv-$target.zip"
    $base = "https://github.com/astral-sh/uv/releases/download/$UvVersion"
    try { $hashLine = (Invoke-WebRequest -UseBasicParsing -Uri "$base/$name.sha256").Content }
    catch { Fail "Could not reach GitHub to download uv. Check your internet connection." }
    if ($hashLine -is [byte[]]) { $hashLine = [System.Text.Encoding]::ASCII.GetString($hashLine) }
    $sha = ($hashLine.Trim() -split '\s+')[0]
    $zip = Join-Path $tmp $name
    Get-Verified "$base/$name" $zip $sha
    if (Test-Path $uvDir) { Remove-Item -Recurse -Force $uvDir }
    Expand-Zip $zip $uvDir
}
if (-not (Test-Path $uvx)) { Fail 'uv did not install.' }
Ok "uv $UvVersion"

# ---------------------------------------------------------------- 2. Node.js (runs the browser tool)
Step 2 "Installing Node.js $NodeVersion (portable)"
$nodeDir = Join-Path $Tools 'node'
$node = Join-Path $nodeDir 'node.exe'
$haveNode = (Test-Path $node) -and ((& $node --version) -eq "v$NodeVersion")
if (-not $haveNode) {
    $plat = 'win-x64'
    if ($Arm) { $plat = 'win-arm64' }
    $folder = "node-v$NodeVersion-$plat"
    $base = "https://nodejs.org/dist/v$NodeVersion"
    try { $sums = (Invoke-WebRequest -UseBasicParsing -Uri "$base/SHASUMS256.txt").Content }
    catch { Fail "Could not reach nodejs.org. Check your internet connection." }
    if ($sums -is [byte[]]) { $sums = [System.Text.Encoding]::ASCII.GetString($sums) }
    $line = ($sums -split "`n") | Where-Object { $_ -match [regex]::Escape("$folder.zip") } | Select-Object -First 1
    if (-not $line) { Fail "No published hash for $folder.zip" }
    $sha = ($line.Trim() -split '\s+')[0]
    $zip = Join-Path $tmp "$folder.zip"
    Get-Verified "$base/$folder.zip" $zip $sha
    $unpack = Join-Path $tmp 'node-unpack'
    if (Test-Path $unpack) { Remove-Item -Recurse -Force $unpack }
    Expand-Zip $zip $unpack
    if (Test-Path $nodeDir) { Remove-Item -Recurse -Force $nodeDir }
    Move-Item -Path (Join-Path $unpack $folder) -Destination $nodeDir
}
if (-not (Test-Path $node)) { Fail 'Node.js did not install.' }
$npm = Join-Path $nodeDir 'npm.cmd'
Ok "node $(& $node --version)"

# ---------------------------------------------------------------- 3. Browser
Step 3 'Checking the browser'
$chromePaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$browser = 'msedge'
foreach ($p in $chromePaths) { if ($p -and (Test-Path $p)) { $browser = 'chrome'; break } }
if ($browser -eq 'chrome') { Ok 'Google Chrome found' } else { Warn 'Google Chrome not found, using Microsoft Edge instead' }

# ---------------------------------------------------------------- 4. Browser tool
Step 4 'Installing the browser tool'
Push-Location $Tools
$env:Path = "$nodeDir;$env:Path"   # npm's scripts look for node on PATH, for this window only
& $npm install --no-audit --no-fund --loglevel=error | Out-Host
$npmExit = $LASTEXITCODE
Pop-Location
if ($npmExit -ne 0) { Fail 'npm install failed.' }
$cli = Join-Path $Tools 'node_modules\@playwright\mcp\cli.js'
if (-not (Test-Path $cli)) { Fail 'The browser tool did not install.' }
Ok ("browser tool " + (& $node $cli --version))

# ---------------------------------------------------------------- 5. LinkedIn reader + sign-in
Step 5 'Preparing the LinkedIn reader (first time downloads ~250 MB, a few minutes)'
$python = '3.13'
if ($Arm) {
    # cryptography has no Windows-on-ARM wheel; x64 Python runs under emulation and installs cleanly.
    $python = 'cpython-3.13-windows-x86_64-none'
    Warn 'ARM laptop detected: using x64 Python.'
}
$env:UV_HTTP_TIMEOUT = '300'
& $uvx --python $python $LinkedInMcp --help *> $null
if ($LASTEXITCODE -ne 0) { Fail 'The LinkedIn reader could not be installed.' }
Ok 'LinkedIn reader installed'

$status = (& $uvx --python $python $LinkedInMcp --no-auto-import --status 2>&1) | Out-String
$loggedIn = $status -match 'Session is valid'
if ($status -match 'Browser installed|No valid source session|Session is valid') { Ok 'LinkedIn reader browser ready' }
else { Write-Host $status; Fail 'The LinkedIn reader could not prepare its browser.' }
if ($loggedIn) {
    Ok 'Already signed in to LinkedIn'
} elseif ($CI) {
    Warn 'CI mode: skipping LinkedIn sign-in'
} else {
    Write-Host ''
    Write-Host '      A browser window will open. Sign in to LinkedIn there (normal sign-in, including any code LinkedIn sends you).' -ForegroundColor White
    Write-Host '      The window closes by itself when you are signed in. You have 30 minutes.' -ForegroundColor White
    & $uvx --python $python $LinkedInMcp --no-auto-import --login | Out-Host
    $status = (& $uvx --python $python $LinkedInMcp --no-auto-import --status 2>&1) | Out-String
    if ($status -match 'Session is valid') { Ok 'Signed in to LinkedIn'; $loggedIn = $true }
    else { Warn 'LinkedIn sign-in not confirmed. The coach will ask you to sign in when it starts.' }
}

# ---------------------------------------------------------------- 6. Coach browser profile
Step 6 'Preparing the coach browser'
if ($loggedIn -and -not $CI) {
    & $node (Join-Path $Tools 'seed-browser-login.mjs') --browser $browser | Out-Host
    if ($LASTEXITCODE -eq 0) { Ok 'Coach browser is signed in to LinkedIn' }
    else { Warn 'Could not copy the sign-in. The coach will ask you to sign in once in its browser window.' }
} else {
    Warn 'Skipped (no LinkedIn sign-in yet).'
}

# ---------------------------------------------------------------- 7. Unipile (optional)
Step 7 'Unipile API key (optional: lets the coach edit through an API instead of the browser)'
$unipileFile = Join-Path $Tools 'unipile.json'
$key = $UnipileKey
if (-not $key -and -not $CI) {
    if (Test-Path $unipileFile) { Write-Host '      A Unipile key is already saved. Press Enter to keep it.' }
    Write-Host '      Paste your Unipile API key and press Enter, or just press Enter to skip.' -ForegroundColor White
    $secure = Read-Host -AsSecureString '      Unipile API key'
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}
if ($key) {
    $key = ($key.Trim() -replace '[\\"\s]', '')
    [System.IO.File]::WriteAllText($unipileFile, ('{"api_key": "' + $key + '"}'), $utf8NoBom)
    Ok 'Unipile key saved (kept only in this folder)'
} elseif (Test-Path $unipileFile) {
    Ok 'Keeping the saved Unipile key'
} else {
    Warn 'No Unipile key: the coach will make edits in the browser instead.'
}

# ---------------------------------------------------------------- 8. OpenCode config
Step 8 'Writing the OpenCode configuration'
$template = Get-Content -Raw -Path (Join-Path $Kit 'opencode.template.json')
$config = $template.Replace('__UVX__', (To-JsonPath $uvx))
$config = $config.Replace('__NODE__', (To-JsonPath $node))
$config = $config.Replace('__KIT__', (To-JsonPath $Kit))
$config = $config.Replace('__BROWSER__', $browser)
$config = $config.Replace('__PYTHON__', $python)
try { $null = $config | ConvertFrom-Json } catch { Fail 'The generated configuration is not valid JSON.' }
[System.IO.File]::WriteAllText((Join-Path $Kit 'opencode.json'), $config, $utf8NoBom)
foreach ($d in 'inbox', 'output') { New-Item -ItemType Directory -Force -Path (Join-Path $Kit $d) | Out-Null }
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Ok 'opencode.json written'

Write-Host ''
Write-Host '==================================================================' -ForegroundColor Green
Write-Host ' Setup finished.' -ForegroundColor Green
Write-Host ''
Write-Host ' Next:'
Write-Host '  1. Open the OpenCode app.'
Write-Host "  2. Open this folder as a project:  $Kit"
Write-Host '  3. Type  hi  and press Enter. The coach takes it from there.'
Write-Host ''
Write-Host ' Optional: put your old CV, certificates, a photo, or an old ChatGPT'
Write-Host " chat (saved as a .txt file) into:  $Kit\inbox"
Write-Host ''
Write-Host ' Do not move this folder after setup. If you do, run setup.cmd again.'
Write-Host '==================================================================' -ForegroundColor Green
exit 0
