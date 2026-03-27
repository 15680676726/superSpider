$files = @(
  'pages\RuntimeCenter\index.module.less',
  'pages\Chat\index.module.less',
  'pages\CapabilityMarket\index.module.less',
  'pages\AgentWorkbench\index.module.less',
  'pages\Settings\System\index.module.less',
  'pages\Settings\Channels\index.module.less',
  'pages\Agent\Skills\index.module.less',
  'pages\Agent\MCP\index.module.less',
  'components\RuntimeExecutionLauncher.module.less'
)

$base = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($f in $files) {
  $path = Join-Path $base $f
  if (-not (Test-Path $path)) { Write-Host "SKIP: $f"; continue }
  $content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)

  # rgba(99, 102, 241, X) -> rgba(27, 79, 216, X)
  $content = $content -replace 'rgba\(99, 102, 241, ([0-9.]+)\)', 'rgba(27, 79, 216, $1)'
  # rgba(168, 85, 247, X) -> rgba(201, 168, 76, X)
  $content = $content -replace 'rgba\(168, 85, 247, ([0-9.]+)\)', 'rgba(201, 168, 76, $1)'
  # #6366f1 -> #1B4FD8
  $content = $content -replace '#6366f1', '#1B4FD8'
  # #818cf8 -> #C9A84C
  $content = $content -replace '#818cf8', '#C9A84C'
  # #8b5cf6 -> #2563EB
  $content = $content -replace '#8b5cf6', '#2563EB'
  # rgba(15, 23, 42, X) -> rgba(5, 12, 35, X)
  $content = $content -replace 'rgba\(15, 23, 42, ([0-9.]+)\)', 'rgba(5, 12, 35, $1)'
  # rgba(30, 41, 59, X) -> rgba(10, 22, 60, X)
  $content = $content -replace 'rgba\(30, 41, 59, ([0-9.]+)\)', 'rgba(10, 22, 60, $1)'

  [System.IO.File]::WriteAllText($path, $content, [System.Text.Encoding]::UTF8)
  Write-Host "DONE: $f"
}
