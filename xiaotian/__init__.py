"""
小天AI智能体包
"""

__version__ = "2.1.1"
__author__ = "Mica"
__description__ = "专业的天文观测助手AI智能体"

from .ai.ai_core import XiaotianAI
from .scheduler import XiaotianScheduler
from .manage.root_manager import RootManager

__all__ = [
    "XiaotianAI",
    "XiaotianScheduler",
    "RootManager"
]
