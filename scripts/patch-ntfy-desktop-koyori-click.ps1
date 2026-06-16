# Patch ntfy-desktop: toast click opens Koyori room (ntfy Click header).
#
# Windows ntfytoast has no URL flag. Toast body click often foregrounds ntfy-desktop
# without firing toasted-notifier's callback. This patch:
#   1. stages open URL to ~/.config/embodied-claude/ntfy-pending-open.url
#   2. opens via shell.openExternal on pipe callback (broad action match)
#   3. falls back on guiMain 'show' if callback never fires (common on Win11)
#
# Usage:
#   .\scripts\patch-ntfy-desktop-koyori-click.ps1
#   .\scripts\patch-ntfy-desktop-koyori-click.ps1 -Force

param(
    [string]$NtfyDesktopDir = "C:\Programs\ntfy-desktop-2.2.0-win32-amd64",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$Asar = Join-Path $NtfyDesktopDir "resources\app.asar"
$Backup = "$Asar.bak"
if (-not (Test-Path $Asar)) {
    Write-Error "app.asar not found: $Asar"
}

$ExtractDir = Join-Path $env:TEMP "ntfy-asar-patch-click"
if (Test-Path $ExtractDir) {
    Remove-Item $ExtractDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null

if ($Force -and (Test-Path $Backup)) {
    Write-Host "Restoring app.asar from backup before re-patch..."
    Copy-Item $Backup $Asar -Force
}

Write-Host "Extracting app.asar..."
Push-Location (Join-Path $Repo "presence-ui")
try {
    npx --yes @electron/asar extract $Asar $ExtractDir | Out-Null
} finally {
    Pop-Location
}

$IndexPath = Join-Path $ExtractDir "index.js"
$content = Get-Content $IndexPath -Raw -Encoding UTF8

$hasHelpers = $content -match 'function stageKoyoriToastOpenUrl'
$hasFocus = $content -match "guiMain\.on\(\s*'focus'"
if ($hasHelpers -and $hasFocus) {
    Write-Host "Already patched (Koyori toast open helpers present)."
    exit 0
}

if (-not $hasHelpers) {

$helperAnchor = "let isPolling = false;              // prevent concurrent polling"
$helpers = @'

const koyoriPendingOpenPath = path.join( app.getPath( 'home' ), '.config', 'embodied-claude', 'ntfy-pending-open.url' );
let koyoriLastOpenAt = 0;
let koyoriLastOpenUrl = '';

function stageKoyoriToastOpenUrl( url )
{
    if ( !url || typeof url !== 'string' ) return;
    try
    {
        fs.mkdirSync( path.dirname( koyoriPendingOpenPath ), { recursive: true } );
        fs.writeFileSync( koyoriPendingOpenPath, url.trim(), 'utf8' );
    }
    catch ( error )
    {
        Log.warn( `core`, chalk.yellow( `[toast]` ), chalk.white( `:  ` ),
            chalk.yellowBright( `<msg>` ), chalk.gray( `Failed to stage open URL` ),
            chalk.yellowBright( `<error>` ), chalk.gray( `${ error.message }` ) );
    }
}

function shouldOpenKoyoriFromToast( response, metadata )
{
    const action = String( ( metadata && metadata.action ) || response || '' ).toLowerCase();
    if ( !action ) return false;
    if ( action === 'dismissed' || action === 'timeout' || action === 'timedout' || action === 'hidden' ) return false;
    return action.includes( 'click' ) || action.includes( 'activ' ) || action === 'buttonpressed';
}

function openKoyoriToastTarget( url )
{
    const target = ( url || '' ).trim();
    if ( !target ) return;
    const now = Date.now();
    if ( target === koyoriLastOpenUrl && now - koyoriLastOpenAt < 2000 ) return;
    koyoriLastOpenAt = now;
    koyoriLastOpenUrl = target;
    try { if ( fs.existsSync( koyoriPendingOpenPath ) ) fs.unlinkSync( koyoriPendingOpenPath ); } catch ( e ) {}
    shell.openExternal( target );
}

function consumeKoyoriPendingOpenUrl( maxAgeMs = 30000 )
{
    try
    {
        if ( !fs.existsSync( koyoriPendingOpenPath ) ) return;
        const stat = fs.statSync( koyoriPendingOpenPath );
        if ( Date.now() - stat.mtimeMs > maxAgeMs )
        {
            fs.unlinkSync( koyoriPendingOpenPath );
            return;
        }
        const url = fs.readFileSync( koyoriPendingOpenPath, 'utf8' ).trim();
        openKoyoriToastTarget( url );
    }
    catch ( error )
    {
        Log.warn( `core`, chalk.yellow( `[toast]` ), chalk.white( `:  ` ),
            chalk.yellowBright( `<msg>` ), chalk.gray( `Pending open URL failed` ),
            chalk.yellowBright( `<error>` ), chalk.gray( `${ error.message }` ) );
    }
}

'@

if (-not $content.Contains($helperAnchor)) {
    Write-Error "Helper anchor not found in index.js"
}
$content = $content.Replace($helperAnchor, $helpers + $helperAnchor)

$notifyOldPartial = @'
            const openUrl = object.click || 'http://127.0.0.1:8090/';
            toasted.notify({
                title: `${ topic } - ${ dateHuman }`,
                subtitle: `${ dateHuman }`,
                message: `${ message }`,
                sound: 'Pop',
                open: openUrl,
                persistent: cfgPersistent,
                sticky: cfgPersistent
            }, ( err, response ) =>
            {
                if ( err || !response ) return;
                const clicked = response === 'activate' || response === 'click' || response === 'clicked';
                if ( clicked && openUrl )
                    shell.openExternal( openUrl );
            });
'@

$notifyOldOriginal = @'
            toasted.notify({
                title: `${ topic } - ${ dateHuman }`,
                subtitle: `${ dateHuman }`,
                message: `${ message }`,
                sound: 'Pop',
                open: cfgInstanceURL,
                persistent: cfgPersistent,
                sticky: cfgPersistent
            });
'@

$notifyNew = @'
            const openUrl = object.click || 'http://127.0.0.1:8090/';
            stageKoyoriToastOpenUrl( openUrl );
            toasted.notify({
                title: `${ topic } - ${ dateHuman }`,
                subtitle: `${ dateHuman }`,
                message: `${ message }`,
                sound: 'Pop',
                open: openUrl,
                persistent: cfgPersistent,
                sticky: cfgPersistent
            }, ( err, response, metadata ) =>
            {
                if ( shouldOpenKoyoriFromToast( response, metadata ) )
                    openKoyoriToastTarget( openUrl );
            });
'@

$notifyPatched = $false
if ($content.Contains($notifyOldPartial)) {
    $content = $content.Replace($notifyOldPartial, $notifyNew)
    $notifyPatched = $true
} elseif ($content.Contains($notifyOldOriginal)) {
    $content = $content.Replace($notifyOldOriginal, $notifyNew)
    $notifyPatched = $true
}
if (-not $notifyPatched -and -not $hasHelpers) {
    Write-Error "Expected toasted.notify block not found in index.js"
}

$readyAnchor = "    initializeMenus();"
$readyHook = @'
    initializeMenus();

    toasted.on( 'click', ( _obj, options ) =>
    {
        if ( options && options.open )
            openKoyoriToastTarget( options.open );
    });

'@

if (-not $content.Contains($readyAnchor)) {
    Write-Error "ready() anchor not found"
}
if ($content -notmatch "toasted\.on\(\s*'click'") {
    $content = $content.Replace($readyAnchor, $readyHook)
}

} # end if (-not $hasHelpers)

$showAnchor = "    guiMain.webContents.on( 'dom-ready', () =>"
$showHook = @'
    guiMain.on( 'show', () =>
    {
        consumeKoyoriPendingOpenUrl( 30000 );
    });

    guiMain.on( 'focus', () =>
    {
        consumeKoyoriPendingOpenUrl( 30000 );
    });

    guiMain.webContents.on( 'dom-ready', () =>
'@

if (-not $content.Contains($showAnchor)) {
    Write-Error "guiMain dom-ready anchor not found"
}
if ($content -notmatch "guiMain\.on\(\s*'show'") {
    $content = $content.Replace($showAnchor, $showHook)
} elseif (-not $hasFocus) {
    $showBlock = @'
    guiMain.on( 'show', () =>
    {
        consumeKoyoriPendingOpenUrl( 30000 );
    });

'@
    $showBlockWithFocus = $showBlock + @'
    guiMain.on( 'focus', () =>
    {
        consumeKoyoriPendingOpenUrl( 30000 );
    });

'@
    $content = $content.Replace($showBlock, $showBlockWithFocus)
}

Set-Content -Path $IndexPath -Value $content -Encoding UTF8 -NoNewline

if (-not (Test-Path $Backup)) {
    Copy-Item $Asar $Backup
    Write-Host "Backup: $Backup"
}

Write-Host "Repacking app.asar..."
Push-Location (Join-Path $Repo "presence-ui")
try {
    npx --yes @electron/asar pack $ExtractDir $Asar | Out-Null
} finally {
    Pop-Location
}

Write-Host "Patched: toast click -> Koyori room (callback + show fallback)."
Write-Host "Restart ntfy-desktop, then:"
Write-Host "  .\scripts\setup-ntfy-ma-home.ps1 -TestOnly"
