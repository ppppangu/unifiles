param(
  [string]$Root = ".",
  [switch]$IncludeMarkdown
)

$ErrorActionPreference = 'Stop'

# Prepare backup folder
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupRoot = Join-Path $Root ("backup_schema_rename_" + $timestamp)

# File patterns to process
$exts = @('*.sql','*.psql','*.sql.j2','*.jinja2','*.j2','*.tpl')
if ($IncludeMarkdown) {
    $exts += @('*.md','*.markdown')
}

# Resolve absolute root path for reliable relative path calculations
$rootFull = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')

# Find files
$files = Get-ChildItem -Path $Root -Recurse -File -Include $exts

$changed = @()
foreach ($f in $files) {
    $text = Get-Content -Raw -LiteralPath $f.FullName

    # Replace schema name only when it is a standalone identifier (word boundaries)
    # This also updates quoted usages and dynamic SQL strings
    $new = [regex]::Replace($text, '(?i)\bunifiles\b', 'unifiles')

    if ($new -ne $text) {
        # Build backup target path keeping relative structure
        $full = (Resolve-Path -LiteralPath $f.FullName).Path
        $rel = $full.Substring($rootFull.Length).TrimStart('\\','/')
        $targetBackupFile = Join-Path $backupRoot $rel
        $targetDir = Split-Path $targetBackupFile -Parent
        if (-not (Test-Path -LiteralPath $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        }
        # Write backup and updated file
        Set-Content -LiteralPath $targetBackupFile -Value $text -Encoding UTF8
        Set-Content -LiteralPath $f.FullName -Value $new -Encoding UTF8
        $changed += $f.FullName
    }
}

Write-Output ("Changed files: " + $changed.Count)
$changed | ForEach-Object { Write-Output $_ }

