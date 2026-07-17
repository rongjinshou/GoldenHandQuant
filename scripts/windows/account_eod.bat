@echo off
rem 每日收盘后真实账户快照(GHQ-Account-EOD 任务调用; QMT 未开则失败跳过, 无害)
rem 输出落 logs\account_eod.log(2026-07-15 复盘: 任务失败无日志无法定位失败步骤)
cd /d C:\Codes\GoldenHandQuant
if not exist logs mkdir logs
echo [%date% %time%] ===== account-eod start ===== >> logs\account_eod.log
C:\Users\11492\.conda\envs\goldenhandquant\python.exe -u scripts\sync_live_account.py >> logs\account_eod.log 2>&1
set EC=%ERRORLEVEL%
echo [%date% %time%] ===== account-eod exit %EC% ===== >> logs\account_eod.log
exit /b %EC%
