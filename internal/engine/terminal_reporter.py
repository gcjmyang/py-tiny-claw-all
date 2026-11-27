# internal/engine/terminal_reporter.py
# 第 10 章：换个汇报员就换一种用法 —— TerminalReporter 把过程打印到终端。
# 和 FeishuReporter 的区别只在"发到哪"：一个 print，一个调用飞书 API。
from internal.engine.reporter import Reporter

# 终端一行放不下太长的参数（比如 write_file 写一整个文件），最多显示这么多字符
MAX_ARGS_CHARS = 150


class TerminalReporter(Reporter):
    """把引擎的关键事件打印到终端（实现 engine.Reporter 接口）。"""

    def on_thinking(self):
        """引擎进入慢思考阶段 -> 打印"思考中"提示。"""
        print("\n[🤔 思考中] 模型正在推理...")

    def on_tool_call(self, tool_name: str, args: str):
        """引擎即将执行工具 -> 打印工具名和参数。"""
        print(f"[🛠️ 调用工具] {tool_name}")

        # 参数里的换行符转义，保证终端里始终只占一行
        display_args = args.replace("\n", "\\n").replace("\r", "\\r")
        if len(display_args) > MAX_ARGS_CHARS:
            display_args = display_args[:MAX_ARGS_CHARS] + "... (已截断)"

        print(f"    参数: {display_args}")

    def on_tool_result(self, tool_name: str, result: str, is_error: bool):
        """工具执行完毕 -> 失败时打印错误内容；成功时只打印"成功"。"""
        if is_error:
            print(f"[❌ 执行失败] {tool_name}")
            if result != "":
                print(f"    错误: {result}")
        else:
            print(f"[✅ 执行成功] {tool_name}")

    def on_message(self, content: str):
        """模型给出了文字回复 -> 打印出来。"""
        if content == "":
            return
        print(f"\n🤖 Agent 回复:\n{content}\n")


def new_terminal_reporter() -> TerminalReporter:
    return TerminalReporter()
