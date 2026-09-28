# outbox-recorder 的验证工装

这个目录**不属于交付物**。要装到内网机的只有隔壁 `../outbox-recorder/`（8 个文件）。
这里是本机用来证明它能跑的四套工装，以及原始输出留档。

技能真身保持 8 个文件不变，是设计阶段定下来的（YAGNI）；工装放在同级目录，
既能让证据从仓库里复现，又不会跟着技能一起被摆渡进内网。

## 怎么重跑

```
# 1. DSH 契约：用 DSH Desktop 内置的真实加载器解析 SKILL.md
#    需要本机装着 DSH Desktop（路径写死在脚本第 14 行的 NM 常量）
node "DSH improve/tests/check_dsh_contract.cjs"

# 2. 脚本机制：临时拷贝一份技能树，跑完整生命周期（init/new/commit/list/
#    audit/answer/sync-inbox/bundle），含正例与三个负例。不落任何测试记录到交付物
python "DSH improve/tests/e2e_outbox.py"            # 加 --keep 可保留临时树

# 3. 27B 可执行性：搭一个最小 agent loop 打 ModelScope 上的 Qwen/Qwen3.8-27B，
#    工具名用小写、write 无 append、正文包在 <skill_instructions> 里，全部照 DSH 的形状
python "DSH improve/tests/agent_loop_27b.py"

# 4. 技能自带的内置用例（这套是交付物的一部分，内网装完也要跑）
python "DSH improve/outbox-recorder/scripts/outbox.py" selftest
```

三套工装都在临时目录里跑，跑完自动删（`agent_loop_27b.py` 会留下 sandbox 与 transcript 路径，按需手删）。

## 留档

| 文件 | 是什么 |
|---|---|
| `evidence-27b-run3.log` | 27B agent loop 第三次跑的完整输出，13/13 全绿、零拒绝、零 denied |
| `evidence-modelscope-round1.log` | 上游探测第一轮：可达性、`max_tokens` 递增、`reasoning_effort` 枚举、thinking 参数。这一轮把 HTTP 200 当成了成功，后来发现 200 也可能带 `choices:null`，故有第二轮 |
| `evidence-modelscope-round2.log` | 第二轮：改用「`choices` 非空 + `finish_reason`」判定。定出 `max_tokens` 上限 131072（262144 返回 200 但 `choices:null`），并证明 `reasoning_effort` 的 `max`/`xhigh`/`high` 上游全收 |
| `evidence-modelscope-round3.log` | 第三轮：一次约 29 万 token 的超长输入被接受（`prompt_tokens: 290054`），据此把 `contextWindow` 定到模型卡的可扩上限 |

## 不在这里的东西

改 `~/.qoder-cn/settings.json` 的补丁脚本与上游探测脚本留在 `MySkills/.probe/`
（`patch_27b_limits.py`、`probe_27b*.py`、`dump_provider.py`）。它们动的是本机 Qoder
的模型配置、会读到凭据文件，与这个技能无关，所以不跟着进仓库。

`.probe/` 是本机既有的临时工装目录，此前就没有纳入版本控制，这次沿用。
