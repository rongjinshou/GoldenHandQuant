@echo off
rem 每日影子盘上午段(GHQ-Shadow-Morning 调用): QMT 看护→refresh→市值同步→dry_run 采样
rem --force: 每日采样模式(2026-07-14 用户指令: 日频跑半个月, 防御信号日频才抓得全)
rem 输出落 logs\shadow_morning.log(2026-07-15 复盘: 任务失败无日志无法定位失败步骤)
cd /d C:\Codes\GoldenHandQuant
if not exist logs mkdir logs
echo [%date% %time%] ===== morning start ===== >> logs\shadow_morning.log
C:\Users\11492\.conda\envs\goldenhandquant\python.exe -u scripts\shadow_tuesday.py --force >> logs\shadow_morning.log 2>&1
set EC=%ERRORLEVEL%
echo [%date% %time%] ===== morning exit %EC% ===== >> logs\shadow_morning.log
exit /b %EC%
