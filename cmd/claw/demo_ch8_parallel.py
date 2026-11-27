# cmd/claw/main.py
# 对应 Go 版: cmd/claw/main.go
# 第 8 章：并行工具调用 —— 一次性读取 a.txt / b.txt / c.txt 三个文件。
# 运行方式（在 py-tiny-claw-all 目录下）: python -m cmd.claw.main
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from internal.engine.loop import AgentEngine
from internal.provider.openai import new_deepseek_provider
from internal.tools.bash import BashTool
from internal.tools.edit_file import EditFileTool
from internal.tools.read_file import ReadFileTool
from internal.tools.registry import new_registry
from internal.tools.write_file import WriteFileTool

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s",
                    datefmt="%Y/%m/%d %H:%M:%S")

# 测试 1：三个互相独立的读操作 -> 应当并发
PROMPT_READ = """
我当前目录下有 a.txt、b.txt、c.txt 三个文件。
为了节省时间，请你在同一轮中一次性调用工具读取这三个文件，
并将它们的内容综合起来告诉我。
"""

# 测试 2：同一轮里混入写操作 -> 应当退回串行
PROMPT_MIX = """
请在同一轮中同时完成两件事：
1. 用 write_file 创建 d.txt，内容为"这是文件D"
2. 用 read_file 读取 a.txt
完成后告诉我 a.txt 的内容。
"""


def prepare_files(work_dir: Path):
    """准备测试文件（等价于教材中的 3 条 echo 命令）"""
    files = {
        "a.txt": "这是文件A，里面记录了前端的报错日志。",
        "b.txt": "这是文件B，里面记录了后端的接口响应时间。",
        "c.txt": "这是文件C，里面写着今天的日期是周五。",
    }
    for name, text in files.items():
        (work_dir / name).write_text(text + "\n", encoding="utf-8")


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        sys.exit("请先配置 DEEPSEEK_API_KEY 环境变量")

    work_dir = PROJECT_ROOT / "workspace"
    work_dir.mkdir(exist_ok=True)
    prepare_files(work_dir)

    llm_provider = new_deepseek_provider("deepseek-v4-flash")
    registry = new_registry()
    registry.register(ReadFileTool(str(work_dir)))
    registry.register(WriteFileTool(str(work_dir)))
    registry.register(BashTool(str(work_dir)))
    registry.register(EditFileTool(str(work_dir)))

    # 为节省 token 关闭慢思考；模型不肯一次发多个调用时可改为 True
    eng = AgentEngine(llm_provider, registry, str(work_dir), False)

    try:
        eng.run(PROMPT_READ)   # 测试 2 时改为 eng.run(PROMPT_MIX)
    except Exception as e:
        sys.exit(f"引擎运行崩溃: {e}")


if __name__ == "__main__":
    main()
