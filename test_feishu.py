# test_feishu.py
# 第 9 章离线验证脚本：不调用大模型、不连接飞书、不消耗 token。
# 运行方式（在 py-tiny-claw-all 目录下）: python test_feishu.py
#
# 验证三件事：
#   1. 引擎在 4 个关键时刻确实调用了 Reporter 的 4 个方法，顺序正确；
#   2. 工具输出超过 200 字时只汇报前 200 字；
#   3. FeishuBot 能取出文字、去掉 @ 标记、记下 chat_id；FeishuReporter 的话术正确。
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from internal.engine.loop import AgentEngine
from internal.engine.reporter import Reporter
from internal.feishu.bot import FeishuBot, FeishuReporter
from internal.provider.interface import LLMProvider
from internal.schema.message import Message, ROLE_ASSISTANT, ToolCall
from internal.tools.read_file import ReadFileTool
from internal.tools.registry import new_registry

PASSED = 0


def check(cond: bool, msg: str):
    global PASSED
    if not cond:
        raise AssertionError(f"❌ 断言失败: {msg}")
    PASSED += 1
    print(f"✅ {msg}")


# ============================================================
# 假的依赖：模型、飞书客户端、事件对象
# ============================================================
class FakeProvider(LLMProvider):
    """按脚本依次返回预设响应，完全不联网。"""

    def __init__(self, responses: list[Message]):
        self.responses = responses
        self.calls = 0

    def generate(self, messages, available_tools) -> Message:
        resp = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return resp


class RecordingReporter(Reporter):
    """把收到的通知记成一个列表，方便断言。"""

    def __init__(self):
        self.events: list[tuple] = []

    def on_thinking(self):
        self.events.append(("thinking",))

    def on_tool_call(self, tool_name, args):
        self.events.append(("tool_call", tool_name, args))

    def on_tool_result(self, tool_name, result, is_error):
        self.events.append(("tool_result", tool_name, result, is_error))

    def on_message(self, content):
        self.events.append(("message", content))


class FakeFeishuClient:
    """假的飞书客户端：只记录发出去的消息，不联网。"""

    def __init__(self):
        self.sent: list[dict] = []
        self.im = SimpleNamespace(
            v1=SimpleNamespace(
                message=SimpleNamespace(create=self._create)
            )
        )

    def _create(self, req):
        body = req.request_body
        self.sent.append({
            "chat_id": body.receive_id,
            "msg_type": body.msg_type,
            "content": json.loads(body.content),
        })
        return SimpleNamespace(success=lambda: True, code=0, msg="ok")


def make_engine(tmp_dir: str, responses: list[Message], thinking=False):
    registry = new_registry()
    registry.register(ReadFileTool(tmp_dir))
    return AgentEngine(FakeProvider(responses), registry, tmp_dir, thinking)


# ============================================================
# 测试 1：引擎的 4 个关键时刻
# ============================================================
def test_engine_reporter():
    print("\n[测试 1] 引擎在关键时刻通知汇报员（慢思考 + 工具调用 + 回答）")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "README.md").write_text("这是 README 的内容。\n",
                                             encoding="utf-8")
        responses = [
            # Turn 1 的 Phase 1：慢思考（此时没有工具）
            Message(role=ROLE_ASSISTANT, content="我打算先读 README.md。"),
            # Turn 1 的 Phase 2：决定调用工具
            Message(role=ROLE_ASSISTANT, tool_calls=[
                ToolCall(id="call_1", name="read_file",
                         arguments='{"path": "README.md"}'),
            ]),
            # Turn 2 的 Phase 1：慢思考
            Message(role=ROLE_ASSISTANT, content="已经读到内容，可以回答了。"),
            # Turn 2 的 Phase 2：给出最终回答，不再调工具
            Message(role=ROLE_ASSISTANT, content="README 里写的是：这是 README 的内容。"),
        ]
        eng = make_engine(tmp, responses, thinking=True)
        rep = RecordingReporter()
        eng.run("帮我看一下 README.md 里写了什么？", rep)

        kinds = [e[0] for e in rep.events]
        check(kinds.count("thinking") == 2, "开启慢思考时，每一轮都调用 on_thinking")
        check(kinds[0] == "thinking", "on_thinking 在模型回答之前触发")
        check(("tool_call", "read_file", '{"path": "README.md"}') in rep.events,
              "on_tool_call 带上工具名和原始 JSON 参数")
        check(any(e[0] == "tool_result" and e[1] == "read_file"
                  and e[2] == "这是 README 的内容。\n" and e[3] is False
                  for e in rep.events),
              "on_tool_result 汇报成功结果")
        check(kinds.count("message") == 1, "模型每给出一次文字回复就调用一次 on_message")
        check(kinds.index("tool_result") < kinds.index("message"),
              "顺序：先汇报工具结果，再汇报最终回答")


# ============================================================
# 测试 2：200 字截断
# ============================================================
def test_truncate():
    print("\n[测试 2] 工具输出超过 200 字时截断")
    with tempfile.TemporaryDirectory() as tmp:
        long_text = "长" * 500
        (Path(tmp) / "long.txt").write_text(long_text, encoding="utf-8")
        responses = [
            Message(role=ROLE_ASSISTANT, tool_calls=[
                ToolCall(id="call_1", name="read_file",
                         arguments='{"path": "long.txt"}'),
            ]),
            Message(role=ROLE_ASSISTANT, content="读完了。"),
        ]
        eng = make_engine(tmp, responses, thinking=False)
        rep = RecordingReporter()
        eng.run("读一下 long.txt", rep)

        results = [e for e in rep.events if e[0] == "tool_result"]
        check(len(results) == 1, "只汇报一次工具结果")
        check(results[0][2].endswith("... (已截断)"), "超过 200 字时追加截断标记")
        check(len(results[0][2]) == 200 + len("... (已截断)"),
              "汇报内容只保留前 200 个字")


# ============================================================
# 测试 3：FeishuReporter 的话术
# ============================================================
def test_feishu_reporter():
    print("\n[测试 3] FeishuReporter 把 4 个通知变成飞书消息")
    client = FakeFeishuClient()
    rep = FeishuReporter(client=client, chat_id="oc_test_chat")

    rep.on_thinking()
    rep.on_tool_call("bash", '{"command": "hostname -I"}')
    rep.on_tool_result("bash", "命令执行成功，无终端输出。", False)
    rep.on_tool_result("read_file", "打开文件失败: no such file", True)
    rep.on_message("查到的内网 IP 是 10.0.0.5。")

    texts = [m["content"]["text"] for m in client.sent]
    check(texts[0] == "🤔 模型正在慢思考 (Thinking)...", "on_thinking 话术正确")
    check(texts[1] == '🛠️ 正在执行工具: bash\n参数: {"command": "hostname -I"}',
          "on_tool_call 话术正确")
    check(texts[2] == "✅ 执行成功 (bash)", "成功时只发一句，不发完整输出")
    check(texts[3].startswith("⚠️ 执行报错 (read_file): "), "失败时发错误内容")
    check(texts[4] == "查到的内网 IP 是 10.0.0.5。", "on_message 原样转发")
    check(all(m["chat_id"] == "oc_test_chat" for m in client.sent),
          "所有消息都按 chat_id 发回同一个聊天窗口")
    check(all(m["msg_type"] == "text" for m in client.sent), "消息类型为 text")


# ============================================================
# 测试 4：FeishuBot 收消息
# ============================================================
def test_feishu_bot():
    print("\n[测试 4] FeishuBot 取出文字、去掉 @ 标记、记下 chat_id")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "README.md").write_text("工作区说明。\n", encoding="utf-8")
        responses = [
            Message(role=ROLE_ASSISTANT, tool_calls=[
                ToolCall(id="call_1", name="read_file",
                         arguments='{"path": "README.md"}'),
            ]),
            Message(role=ROLE_ASSISTANT, content="README 里写的是：工作区说明。"),
        ]
        eng = make_engine(tmp, responses)
        bot = FeishuBot(eng, "cli_fake_app_id", "fake_secret")
        bot.client = FakeFeishuClient()

        # 让新线程同步执行，测试才好断言
        class SyncThread:
            def __init__(self, target, args=(), daemon=None):
                self.target, self.args = target, args

            def start(self):
                self.target(*self.args)

        import internal.feishu.bot as bot_module
        origin_thread = bot_module.threading.Thread
        bot_module.threading.Thread = SyncThread
        try:
            # 群聊里 @机器人：飞书把 @ 转成 @_user_1 这样的标记
            group_msg = SimpleNamespace(
                message_type="text",
                content=json.dumps({"text": "@_user_1 帮我看一下 README.md"},
                                   ensure_ascii=False),
                chat_id="oc_group_chat",
            )
            bot.on_message_receive(SimpleNamespace(event=SimpleNamespace(message=group_msg)))

            # 非文本消息应被忽略，不产生任何回复
            before = len(bot.client.sent)
            image_msg = SimpleNamespace(message_type="image",
                                        content='{"image_key": "img_1"}',
                                        chat_id="oc_group_chat")
            bot.on_message_receive(SimpleNamespace(event=SimpleNamespace(message=image_msg)))
            check(len(bot.client.sent) == before, "图片等非文本消息被忽略")
        finally:
            bot_module.threading.Thread = origin_thread

        texts = [m["content"]["text"] for m in bot.client.sent]
        check(texts[0] == '🛠️ 正在执行工具: read_file\n参数: {"path": "README.md"}',
              "@ 标记被去掉后交给引擎，引擎收到的是干净的提问")
        check(texts[-1] == "README 里写的是：工作区说明。", "回答发回同一个群聊窗口")
        check(all(m["chat_id"] == "oc_group_chat" for m in bot.client.sent),
              "chat_id 取自消息来源")

        # 引擎崩溃时要把错误也发到飞书
        class BrokenEngine:
            def run(self, prompt, reporter=None):
                raise RuntimeError("模拟模型超时")

        broken_bot = FeishuBot(BrokenEngine(), "cli_fake_app_id", "fake_secret")
        broken_bot.client = FakeFeishuClient()
        broken_bot.handle_agent_run("oc_group_chat", "随便问一句")
        check(broken_bot.client.sent[0]["content"]["text"]
              .startswith("❌ Agent 运行崩溃: 模拟模型超时"),
              "引擎崩溃时把错误发到飞书，而不是让程序挂掉")


if __name__ == "__main__":
    print("========== 第 9 章 飞书集成 · 离线验证 ==========")
    test_engine_reporter()
    test_truncate()
    test_feishu_reporter()
    test_feishu_bot()
    print(f"\n🎉 全部通过：共 {PASSED} 项断言，未调用模型、未连接飞书。")
