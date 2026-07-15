param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ReportPaths
)

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$script = Join-Path $root 'audit\scripts\rebuild_audit_state.py'

if (-not (Test-Path -LiteralPath $script)) {
    throw "Missing rebuild script: $script"
}

python $script @ReportPaths
