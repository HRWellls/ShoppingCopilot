param(
    [string]$MirrorPath = "../demo/video-assets"
)

$ErrorActionPreference = "Stop"
$edgeCandidates = @(
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe"
)
$edge = $edgeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $edge) { throw "Microsoft Edge was not found." }

$root = [IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$workspace = [IO.Path]::GetFullPath((Split-Path -Parent $root))
$index = Join-Path $root "index.html"
$output = [IO.Path]::GetFullPath((Join-Path $root "assets"))
$staging = [IO.Path]::GetFullPath((Join-Path $root ".asset-staging"))
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())

foreach ($path in @($output, $staging)) {
    if (-not $path.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Asset path escaped the recording package: $path"
    }
}

$html = Get-Content -Raw -Encoding UTF8 -LiteralPath $index
$match = [regex]::Match(
    $html,
    '<script type="application/json" id="frame-manifest">\s*([\s\S]*?)\s*</script>'
)
if (-not $match.Success) { throw "Embedded frame manifest was not found." }
$frames = $match.Groups[1].Value | ConvertFrom-Json
if ($frames.Count -ne 54) { throw "Expected 54 manifest frames, found $($frames.Count)." }
$duplicateIds = @($frames | Group-Object id | Where-Object Count -gt 1)
$duplicateFiles = @($frames | Group-Object filename | Where-Object Count -gt 1)
if ($duplicateIds.Count -or $duplicateFiles.Count) { throw "Frame IDs and filenames must be unique." }

if (Test-Path -LiteralPath $staging) { Remove-Item -Recurse -Force -LiteralPath $staging }
New-Item -ItemType Directory -Force -Path $staging | Out-Null
$baseUri = ([uri](Resolve-Path -LiteralPath $index).Path).AbsoluteUri

foreach ($frame in $frames) {
    $profile = Join-Path $tempRoot ("shopping-copilot-assets-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Force -Path $profile | Out-Null
    try {
        $target = Join-Path $staging $frame.filename
        $url = $baseUri + "?frame=" + [uri]::EscapeDataString($frame.id)
        $arguments = @(
            "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1920,1080",
            "--user-data-dir=`"$profile`"", "--screenshot=`"$target`"", $url
        )
        $process = Start-Process -FilePath $edge -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
        if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $target)) {
            throw "Failed to export $($frame.id) to $($frame.filename)."
        }
    } finally {
        $resolvedProfile = [IO.Path]::GetFullPath($profile)
        if ($resolvedProfile.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            try { Remove-Item -Recurse -Force -LiteralPath $resolvedProfile -ErrorAction Stop } catch { }
        }
    }
}

$staged = @(Get-ChildItem -LiteralPath $staging -Filter "*.png" -File)
if ($staged.Count -ne $frames.Count) { throw "Staging contains $($staged.Count) PNGs, expected $($frames.Count)." }

New-Item -ItemType Directory -Force -Path $output | Out-Null
Get-ChildItem -LiteralPath $output -Filter "*.png" -File | Remove-Item -Force
Copy-Item -Force -LiteralPath $staged.FullName -Destination $output

if ($MirrorPath) {
    $resolvedMirror = [IO.Path]::GetFullPath((Join-Path $root $MirrorPath))
    if (-not $resolvedMirror.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Mirror path escaped the workspace: $resolvedMirror"
    }
    New-Item -ItemType Directory -Force -Path $resolvedMirror | Out-Null
    Get-ChildItem -LiteralPath $resolvedMirror -Filter "*.png" -File | Remove-Item -Force
    Copy-Item -Force -LiteralPath $staged.FullName -Destination $resolvedMirror
}

Remove-Item -Recurse -Force -LiteralPath $staging
Write-Host "Exported $($frames.Count) manifest-driven recording assets at 1920x1080."
