"""插件注册器 —— 插件管理与自动发现。"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from app.core.message.plugins.base import BasePlugin, PluginInfo
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PluginRegistry:
    """插件注册器。

    支持:
    - 手动注册: registry.register(plugin_instance)
    - 自动发现: registry.discover("app.core.message.plugins")
    """

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        """注册一个插件实例。

        Args:
            plugin: 插件实例。
        """
        self._plugins[plugin.name] = plugin
        logger.info("插件已注册: %s - %s", plugin.name, plugin.description)

    def get(self, name: str) -> BasePlugin | None:
        """按名称获取插件。"""
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginInfo]:
        """列出所有已注册插件的元信息。"""
        return [plugin.info() for plugin in self._plugins.values()]

    def discover(self, package_path: str) -> None:
        """自动发现并注册指定包下的所有插件。

        导入包中所有模块，每个模块应在其顶层通过
        `registry.register(MyPlugin())` 完成注册，或在模块内
        定义 get_plugin() 工厂函数。

        Args:
            package_path: 包路径，如 "app.core.message.plugins"。
        """
        try:
            package = importlib.import_module(package_path)
        except ImportError as exc:
            logger.warning("插件包导入失败: %s - %s", package_path, exc)
            return

        for _importer, modname, _ispkg in pkgutil.walk_packages(
            package.__path__, package.__name__ + "."
        ):
            if modname == package_path:
                continue
            try:
                importlib.import_module(modname)
                logger.debug("插件模块已加载: %s", modname)
            except Exception as exc:
                logger.warning("插件模块加载失败: %s - %s", modname, exc)
