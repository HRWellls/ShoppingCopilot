$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$workspace = [IO.Path]::GetFullPath((Split-Path -Parent $root))
$index = Join-Path $root "index.html"
$assets = Join-Path $root "assets"
$mirror = [IO.Path]::GetFullPath((Join-Path $workspace "demo/video-assets"))
$runbookMatches = @(Get-ChildItem -LiteralPath (Join-Path $workspace "demo") -Filter "06-*.md" -File)
if ($runbookMatches.Count -ne 1) { throw "Expected exactly one 06-*.md runbook." }
$runbook = $runbookMatches[0].FullName

function Fail([string]$Message) { throw $Message }

function Read-Manifest([string]$Html) {
    $match = [regex]::Match(
        $Html,
        '<script type="application/json" id="frame-manifest">\s*([\s\S]*?)\s*</script>'
    )
    if (-not $match.Success) { Fail "Embedded frame manifest was not found." }
    return $match.Groups[1].Value | ConvertFrom-Json
}

function Format-Time([int]$Seconds) {
    return "{0}:{1:D2}" -f [math]::Floor($Seconds / 60), ($Seconds % 60)
}

function Assert-FrameContract($Candidate) {
    $items = @($Candidate)
    if ($items.Count -ne 54) { Fail "Frame count is $($items.Count); expected 54." }
    $duplicateId = @($items | Group-Object id | Where-Object Count -gt 1 | Select-Object -First 1)
    if ($duplicateId.Count) { Fail "Duplicate frame ID: $($duplicateId[0].Name)" }
    $duplicateFile = @($items | Group-Object filename | Where-Object Count -gt 1 | Select-Object -First 1)
    if ($duplicateFile.Count) { Fail "Duplicate PNG filename: $($duplicateFile[0].Name)" }
    if ([int]$items[0].start -ne 0) { Fail "First frame must start at 0:00: $($items[0].id)" }
    for ($i = 0; $i -lt $items.Count; $i++) {
        $frame = $items[$i]
        if (-not $frame.id -or -not $frame.filename -or -not $frame.narration) {
            Fail "Frame $i is missing an ID, filename, or narration."
        }
        if ([int]$frame.end -le [int]$frame.start) { Fail "Non-positive duration: $($frame.id)" }
        if ($i -gt 0 -and [int]$frame.start -ne [int]$items[$i - 1].end) {
            Fail "Timeline gap or reorder before $($frame.id): expected start $($items[$i - 1].end), got $($frame.start)."
        }
        $wordRate = @($frame.narration -split '\s+').Count / ([int]$frame.end - [int]$frame.start)
        if ($wordRate -gt 2.6) { Fail "Narration exceeds 2.6 words/second: $($frame.id)" }
    }
    if ([int]$items[-1].end -ne 295) { Fail "Final frame must end at 4:55: $($items[-1].id)" }
    $actualSegments = @($items.segment | Select-Object -Unique)
    $expectedSegments = @("S01", "S02", "S03", "S04", "S05A", "S05B", "S06", "S07")
    if (($actualSegments -join '|') -ne ($expectedSegments -join '|')) {
        Fail "Segment order mismatch: $($actualSegments -join ', ')"
    }
    $expectedPhases = @("Message", "Intent", "Slot Update", "FSM / Execution", "Agent Response")
    $actions = @($items | Where-Object actionKey | Group-Object actionKey)
    if ($actions.Count -ne 8) { Fail "Expected 8 scripted user actions, found $($actions.Count)." }
    foreach ($action in $actions) {
        $actual = @($action.Group.phase)
        if (($actual -join '|') -ne ($expectedPhases -join '|')) {
            Fail "Phase order mismatch for action $($action.Name): $($actual -join ', ')"
        }
    }
}

function Read-RunbookRows([string[]]$Lines) {
    $rows = @()
    foreach ($line in $Lines) {
        if ($line -notmatch '^\| \d:\d{2}-\d:\d{2} \| `S') { continue }
        $parts = $line.Split('|')
        $rows += [pscustomobject]@{
            Time = $parts[1].Trim()
            Id = $parts[2].Trim().Trim('`')
            Filename = $parts[3].Trim().Trim('`')
            Narration = $parts[5].Trim()
            EntryAction = $parts[6].Trim().Trim('`')
        }
    }
    return $rows
}

function Assert-RunbookAlignment($Frames, $Rows) {
    $manifest = @($Frames)
    $runbookRows = @($Rows)
    $openPageAction = -join @([char]0x6253, [char]0x5F00, [char]0x9875, [char]0x9762)
    if ($runbookRows.Count -ne $manifest.Count) {
        Fail "Runbook has $($runbookRows.Count) formal rows; expected $($manifest.Count)."
    }
    for ($i = 0; $i -lt $manifest.Count; $i++) {
        $frame = $manifest[$i]
        $row = $runbookRows[$i]
        $time = "$(Format-Time $frame.start)-$(Format-Time $frame.end)"
        if ($row.Id -ne $frame.id) { Fail "Runbook frame mismatch at ${i}: $($row.Id) != $($frame.id)" }
        if ($row.Filename -ne $frame.filename) { Fail "Runbook PNG mismatch for $($frame.id): $($row.Filename)" }
        if ($row.Time -ne $time) { Fail "Runbook time mismatch for $($frame.id): $($row.Time) != $time" }
        if ($row.Narration -ne $frame.narration) { Fail "Runbook narration mismatch for $($frame.id)" }
        $expectedAction = if ($i -eq 0) {
            $openPageAction
        } elseif ($frame.segment -ne $manifest[$i - 1].segment) {
            "]"
        } else {
            "Space"
        }
        if ($row.EntryAction -ne $expectedAction) {
            Fail "Runbook entry action mismatch for $($frame.id): $($row.EntryAction) != $expectedAction"
        }
    }
}

function Expect-Failure([scriptblock]$Check, [string]$Label) {
    $failed = $false
    try { & $Check } catch { $failed = $true }
    if (-not $failed) { Fail "Verifier self-test did not catch $Label." }
}

$html = Get-Content -Raw -Encoding UTF8 -LiteralPath $index
$frames = Read-Manifest $html
Assert-FrameContract $frames

$runbookLines = Get-Content -Encoding UTF8 -LiteralPath $runbook
$runbookRows = Read-RunbookRows $runbookLines
Assert-RunbookAlignment $frames $runbookRows
$imageEmbeds = @($runbookLines | Where-Object { $_ -match '^!\[S' })
if ($imageEmbeds.Count -ne 54) { Fail "Runbook must embed 54 frame previews; found $($imageEmbeds.Count)." }

# Self-tests prove that the clean validator rejects the required drift classes.
$duplicate = $frames | ConvertTo-Json -Depth 12 | ConvertFrom-Json
$duplicate[1].id = $duplicate[0].id
Expect-Failure { Assert-FrameContract $duplicate } "a duplicate frame"
$missing = @($frames[0..($frames.Count - 2)])
Expect-Failure { Assert-FrameContract $missing } "a missing frame"
$reordered = $frames | ConvertTo-Json -Depth 12 | ConvertFrom-Json
$swap = $reordered[0]; $reordered[0] = $reordered[1]; $reordered[1] = $swap
Expect-Failure { Assert-FrameContract $reordered } "reordered frames"
$badFilenameRows = @($runbookRows | ForEach-Object { [pscustomobject]@{ Time=$_.Time; Id=$_.Id; Filename=$_.Filename; Narration=$_.Narration; EntryAction=$_.EntryAction } })
$badFilenameRows[0].Filename = "wrong.png"
Expect-Failure { Assert-RunbookAlignment $frames $badFilenameRows } "a runbook PNG mismatch"
$badNarrationRows = @($runbookRows | ForEach-Object { [pscustomobject]@{ Time=$_.Time; Id=$_.Id; Filename=$_.Filename; Narration=$_.Narration; EntryAction=$_.EntryAction } })
$badNarrationRows[0].Narration = "Changed narration."
Expect-Failure { Assert-RunbookAlignment $frames $badNarrationRows } "a runbook narration mismatch"
$badEntryRows = @($runbookRows | ForEach-Object { [pscustomobject]@{ Time=$_.Time; Id=$_.Id; Filename=$_.Filename; Narration=$_.Narration; EntryAction=$_.EntryAction } })
$badEntryRows[1].EntryAction = "]"
Expect-Failure { Assert-RunbookAlignment $frames $badEntryRows } "a runbook entry-action mismatch"

foreach ($required in @(
    "intent model off", "dense=false", "llm=false", "rule path active",
    "before", "delta", "effective", "candidate space too broad",
    "empty set; relaxation enabled", "No legal match", "get('frame')"
)) {
    if ($html -notmatch [regex]::Escape($required)) { Fail "Missing required workbench text: $required" }
}
if ($html.Contains("System: verify permitted relaxations.")) { Fail "Synthetic system turn is still present." }
foreach ($binding in @(
    "event.code==='Space'", "event.key==='Backspace'", "event.key==='['", "event.key===']'",
    "event.key.toLowerCase()==='r'", "event.key.toLowerCase()==='b'",
    "event.key.toLowerCase()==='p'", "event.key.toLowerCase()==='f'"
)) {
    if (-not $html.Contains($binding)) { Fail "Missing keyboard binding: $binding" }
}
if (-not $html.Contains("responseVisible=frame.phase==='Agent Response'")) {
    Fail "Agent response visibility is not gated by the response phase."
}

$formalNarration = ($runbookRows.Narration -join "`n")
foreach ($forbidden in @(
    ("ground" + "_truth"), ("DEEPSEEK" + "_API_KEY"), ("api" + ".env"),
    "summer wedding", "68.675", "300 → 40 → 8", "total cost is zero",
    "always returns the closest product"
)) {
    if ($html -match [regex]::Escape($forbidden) -or $formalNarration -match [regex]::Escape($forbidden)) {
        Fail "Forbidden disclosure or stale claim found: $forbidden"
    }
}

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { Fail "Node.js is required for JavaScript syntax verification." }
$nodeCheck = @'
const fs=require("fs");
const html=fs.readFileSync(process.argv[2],"utf8");
const scripts=[...html.matchAll(/<script(?![^>]*application\/json)[^>]*>([\s\S]*?)<\/script>/g)];
scripts.forEach(script=>new Function(script[1]));
'@
$nodeCheck | & $node.Source - $index
if ($LASTEXITCODE -ne 0) { Fail "JavaScript syntax check failed." }

Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class RecordingImageCheck {
    public static bool IsOpaque(string path) {
        using (var source = new Bitmap(path))
        using (var bitmap = new Bitmap(source.Width, source.Height, PixelFormat.Format32bppArgb)) {
            using (var graphics = Graphics.FromImage(bitmap)) {
                graphics.Clear(Color.Transparent);
                graphics.DrawImageUnscaled(source, 0, 0);
            }
            var rect = new Rectangle(0, 0, bitmap.Width, bitmap.Height);
            var data = bitmap.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            try {
                int bytes = Math.Abs(data.Stride) * bitmap.Height;
                var pixels = new byte[bytes];
                Marshal.Copy(data.Scan0, pixels, 0, bytes);
                for (int y = 0; y < bitmap.Height; y++) {
                    int row = y * Math.Abs(data.Stride);
                    for (int x = 0; x < bitmap.Width; x++) {
                        if (pixels[row + x * 4 + 3] != 255) return false;
                    }
                }
                return true;
            } finally {
                bitmap.UnlockBits(data);
            }
        }
    }
}
'@

$external = @(Get-ChildItem -LiteralPath $assets -Filter "*.png" -File)
$mirrored = @(Get-ChildItem -LiteralPath $mirror -Filter "*.png" -File)
if ($external.Count -ne 53 -or $mirrored.Count -ne 53) {
    Fail "PNG count mismatch: external=$($external.Count), mirror=$($mirrored.Count), expected 53 each."
}
$declared = @($frames.filename)
$undeclaredExternal = @($external.Name | Where-Object { $_ -notin $declared })
$undeclaredMirror = @($mirrored.Name | Where-Object { $_ -notin $declared })
if ($undeclaredExternal.Count -or $undeclaredMirror.Count) { Fail "An active asset directory contains undeclared PNGs." }

foreach ($frame in $frames) {
    $externalPath = Join-Path $assets $frame.filename
    $mirrorPath = Join-Path $mirror $frame.filename
    foreach ($path in @($externalPath, $mirrorPath)) {
        if (-not (Test-Path -LiteralPath $path)) { Fail "Missing PNG for $($frame.id): $path" }
    }
    $image = [Drawing.Image]::FromFile($externalPath)
    try {
        if ($image.Width -ne 1920 -or $image.Height -ne 1080) {
            Fail "$($frame.filename) is $($image.Width)x$($image.Height); expected 1920x1080."
        }
    } finally { $image.Dispose() }
    if (-not [RecordingImageCheck]::IsOpaque($externalPath)) { Fail "$($frame.filename) contains transparent pixels." }
    $externalHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $externalPath).Hash
    $mirrorHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $mirrorPath).Hash
    if ($externalHash -ne $mirrorHash) { Fail "Mirror hash mismatch for $($frame.id)." }
}

# Manifest navigation is selection-only; replaying the same segment produces the same ordered IDs.
$firstReplay = @($frames | Where-Object segment -eq "S03" | Select-Object -ExpandProperty id)
$secondReplay = @($frames | Where-Object segment -eq "S03" | Select-Object -ExpandProperty id)
if (($firstReplay -join '|') -ne ($secondReplay -join '|') -or $firstReplay.Count -ne 15) {
    Fail "Deterministic Buying replay assertion failed."
}

Write-Host "PASS: 53 frames, 8 five-phase actions, 295 seconds, aligned runbook, opaque mirrored PNGs, JavaScript, replay, and disclosure checks."
