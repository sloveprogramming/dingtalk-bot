"""结构化日志配置。"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """配置全局日志。

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)。
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """获取带名称的日志器。

    Args:
        name: 日志器名称，通常用 __name__。

    Returns:
        配置好的 Logger 实例。
    """
    return logging.getLogger(name)
