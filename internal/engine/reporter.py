# internal/engine/reporter.py
# 第 9 章：Reporter（汇报员）—— 把"干活"和"汇报"分开的岗位说明书。
# 引擎只认这份说明书规定的 4 个方法，具体发到飞书还是发到终端，由子类决定。
from abc import ABC, abstractmethod


class Reporter(ABC):
    """抽象基类只规定"要有哪些方法"，不写具体实现。
    子类必须把下面 4 个方法全部实现，否则无法实例化。"""

    @abstractmethod
    def on_thinking(self):
        """模型开始"慢思考"时调用（仅 enable_thinking=True 时触发）。
        用途：告诉用户"我在想，别着急"。"""
        ...

    @abstractmethod
    def on_tool_call(self, tool_name: str, args: str):
        """模型决定调用某个工具、即将执行之前调用。
        tool_name: 工具名，如 "read_file"、"bash"
        args:      模型给出的参数，原始 JSON 字符串"""
        ...

    @abstractmethod
    def on_tool_result(self, tool_name: str, result: str, is_error: bool):
        """工具执行完毕后调用。
        result:   工具输出（引擎已截断到 200 字左右）
        is_error: 工具是否执行失败"""
        ...

    @abstractmethod
    def on_message(self, content: str):
        """模型输出了一段要给用户看的文字（中间说明或最终回答）时调用。"""
        ...
