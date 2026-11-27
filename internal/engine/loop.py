# internal/engine/loop.py
# 对应 Go 版: internal/engine/loop.go
# 第 8 章：并发执行工具调用（Fork-Join）。
# Go 版用 goroutine + WaitGroup，
# Python 版用 ThreadPoolExecutor 实现"并发执行、按序聚合"。
# 本课程改进：Fork 之前先判断，只读并发、涉写串行。
# 第 9 章：引擎不再自己 print，而是在 4 个关键时刻通知 Reporter（汇报员）。
import logging
from concurrent.futures import ThreadPoolExecutor

from internal.engine.reporter import Reporter
from internal.provider.interface import LLMProvider
from internal.schema.message import (
    Message, ROLE_SYSTEM, ROLE_USER, ToolCall,
)
from internal.tools.registry import Registry

log = logging.getLogger(__name__)

# 只读工具白名单：只有名单里的工具允许并发执行。
# write_file / edit_file / bash 都可能修改文件，一律按"写"处理。
READ_ONLY_TOOLS = {"read_file"}

# 汇报给用户前，工具输出最多保留的字符数，避免把飞书 / 终端刷屏。
MAX_RESULT_CHARS = 200


class AgentEngine:
    def __init__(self, provider: LLMProvider, registry: Registry,
                 work_dir: str, enable_thinking: bool):
        self.provider = provider
        self.registry = registry
        self.work_dir = work_dir
        self.enable_thinking = enable_thinking

    def run(self, user_prompt: str, reporter: Reporter | None = None) -> None:
        log.info("[Engine] 引擎启动，锁定工作区: %s", self.work_dir)
        log.info("[Engine] 慢思考模式 (Thinking Phase): %s",
                 self.enable_thinking)

        context_history: list[Message] = [
            Message(
                role=ROLE_SYSTEM,
                content="You are py-tiny-claw-all, an expert coding "
                        "assistant. You have full access to tools "
                        "in the workspace.",
            ),
            Message(role=ROLE_USER, content=user_prompt),
        ]

        turn_count = 0

        while True:
            turn_count += 1
            log.info("\n========== [Turn %d] 开始 ==========",
                     turn_count)

            available_tools = self.registry.get_available_tools()

            # ============ Phase 1: Thinking ============
            if self.enable_thinking:
                # ① 慢思考开始 -> 告诉用户"我在想，别着急"
                if reporter is not None:
                    reporter.on_thinking()

                log.info("[Engine][Phase 1] 剥夺工具访问权，"
                         "强制进入慢思考与规划阶段...")
                try:
                    # 传入 None 剥夺工具
                    think_resp = self.provider.generate(
                        context_history, None)
                except Exception as e:
                    raise RuntimeError(
                        f"Thinking 阶段生成失败: {e}") from e
                if think_resp.content != "":
                    log.info("🧠 [内部思考 Trace]: %s", think_resp.content)
                    context_history.append(think_resp)

            # ============ Phase 2: Action ============
            log.info("[Engine][Phase 2] 恢复工具挂载，"
                     "等待模型采取行动...")
            try:
                action_resp = self.provider.generate(
                    context_history, available_tools)
            except Exception as e:
                raise RuntimeError(f"Action 阶段生成失败: {e}") from e

            context_history.append(action_resp)

            # ② 模型给出了要给用户看的文字 -> 交给汇报员
            if action_resp.content != "" and reporter is not None:
                reporter.on_message(action_resp.content)

            # ============ 执行判断 ============
            tool_calls = action_resp.tool_calls
            if len(tool_calls) == 0:
                log.info("[Engine] 模型未请求调用工具，任务宣告完成。")
                break

            log.info("[Engine] 模型请求调用 %d 个工具...",
                     len(tool_calls))

            # ① 判断本批次能否并发：多于 1 个，且全部是只读工具
            can_parallel = len(tool_calls) > 1 and all(
                call.name in READ_ONLY_TOOLS for call in tool_calls
            )

            # ② 预分配结果列表：第 idx 个工具的结果放进第 idx 格
            #    每个线程只写自己的格子，不需要加锁，顺序也不会乱
            observation_msgs: list[Message | None] = (
                [None] * len(tool_calls)
            )

            def run_tool(idx: int, call: ToolCall):
                log.info("  -> [Worker-%d] 🛠️ 开始执行: %s | 参数: %s",
                         idx, call.name, call.arguments)

                # ③ 工具即将执行 -> 告诉用户"正在干什么"
                if reporter is not None:
                    reporter.on_tool_call(call.name, call.arguments)

                # 执行底层工具
                result = self.registry.execute(call)

                if result.is_error:
                    log.info("  -> [Worker-%d] ❌ 工具执行报错: %s",
                             idx, result.output)
                else:
                    log.info("  -> [Worker-%d] ✅ 工具执行成功"
                             " (返回 %d 字节)",
                             idx, len(result.output))

                # ④ 工具执行完毕 -> 汇报结果（成功只报一句，失败报错误内容）
                if reporter is not None:
                    display_output = result.output
                    if len(display_output) > MAX_RESULT_CHARS:
                        display_output = (
                            display_output[:MAX_RESULT_CHARS]
                            + "... (已截断)"
                        )
                    reporter.on_tool_result(call.name, display_output,
                                            result.is_error)

                # 写入自己专属的格子
                observation_msgs[idx] = Message(
                    role=ROLE_USER,
                    content=result.output,
                    tool_call_id=call.id,
                )

            # ③ 只读批次 -> Fork-Join 并发；涉写批次 -> 按顺序串行
            if can_parallel:
                log.info("[Engine] ⚡ 本批次全部为只读工具，"
                         "启动并发执行 (Fork)...")
                with ThreadPoolExecutor(
                        max_workers=len(tool_calls)) as executor:
                    # Fork：把每个工具调用分派给一个线程
                    futures = [
                        executor.submit(run_tool, i, call)
                        for i, call in enumerate(tool_calls)
                    ]
                    # Join：逐个等待，并让线程内的异常向上传播
                    for f in futures:
                        f.result()
                log.info("[Engine] 所有并发工具执行完毕 (Join)，"
                         "开始聚合观察结果...")
            else:
                log.info("[Engine] 🔒 本批次包含写操作或只有 1 个"
                         "工具，按顺序串行执行...")
                for i, call in enumerate(tool_calls):
                    run_tool(i, call)

            # ④ 按模型给出的原始顺序，把结果追加回上下文
            for obs in observation_msgs:
                context_history.append(obs)
