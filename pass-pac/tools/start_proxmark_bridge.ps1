$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BridgeScript = Join-Path $PSScriptRoot "proxmark_bridge.py"
$ClientPath = Join-Path $PSScriptRoot "proxspace_client.cmd"
$DevicePort = "COM8"
$BridgePort = 8765

python $BridgeScript `
  --host 127.0.0.1 `
  --port $BridgePort `
  --client $ClientPath `
  --device-port $DevicePort `
  --timeout 20
