# internal/feishu/bot.py
# 第 9 章：飞书机器人的"一收一发"。
# FeishuBot     —— 收：收到飞书消息，取出文字和 chat_id，开新线程交给引擎；
# FeishuReporter —— 发：把引擎在关键时刻的通知，按 chat_id 发回同一个聊天窗口。
import json
import logging
import re
import threading

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)

from internal.engine.loop import AgentEngine
from internal.engine.reporter import Reporter

log = logging.getLogger(__name__)


class FeishuBot:
    """收消息：长连接收到事件后，把问题交给引擎，把过程交给汇报员。"""

    def __init__(self, engine: AgentEngine, app_id: str, app_secret: str):
        self.engine = engine
        # 飞书客户端：App ID 相当于账号，App Secret 相当于密码
        self.client = (
            lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )

    def get_event_dispatcher(self):
        """注册"接收消息"事件，返回事件分发器，交给长连接客户端使用。"""
        return (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self.on_message_receive)
            .build()
        )

    def on_message_receive(self, event: P2ImMessageReceiveV1) -> None:
        """每当有人给机器人发消息（私聊或群里 @ 它），SDK 就会调用这个函数。"""
        message = event.event.message

        # 1. 只处理文本消息，图片、文件等一律忽略
        if message.message_type != "text":
            log.info("[Feishu] 忽略非文本消息: %s", message.message_type)
            return

        # 2. 飞书发来的是 JSON 字符串，如 {"text":"@_user_1 帮我看看 README.md"}
        try:
            text = json.loads(message.content).get("text", "")
        except (TypeError, json.JSONDecodeError):
            log.info("[Feishu] 消息内容解析失败，已忽略")
            return

        # 3. 去掉群里 @机器人 留下的标记 @_user_1
        text = re.sub(r"@_user_\d+", "", text).strip()
        if text == "":
            log.info("[Feishu] 消息为空（可能只 @ 了机器人），已忽略")
            return

        # 4. 记下这条消息来自哪个聊天窗口，回消息时要发回这里
        chat_id = message.chat_id
        log.info("[Feishu] 收到 %s 的消息: %s", chat_id, text)

        # 5. 开一个新线程在后台跑 Agent：
        #    长连接的事件回调必须立刻返回，不能在这里阻塞等模型
        threading.Thread(
            target=self.handle_agent_run,
            args=(chat_id, text),
            daemon=True,
        ).start()

    def handle_agent_run(self, chat_id: str, prompt: str):
        """运行在新线程里，是真正干活的地方。"""
        reporter = FeishuReporter(client=self.client, chat_id=chat_id)
        try:
            self.engine.run(prompt, reporter)
        except Exception as e:
            log.error("[Feishu] Agent 运行崩溃: %s", e)
            reporter.send_msg(f"❌ Agent 运行崩溃: {e}")


class FeishuReporter(Reporter):
    """发消息：把引擎的 4 个关键时刻翻译成一句话，发回飞书聊天窗口。"""

    def __init__(self, client: lark.Client, chat_id: str):
        self.client = client
        self.chat_id = chat_id

    def send_msg(self, text: str):
        """按 chat_id 把一段文字发到飞书（text 消息类型）。"""
        if text == "":
            return

        req = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(self.chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .build()
            )
            .build()
        )

        resp = self.client.im.v1.message.create(req)
        if not resp.success():
            log.error("[Feishu] 发送消息失败: code=%s, msg=%s",
                      resp.code, resp.msg)

    def on_thinking(self):
        self.send_msg("🤔 模型正在慢思考 (Thinking)...")

    def on_tool_call(self, tool_name: str, args: str):
        self.send_msg(f"🛠️ 正在执行工具: {tool_name}\n参数: {args}")

    def on_tool_result(self, tool_name: str, result: str, is_error: bool):
        if is_error:
            self.send_msg(f"⚠️ 执行报错 ({tool_name}): \n{result}")
        else:
            # 成功时只发一句，不发完整输出，避免刷屏
            self.send_msg(f"✅ 执行成功 ({tool_name})")

    def on_message(self, content: str):
        self.send_msg(content)
