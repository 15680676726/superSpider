@echo off
chcp 65001 >nul
title Codex Main Agent Audit
cd /d D:\word\copaw
echo Running Codex main-agent audit in D:\word\copaw
echo.
codex exec "Inspect ONLY the main-agent / main-brain path in D:\word\copaw. Focus on whether the main agent truly acts as planner, delegator, integrator, and final decision-maker. Prioritize these files and closely related ones only: src/copaw/kernel/main_brain_chat_service.py, src/copaw/kernel/turn_executor.py, src/copaw/kernel/query_execution_runtime.py, src/copaw/kernel/query_execution_prompt.py, src/copaw/kernel/query_execution_tools.py, plus any directly imported helper that is essential. Please answer: 1) Does the main agent really understand and decompose tasks before delegation? 2) Does it have a persistent planning state? 3) Does it gather subagent/tool outputs and synthesize them before answering? 4) Where exactly does it fail to behave like a true master agent? 5) What are the top 3 code hotspots to change first? Return a concise diagnostic report with file/function references. Do not modify code."
echo.
echo Codex finished. Press any key to close.
pause >nul
