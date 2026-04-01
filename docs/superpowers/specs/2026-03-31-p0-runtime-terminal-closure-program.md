# P0 Runtime Terminal Closure Program

## Goal

把当前“已能跑的自治基线”推进到真正的 P0 终态收口，并且严格按以下顺序施工：

1. `P0-1` 宿主真相统一
2. `P0-2` 单行业长跑闭环
3. `P0-3` 主脑驾驶舱
4. `P0-4` 宽回归与 live smoke
5. `P0-5` 持续删旧

这不是一次性混合补丁集，而是一条必须顺序通过 gate 的程序级施工线。

## Why This Order Is Mandatory

- `P0-1` 不先做完，后续所有消费者都会继续读错宿主真相。
- `P0-2` 不稳定，cockpit 只会展示阶段性成功，不是真闭环。
- `P0-3` 必须建立在真实对象和真实长跑链上，否则只是好看的壳。
- `P0-4` 必须等前三项稳定后再上升为发布门槛。
- `P0-5` 贯穿全程，但最终还要单独关账一次。

## Program Boundaries

### P0-1 宿主真相统一

统一 `host_twin / seat / host contract / workflow / cron / fixed-SOP / runtime` 的 canonical host truth，所有执行入口对 `selected_seat_ref / selected_session_mount_id / host_requirement / legal_recovery` 使用同一口径。

### P0-2 单行业长跑闭环

让单个行业实例在多周期里稳定跑通：

`staffing -> handoff -> human assist -> report -> synthesis -> replan`

并保证 continuity、回流、监督链和执行焦点不会在 rollover 后丢失。

### P0-3 主脑驾驶舱

把 `Runtime Center` 收成真正 cockpit，而不是 detail reader。核心对象：

`carrier / strategy / lanes / backlog / cycle / assignment / report / environment / governance / recovery / automation / evidence / decision / patch`

都必须在一个 runtime surface 中可见、可关联、可追踪。

### P0-4 宽回归与 live smoke

把关键 runtime chain、host continuity、multi-cycle industry、host switch、handoff、resume、evidence replay、multi-agent contention 收成正式发布门槛。

### P0-5 持续删旧

持续删除残余 `goal / task / schedule` 主脑心智、compat façade、legacy alias、旧入口和前台旧文案；每个阶段都必须同步关账，但最终还要做一次全量兼容清零。

## Gates

### Gate A: Canonical Host Truth

只有当 `workflow / cron / fixed-SOP / Runtime Center / industry runtime` 对 canonical host truth 的关键字段使用同一共享逻辑，`P0-1` 才算通过。

### Gate B: Long-Run Industry Closure

只有当单行业实例可以稳定连续跑多个周期，且 `staffing + handoff + human assist + report + synthesis + replan` 不掉链，`P0-2` 才算通过。

### Gate C: Cockpit Closure

只有当 Runtime Center 能直接展示并串联主脑对象、执行对象、证据对象、治理对象，且不再依赖旧 `goal / task / schedule` 主脑心智，`P0-3` 才算通过。

### Gate D: Release-Grade Verification

只有当宽回归与 live smoke 覆盖关键主链并成为发布门槛，`P0-4` 才算通过。

### Gate E: Legacy Zero

只有当剩余 compat/alias/旧入口完成文档、路由、前台、测试和读写心智的统一收口，`P0-5` 才算通过。

## Immediate Execution Decision

本轮立即开工 `P0-1`，并只做对后续四项有净正贡献的工作：

- 把散落在 `workflow / cron / fixed-SOP` 的 canonical host identity 解析逻辑收成共享 helper
- 用测试锁住 canonical `environment_ref / environment_id / session_mount_id / selected_seat_ref / selected_session_mount_id` 合同
- 避免继续在每个 consumer 里复制 `scheduler_inputs / host_twin_summary / coordination / metadata` 的优先级推断

## Out of Scope For The First Implementation Slice

以下内容属于后续阶段，不在第一批实现里直接混做：

- 多周期 single-industry orchestration 逻辑扩面
- Runtime Center cockpit 大改版
- 长时间 live smoke 扩面
- 全量 legacy 清零

## Success Standard

这条程序线的成功，不是“若干测试通过”，而是：

- 运行真相只有一套
- 单行业长跑只有一条主链
- cockpit 只展示真实 runtime truth
- smoke 与 regression 是发布门槛
- legacy 只减不增
