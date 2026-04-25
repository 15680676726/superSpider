# WorkContext Implementation Plan

鏈枃妗ｅ畾涔夊熀浜庡綋鍓?`CoPaw` 浠ｇ爜鐜板疄鐨?`WorkContext` 钀藉湴鏂规銆?
瀹冧笉鏄柊璁板繂绯荤粺锛屼篃涓嶆槸鏂拌繍琛屼富閾撅紝鑰屾槸鎶娾€滄寔缁伐浣滃崟鍏冣€濇寮忔敹鏁涗负缁熶竴 `state` 瀵硅薄銆?
---

## 1. 涓€鍙ヨ瘽缁撹

`WorkContext` 应落成：

> 统一 `state` 中的连续工作容器，用来把 `task / mailbox / checkpoint / task-thread / report / recall` 鏀舵暃鍒板悓涓€涓伐浣滆竟鐣屻€?
而不是：

> 缁欐瘡涓?agent 鍐嶉€犱竴濂楃鏈夐暱鏈熻蹇嗭紝鎴栨妸 sidecar / prompt transcript 鍙樻垚绗簩鐪熺浉婧愩€?
---

## 2. 涓轰粈涔堢幇鍦ㄥ繀椤昏ˉ瀹?
鐜版湁浠ｇ爜宸茬粡鏈変袱鏉℃纭熀纭€锛?
1. 闀挎湡璁板繂宸茬粡涓嶆槸涓€涓叏灞€姹狅紝鑰屾槸 `task / agent / industry / global` 分层 recall銆?2. worker 运行时已经有 mailbox / checkpoint / actor lease 杩欎簺鈥滅鏈夊伐浣滄€佲€濄€?
浣嗚繕缂轰竴涓寮忓璞℃潵琛ㄨ揪锛?
- 杩欐杩炵画宸ヤ綔鍒板簳鏄湪鏈嶅姟鍝釜鈥滃伐浣滃崟鍏冣€?- 多个 agent 鍦ㄥ悓涓€宸ヤ綔鍗曞厓鍐呬粈涔堝彲浠ュ叡浜紝浠€涔堜笉鑳藉叡浜?- 鍚屼竴涓?agent 骞惰澶勭悊澶氫釜宸ヤ綔鍗曞厓鏃讹紝濡備綍閬垮厤涓婁笅鏂囦覆绾?
---

## 3. 正式边界

### 3.1 分层定义

- `StrategyMemory`
  - 鍙睘浜庝富鑴戦暱鏈熸垬鐣ワ紝涓嶅睘浜庢墽琛屼綅銆?- `SharedFactMemory`
  - 鐢?`KnowledgeChunkRecord / derived memory index` 鎵胯浇鐨勯暱鏈熶簨瀹炪€?- `WorkContext`
  - 杩炵画宸ヤ綔瀹瑰櫒锛岃〃杈锯€滆繖浠朵簨鈥濇湰韬€?- `Task`
  - `WorkContext` 鍐呮煇涓€娆″彲璋冨害銆佸彲鎵ц鐨勫伐浣滃崟鍏冦€?- `Thread / Session`
  - 浜や簰琛ㄩ潰锛屼笉鏄伐浣滅湡鐩搞€?- `AgentWorkingState`
  - mailbox / checkpoint / runtime锛屼粎鏄墽琛屾湡绉佹湁宸ヤ綔鎬侊紝涓嶆槸鍏变韩鐪熺浉銆?
### 3.2 隔离规则

- 鍚屼竴涓?`WorkContext`
  - 可以共享 facts / evidence / reports / compiled summary
  - 涓嶅叡浜鏈?checkpoint / mailbox / transient chain-of-thought
- 不同 `WorkContext`
  - 默认隔离 recall 鍜屽伐浣滄€?- `StrategyMemory`
  - 不下放给职业 agent 作为独立长期使命

---

## 4. 瀵圭幇鏈変唬鐮佺殑鏈€灏忔纭敼閫?
### 4.1 新增正式对象

- `WorkContextRecord`
  - 单一真相源：`src/copaw/state/`
  - 表达连续工作单元

### 4.2 鏍稿績杩愯璁板綍琛?`work_context_id`

- `TaskRecord`
- `AgentMailboxRecord`
- `AgentCheckpointRecord`
- `AgentThreadBindingRecord`
- `AgentReportRecord`
- `KernelTask`

璇存槑锛?
- 对于这些已有正式对象，`work_context_id` 鐩存帴鎸傚湪瀵硅薄鏈韩鍗冲彲锛屼笉鍐嶉澶栧埗閫犲钩琛屽叧绯绘簮銆?- `EvidenceRecord` 仍保留在 `evidence` 层，当前阶段通过 `metadata["work_context_id"]` 鎺ョ嚎锛屼笉棰濆寮€绗簩濂?evidence store銆?
### 4.3 褰撳墠闃舵鐨勯粯璁ゅ缓妯＄瓥鐣?
`WorkContext` 鐨勯€氱敤鍚堝悓鏄€滄樉寮忎紶鍏ユ垨浠庣埗閾剧户鎵库€濓紝涓嶆槸鈥滀负瀹㈡湇銆侀攢鍞€佺爺绌跺悇鍐欎竴濂椾唬鐮佲€濄€?
当前第一批默认锚点：

1. `task-chat` / `task-session:*`
   - 涓€涓ǔ瀹?task-thread 瀵瑰簲涓€涓ǔ瀹?`WorkContext`
2. parent task delegation
   - child task 继承 parent 鐨?`work_context_id`
3. 显式外部传入
   - 后续任意 front-door 鍙鑳芥彁渚涚ǔ瀹?`work_context_id` 鎴?`context_key`锛岄兘鍙鐢ㄥ悓涓€濂椾富閾?
---

## 5. 鐪熺浉婧愯竟鐣?
### 5.1 不是新的 memory store

`WorkContext` 涓嶄繚瀛樺彟涓€浠介暱鏈熻蹇嗘鏂囥€?
瀹冨彧璐熻矗锛?
- 定义连续工作边界
- 鎶?recall selector 收敛到正确的 scope
- 璁?task/mailbox/report/evidence 閮借兘褰掑睘鍒扳€滃悓涓€浠朵簨鈥?
### 5.2 不是新的 runtime chain

执行仍然走现有：

- `KernelDispatcher`
- `TaskRecord / TaskRuntimeRecord`
- `ActorMailboxService`
- `EvidenceLedger`

`WorkContext` 鍙槸鎸傚湪杩欐潯涓婚摼涓婄殑姝ｅ紡瀵硅薄銆?
---

## 6. Recall 规则

新增 `work_context` scope 后，正式 recall 顺序为：

1. current `task`
2. current `work_context`
3. current `agent`
4. current `industry`
5. current `global`
6. needed `strategy summary`

这样做的含义是：

- 鍚屼竴浠诲姟鐨勫嵆鏃朵笂涓嬫枃浼樺厛绾ф渶楂?- 同一工作单元内跨 turn / 璺?child-task 鐨勮繛缁簨瀹炵浜屼紭鍏?- agent 鑷韩缁忛獙鍙綔涓烘洿浣庝紭鍏堢骇鑳屾櫙锛屼笉鍐嶅帇杩囧綋鍓嶅伐浣滃崟鍏?
---

## 7. 鐜版湁澶?agent 场景下的作用

### 7.1 不给每个 worker 造独立长期脑

职业 agent 浠嶇劧鍙湁锛?
- 私有 working state
- 可回写的 agent experience

涓嶉渶瑕佸啀缁欐瘡涓?worker 寤轰竴濂楀钩琛岄暱鏈熺湡鐩告簮銆?
### 7.2 同一工作单元内可协作

渚嬪锛?
- 涓€涓鍗曞敭鍚?- 涓€涓嚎绱㈣浆鍖?- 涓€涓爺绌朵笓棰?- 涓€涓簨鏁呮帓鏌?
多个 agent 閮藉彲浠ユ寕鍒板悓涓€涓?`WorkContext`，共享：

- 相关 evidence
- task terminal reports
- compiled memory summary

但不会共享彼此的 mailbox / checkpoint銆?
### 7.3 不同工作单元默认隔离

鍚屼竴涓鏈?agent 鍚屾椂鎺?10 涓敤鎴锋椂锛?
- 应是 10 涓?`WorkContext`
- 鑰屼笉鏄?1 涓?agent 私有长记忆把 10 涓細璇濇弶鍦ㄤ竴璧?
---

## 8. 当前实现范围

鏈疆蹇呴』涓€娆℃€цˉ榻愶細

1. 姝ｅ紡瀵硅薄涓?schema
2. repository / service
3. task / mailbox / checkpoint / report / evidence / recall 接线
4. Runtime Center 读面
5. 鑷姩鍖栨祴璇?
鏈疆涓嶅仛锛?
- 绗簩濂?memory backend
- 绗簩濂?evidence ledger
- 缁欐瘡绉嶄笟鍔″満鏅崟鐙啓涓€鏉′笓鐢ㄩ摼璺?
---

## 9. 鍒犻櫎涓庡吋瀹硅竟鐣?
鏈柟妗堜笉寮曞叆闀挎湡鍙屽啓鍏煎灞傘€?
当前仓库尚未上线，因此不再为“旧数据缺失 `work_context_id`鈥濅繚鐣欓暱鏈熷吋瀹瑰垎鏀€?
褰撳墠绛栫暐鏀逛负锛?
- 新链路必须显式写入或继承 `work_context_id`
- Runtime Center / recall / conversation facade 优先消费正式 `WorkContext` 合同
- 线程 alias 涓?metadata sniffing 鍙兘淇濈暀涓轰氦浜掕矾鐢辫涔夛紝涓嶅啀浣滀负鍘嗗彶鏁版嵁鍏煎涓绘柟妗?
鍒犻櫎鏉′欢锛?
- 褰撳墠鎵€鏈夋寮?front-door 閮借兘绋冲畾鎻愪緵鎴栫户鎵?`work_context_id`
- 主要 worker 鍗忎綔璺緞涓嶅啀渚濊禆鈥滃彧鐪?agent 线程”推断上下文
### 9.1 Hardening Note

- `2026-03-20` 起，WorkContext 正式要求“显式合同或父链继承”，不再接受 thread/session 鐚滄祴寮忚ˉ绾裤€?
- execution-core control thread 必须通过 thread binding 鎸傛寮?`work_context_id`，conversation facade 涓嶅啀浠?`control_thread_id` 推回 `context_key`銆?
- task persistence 不再根据 `control_thread_id` 鎴?`task-session:*` 鑷姩閫?`context_key`锛涘鏋?front-door 娌＄粰鍚堝悓锛屽氨搴旀毚闇茬己鍙ｈ€屼笉鏄潤榛樺厹搴曘€?
- 前端 `/chat` 涓?task-thread 打开路径只能复用后端已给出的 `work_context_id / context_key / work_context`锛屼笉鑳藉啀鍦?happy path 上做 thread alias 鎺ㄦ柇銆?
