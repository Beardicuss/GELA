param(
    [ValidateRange(5, 300)]
    [int]$Seconds = 10
)

$ErrorActionPreference = "Stop"
$logicalProcessors = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
$processes = @(Get-CimInstance Win32_Process)
$root = $processes |
    Where-Object { $_.Name -eq "Gela.exe" -and $_.CommandLine -like "*--home-window*" } |
    Select-Object -First 1
if (-not $root) {
    throw "Installed Gela Home is not running."
}

$ids = [System.Collections.Generic.List[int]]::new()
$ids.Add([int]$root.ProcessId)
for ($index = 0; $index -lt $ids.Count; $index++) {
    $parentId = $ids[$index]
    foreach ($child in $processes | Where-Object { $_.ParentProcessId -eq $parentId }) {
        if (-not $ids.Contains([int]$child.ProcessId)) {
            $ids.Add([int]$child.ProcessId)
        }
    }
}

$cpuBefore = @{}
foreach ($processId in $ids) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) { $cpuBefore[$processId] = $process.CPU }
}
Start-Sleep -Seconds $Seconds

$rows = foreach ($processId in $ids) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    $cpuDelta = $process.CPU - [double]($cpuBefore[$processId] ?? $process.CPU)
    [pscustomobject]@{
        Process = $process.ProcessName
        PID = $processId
        WorkingMB = [math]::Round($process.WorkingSet64 / 1MB, 1)
        PrivateMB = [math]::Round($process.PrivateMemorySize64 / 1MB, 1)
        CpuPercent = [math]::Round(($cpuDelta / $Seconds / $logicalProcessors) * 100, 2)
    }
}

[pscustomobject]@{
    SampleSeconds = $Seconds
    Processes = $rows.Count
    WorkingMB = [math]::Round(($rows | Measure-Object WorkingMB -Sum).Sum, 1)
    PrivateMB = [math]::Round(($rows | Measure-Object PrivateMB -Sum).Sum, 1)
    CpuPercent = [math]::Round(($rows | Measure-Object CpuPercent -Sum).Sum, 2)
}
$rows | Sort-Object WorkingMB -Descending
