# BD_TASK_PLAN.md

## 1. 目标
以任务规划为主，明确当前重构缺口的完成状态、所属阶段与下一步动作。

## 2. 当前完成状态（基于代码）
| 编号 | 项目 | 所属阶段 | 状态 | 代码证据 | 说明/下一步 |
| --- | --- | --- | --- | --- | --- |
| P1-1 | `jobs/chats` delete-gate 进入可删除状态 | Phase 1 Next-1/2 | **已完成** | `src/copaw/app/runner/repo/state_repo.py`、`src/copaw/app/crons/repo/state_repo.py`、`src/copaw/app/legacy/write_policy.py` | 主链读写已切到 state repo，delete-gate 审计/清理入口已移除，遗留文件需人工清理 |
| P2-1 | Capability 执行化 + 风险裁决 + 证据契约（含 skill/MCP/system） | Phase 2 | **已完成** | `src/copaw/capabilities/service.py`、`src/copaw/capabilities/sources/system.py`、`src/copaw/app/mcp/manager.py`、`src/copaw/app/_app.py` | Capability 统一走 Kernel 风险门；skill/MCP/system 有可执行入口与证据记录 |
| P3-1 | EnvironmentMount/Session 挂载 | Phase 3 | **已完成** | `src/copaw/environments/registry.py`、`src/copaw/environments/repository.py`、`src/copaw/environments/service.py` | 环境持久化、注册与回收逻辑已落地，执行期 lease 生命周期已有自动化覆盖 |
| P4-1 | SRK 内核成为唯一主链 | Phase 4 | **已完成** | `src/copaw/app/runner/runner.py`、`src/copaw/kernel/tool_bridge.py` | Phase1 bridge 已退出主链，读写均进 kernel/state |
| P4-2 | Compiler 接入 SRK 执行闭环 | Phase 4 | **已完成** | `src/copaw/compiler/compiler.py`、`src/copaw/goals/service.py`、`src/copaw/kernel/persistence.py` | Goal→Compiler→Kernel 投递打通 |
| P6-1 | Learning 闭环（proposal→patch→apply） | Phase 6/7 | **已完成（最小闭环）** | `src/copaw/learning/service.py`、`src/copaw/learning/engine.py`、`src/copaw/app/routers/learning.py` | 具备提案/审批/应用/成长记录闭环 |
| P7-1 | Learning 策略化自动化（自动发现→proposal→patch→自动 apply/rollback） | Phase 5/7 | **已完成（基础策略）** | `src/copaw/learning/service.py`、`src/copaw/app/routers/learning.py`、`src/copaw/capabilities/sources/system.py`、`src/copaw/capabilities/service.py` | 基于证据失败统计生成 proposal/patch，自动 apply/rollback 并写入 DecisionRequest |

## 3. 建议优先级
1) Phase 4/5：继续收缩 runner 宿主职责，补齐 operator/manual E2E 验收  
2) Phase 5/6：扩大真实 provider/environment 覆盖，并补环境宿主恢复/跨进程 lease

## 4. 下一步可交付清单（最小闭环）
- legacy JSON 残留清理与验证报告
- 策略参数调优（阈值/回滚策略）与前端面板接入
- 将策略化执行结果同步到成长轨迹与日报/周报
