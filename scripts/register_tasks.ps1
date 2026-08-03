# CodeOracle - Windows Task Scheduler registration
#
# Idempotent: safe to re-run. Removes any existing task with the same name
# before re-registering. Requires an elevated PowerShell (Run as Admin) only
# if RunLevel=Highest is left uncommented.
#
# Registered tasks (v1):
#   CodeOracle_ScanSolana      - every 5 min -> scripts/run_scan_solana.py
#   CodeOracle_ResolverSolana  - every 5 min -> scripts/run_resolver.py
#
# Future tasks (E4, E9, digest, expirer, etc.) are stubbed at the bottom
# commented out; uncomment when their runners exist.

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\CodeOracle"
$Venv        = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir      = Join-Path $ProjectRoot "logs"

if (-not (Test-Path $Venv)) {
    Write-Warning "Python venv not found at $Venv - falling back to system python. Recommended: python -m venv .venv"
    $Venv = "python"
}
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Register-CodeOracleTask {
    param(
        [string]$Name,
        [string]$Script,
        [int]$IntervalMinutes,
        [string]$LogFile
    )

    # PowerShell wrapper: redirect stdout+stderr to a rolling log file
    $psCmd = "& '$Venv' '$Script' *>> '$LogFile'"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($psCmd))
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand $encoded" `
        -WorkingDirectory $ProjectRoot

    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
    # Task Scheduler's -RepetitionDuration was deprecated; the above repeats indefinitely on modern Windows.

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

    $principal = New-ScheduledTaskPrincipal -UserId $env:UserName -LogonType Interactive

    # Idempotent: unregister first if exists
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    }

    Register-ScheduledTask -TaskName $Name `
        -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
        -Description "CodeOracle: $Script (every $IntervalMinutes min)" | Out-Null

    Write-Host "registered $Name  ->  $Script (every $IntervalMinutes min)"
}

# --- v1 tasks -------------------------------------------------------------

Register-CodeOracleTask `
    -Name "CodeOracle_ScanSolana" `
    -Script (Join-Path $ProjectRoot "scripts\run_scan_solana.py") `
    -IntervalMinutes 5 `
    -LogFile (Join-Path $LogDir "scan_solana.log")

Register-CodeOracleTask `
    -Name "CodeOracle_ResolverSolana" `
    -Script (Join-Path $ProjectRoot "scripts\run_resolver.py") `
    -IntervalMinutes 5 `
    -LogFile (Join-Path $LogDir "resolver_solana.log")

# --- future tasks (stub, uncomment when runner lands) ---------------------
# Register-CodeOracleTask -Name "CodeOracle_Digest"      -Script "scripts\run_digest.py"       -IntervalMinutes 1440 -LogFile "$LogDir\digest.log"
# Register-CodeOracleTask -Name "CodeOracle_ScanBSC"     -Script "scripts\run_scan_bsc.py"     -IntervalMinutes 15   -LogFile "$LogDir\scan_bsc.log"
# Register-CodeOracleTask -Name "CodeOracle_ScanETH"     -Script "scripts\run_scan_eth.py"     -IntervalMinutes 15   -LogFile "$LogDir\scan_eth.log"
# Register-CodeOracleTask -Name "CodeOracle_ScanBase"    -Script "scripts\run_scan_base.py"    -IntervalMinutes 15   -LogFile "$LogDir\scan_base.log"
# Register-CodeOracleTask -Name "CodeOracle_ScanStocks"  -Script "scripts\run_scan_stocks.py"  -IntervalMinutes 5    -LogFile "$LogDir\scan_stocks.log"

Write-Host ""
Write-Host "done. verify with:  Get-ScheduledTask -TaskName 'CodeOracle_*' | Format-Table TaskName, State"
