@echo off
rem 每日影子盘收盘段(GHQ-Shadow-PostClose 调用): refresh→一致性比对→纸面净值→台账
rem 输出落 logs\shadow_postclose.log(2026-07-15 复盘: 任务失败无日志无法定位失败步骤)
cd /d C:\Codes\GoldenHandQuant
if not exist logs mkdir logs
echo [%date% %time%] ===== post-close start ===== >> logs\shadow_postclose.log
C:\Users\11492\.conda\envs\goldenhandquant\python.exe -u scripts\shadow_tuesday.py --force --post-close >> logs\shadow_postclose.log 2>&1
set EC=%ERRORLEVEL%
echo [%date% %time%] ===== post-close exit %EC% ===== >> logs\shadow_postclose.log
exit /b %EC%
