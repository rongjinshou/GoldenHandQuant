<#
影子盘每日任务计划注册(设计 0711-shadow-control SC-5; 2026-07-14 起日频)。

Windows PowerShell(管理员)执行一次:
  powershell -ExecutionPolicy Bypass -File scripts\windows\register_shadow_tasks.ps1
卸载:
  powershell -ExecutionPolicy Bypass -File scripts\windows\register_shadow_tasks.ps1 -Unregister
验证:
  Get-ScheduledTask -TaskName "GHQ-*"

2026-07-15 复盘修订:
  - 动作统一走 scripts\windows\*.bat(输出落 logs\, 否则任务失败无日志无法定位)
  - 触发器日频工作日(Mon-Fri), 与 2026-07-14 日频采样指令对齐(旧版误为周频周二)
  - PostClose/Account-EOD 加 StartWhenAvailable(错过→开机补跑; 收盘后任何时间补跑语义都对)
  - Morning 不加 StartWhenAvailable: 盘后补采样口径漂移, 宁可如实 MISSED
  - 三任务均允许电池供电启动(笔记本拔电源时 15:10 静默跳过即 07-15 事故一环)

注意: 任务在当前用户会话运行, 须已登录 Windows; QMT 仍须人工打开——
编排器负责"提醒+等待+超时告警", 不做自动登录(设计裁定, 乙案否决)。
#>
param(
    [string]$RepoDir = "C:\Codes\GoldenHandQuant",
    [switch]$Unregister
)
$ErrorActionPreference = "Stop"

$tasks = @(
    @{ Name = "GHQ-Shadow-Morning";   Bat = "shadow_morning.bat";   At = "09:20"; CatchUp = $false
       Desc = "GoldenHandQuant 影子盘每日上午采样(dry-run)" }
    @{ Name = "GHQ-Shadow-PostClose"; Bat = "shadow_postclose.bat"; At = "15:10"; CatchUp = $true
       Desc = "GoldenHandQuant 影子盘每日收盘比对+净值" }
    @{ Name = "GHQ-Account-EOD";      Bat = "account_eod.bat";      At = "15:05"; CatchUp = $true
       Desc = "GoldenHandQuant 每日收盘真实账户快照(只读)" }
)

if ($Unregister) {
    foreach ($t in $tasks) {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue
    }
    Write-Host "已卸载: $(($tasks | ForEach-Object Name) -join ', ')"
    exit 0
}

foreach ($t in $tasks) {
    $settingsArgs = @{
        AllowStartIfOnBatteries    = $true
        DontStopIfGoingOnBatteries = $true
        ExecutionTimeLimit         = (New-TimeSpan -Hours 6)
    }
    if ($t.CatchUp) { $settingsArgs.StartWhenAvailable = $true }
    $settings = New-ScheduledTaskSettingsSet @settingsArgs

    $action  = New-ScheduledTaskAction -Execute "$RepoDir\scripts\windows\$($t.Bat)" -WorkingDirectory $RepoDir
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $t.At
    Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger `
        -Settings $settings -Description $t.Desc -Force | Out-Null
    Write-Host "已注册: $($t.Name) (工作日 $($t.At), 补跑=$($t.CatchUp))"
}
