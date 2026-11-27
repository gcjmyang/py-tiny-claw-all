# cmd/claw/main.py
# 第 9 / 10 章：装配引擎，然后把"消息从哪来、汇报发到哪"交给不同的汇报员。
#   RUN_MODE = "feishu"   —— 启动飞书机器人，在飞书里对话
#   RUN_MODE = "terminal" —— 不连飞书，直接在终端里输入问题
# 运行方式（在 py-tiny-claw-all 目录下）: python -m cmd.claw.main
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from internal.engine.loop import AgentEngine
from internal.engine.terminal_reporter import new_terminal_reporter
from internal.provider.openai import new_deepseek_provider
from internal.tools.bash import BashTool
from internal.tools.edit_file import EditFileTool
from internal.tools.read_file import ReadFileTool
from internal.tools.registry import new_registry
from internal.tools.write_file import WriteFileTool

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s",
                    datefmt="%Y/%m/%d %H:%M:%S")

# 运行模式：
#   "feishu"   —— 启动飞书机器人，在飞书里对话（需要 FEISHU_APP_ID / FEISHU_APP_SECRET）
#   "terminal" —— 不连飞书，直接在终端里输入问题，过程用 TerminalReporter 打印
# 也可以用环境变量临时切换：RUN_MODE=terminal python -m cmd.claw.main
RUN_MODE = os.getenv("RUN_MODE", "feishu")

README_TEXT = """# py-tiny-claw-all 工作区

这是 Agent 的工作区，所有 read_file / write_file / bash 操作都被锁定在这个目录里。

- 第 8 章：同一轮里的多个只读工具调用会并发执行（Fork-Join）；
- 第 9 章：引擎通过 Reporter 把过程汇报出去，FeishuReporter 发到飞书；
- 第 10 章：换一个 TerminalReporter，同样的引擎就能直接在终端里用。
"""


def load_env_file():
    """从项目根目录的 .env 读取配置（不覆盖已存在的环境变量）。"""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line == "" or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def prepare_workspace(work_dir: Path):
    """准备工作区：保证目录存在，并在首次运行时放一个 README.md。"""
    work_dir.mkdir(exist_ok=True)
    readme = work_dir / "README.md"
    if not readme.exists():
        readme.write_text(README_TEXT, encoding="utf-8")


def build_engine(work_dir: Path) -> AgentEngine:
    """装配引擎：挂载四个原语工具，工作区锁定在 workspace/。"""
    llm_provider = new_deepseek_provider("deepseek-v4-flash")

    registry = new_registry()
    registry.register(ReadFileTool(str(work_dir)))
    registry.register(WriteFileTool(str(work_dir)))
    registry.register(BashTool(str(work_dir)))
    registry.register(EditFileTool(str(work_dir)))

    # 关闭慢思考以节省 token；想看到 on_thinking 汇报时可改成 True
    return AgentEngine(llm_provider, registry, str(work_dir), False)


def run_terminal(eng: AgentEngine):
    """终端对话模式：循环读取输入，每句话跑一次引擎，输入 exit 退出。"""
    reporter = new_terminal_reporter()
    print("💻 终端模式已启动，输入你的问题（输入 exit 退出）")

    while True:
        try:
            prompt = input("\n👤 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if prompt in ("exit", "quit"):
            break
        if prompt == "":
            continue

        # 同一个引擎，换了一个汇报员
        try:
            eng.run(prompt, reporter)
        except Exception as e:
            print(f"❌ Agent 运行崩溃: {e}")


def run_feishu(eng: AgentEngine):
    """飞书模式：用长连接接收事件，程序一直运行、一直听消息。"""
    # 延迟导入：只跑终端模式时，不需要安装飞书 SDK
    import lark_oapi as lark

    from internal.feishu.bot import FeishuBot

    app_id = os.getenv("FEISHU_APP_ID", "")
    app_secret = os.getenv("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        sys.exit("请先配置 FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量")

    bot = FeishuBot(eng, app_id, app_secret)
    event_handler = bot.get_event_dispatcher()

    # 长连接：由我们的程序主动连上飞书，不需要公网地址。
    # 教材里的 Webhook 要飞书来访问我们的程序，必须公网 IP，这里不采用。
    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )

    print("🚀 py-tiny-claw-all 飞书机器人已启动，正在通过长连接接收事件...")
    ws_client.start()


def main():
    load_env_file()

    if not os.getenv("DEEPSEEK_API_KEY"):
        sys.exit("请先配置 DEEPSEEK_API_KEY 环境变量")

    work_dir = PROJECT_ROOT / "workspace"
    prepare_workspace(work_dir)

    eng = build_engine(work_dir)

    if RUN_MODE == "terminal":
        run_terminal(eng)
    else:
        run_feishu(eng)


if __name__ == "__main__":
    main()
