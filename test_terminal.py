# test_terminal.py
# 第 10 章离线验证脚本：不调用大模型、不消耗 token。
# 运行方式（在 py-tiny-claw-all 目录下）: python test_terminal.py
#
# 验证两件事：
#   1. TerminalReporter 的 4 个方法打印的内容符合要求（换行转义、150 字截断）；
#   2. run_terminal 的对话循环：空输入跳过、exit 退出、引擎出错不中断程序。
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from internal.engine.terminal_reporter import (
    MAX_ARGS_CHARS, TerminalReporter, new_terminal_reporter,
)

PASSED = 0


def check(cond: bool, msg: str):
    global PASSED
    if not cond:
        raise AssertionError(f"❌ 断言失败: {msg}")
    PASSED += 1
    print(f"✅ {msg}")


def capture(func, *args, **kwargs) -> str:
    """把函数里的 print 抓成字符串。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    return buf.getvalue()


def test_terminal_reporter():
    print("\n[测试 1] TerminalReporter 的 4 个方法")
    rep = new_terminal_reporter()
    check(isinstance(rep, TerminalReporter), "new_terminal_reporter 返回 TerminalReporter")

    out = capture(rep.on_thinking)
    check("[🤔 思考中]" in out, "on_thinking 打印思考中提示")

    out = capture(rep.on_tool_call, "read_file", '{"path": "README.md"}')
    check("[🛠️ 调用工具] read_file" in out, "on_tool_call 打印工具名")
    check('参数: {"path": "README.md"}' in out, "on_tool_call 打印参数")

    # 参数里的换行必须转义成 \n，保证终端里只占一行
    out = capture(rep.on_tool_call, "write_file",
                  '{"path": "x.py", "content": "line1\nline2"}')
    check("line1\\nline2" in out, "参数中的换行符被转义成 \\n")
    check(len(out.splitlines()) == 2, "参数确实只占一行（工具名一行 + 参数一行）")

    # 超过 150 字要截断
    out = capture(rep.on_tool_call, "write_file", "A" * 300)
    check("... (已截断)" in out, "参数超过 150 字时追加截断标记")
    check(len([l for l in out.splitlines() if l.startswith("    参数")]) == 1,
          "截断后参数仍只占一行")
    check(("A" * MAX_ARGS_CHARS) in out, "保留前 150 个字")

    out = capture(rep.on_tool_result, "bash", "", False)
    check(out.strip() == "[✅ 执行成功] bash", "成功时只打印一句")

    out = capture(rep.on_tool_result, "read_file", "打开文件失败: no such file", True)
    check("[❌ 执行失败] read_file" in out, "失败时打印失败标题")
    check("错误: 打开文件失败: no such file" in out, "失败时打印错误内容")

    out = capture(rep.on_message, "")
    check(out == "", "content 为空时不打印")

    out = capture(rep.on_message, "README 里写的是：工作区说明。")
    check("🤖 Agent 回复:" in out, "on_message 打印回复标题")
    check("README 里写的是：工作区说明。" in out, "on_message 打印回复内容")


def test_run_terminal():
    print("\n[测试 2] run_terminal 的对话循环")

    class FakeEngine:
        def __init__(self, fail_on: str = ""):
            self.prompts: list[str] = []
            self.fail_on = fail_on

        def run(self, prompt, reporter=None):
            self.prompts.append(prompt)
            if prompt == self.fail_on:
                raise RuntimeError("模拟模型超时")

    # 依次喂：空行、正常问题、会崩溃的问题、再一个正常问题、exit
    inputs = iter(["", "看下 README.md", "这次会崩", "再看一次", "exit"])

    from cmd.claw.main import run_terminal

    def fake_input(prompt=""):
        """模拟 input()：先把提示打出来，再返回预先准备的输入。"""
        print(prompt, end="")
        return next(inputs)

    import builtins
    origin_input = builtins.input
    builtins.input = fake_input
    try:
        eng = FakeEngine(fail_on="这次会崩")
        out = capture(run_terminal, eng)
    finally:
        builtins.input = origin_input

    check("💻 终端模式已启动" in out, "启动时打印提示")
    check("👤 你:" in out, "每轮打印输入提示")
    check(eng.prompts == ["看下 README.md", "这次会崩", "再看一次"],
          "空输入被跳过，问题和 exit 都正确处理")
    check("❌ Agent 运行崩溃: 模拟模型超时" in out, "引擎出错时打印错误但不退出")
    check(out.count("👤 你:") == 5, "崩溃后循环继续，直到输入 exit")


if __name__ == "__main__":
    print("========== 第 10 章 Terminal 终端模式 · 离线验证 ==========")
    test_terminal_reporter()
    test_run_terminal()
    print(f"\n🎉 全部通过：共 {PASSED} 项断言，未调用模型。")
