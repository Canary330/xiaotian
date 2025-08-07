"""
小天的管理员功能模块
负责处理管理员命令和日志查看
"""

import os
import re
import shutil
import datetime
from typing import List, Dict, Optional, Tuple, Any
import glob


class AdminTools:
    def __init__(self, root_id: str, log_dir: str = "logs"):
        self.root_id = root_id  # 超级管理员ID
        self.log_dir = log_dir
        
        # 确保日志目录存在
        os.makedirs(self.log_dir, exist_ok=True)
    
    def is_root(self, user_id: str) -> bool:
        """检查用户是否是超级管理员"""
        return user_id == self.root_id
    
    def process_admin_command(self, user_id: str, message: str) -> Optional[Tuple[str, Any]]:
        """处理管理员命令
        
        返回值: Tuple[str, Any]，第一个元素是回复消息，第二个元素是附加数据（如图片路径）
        """
        if not self.is_root(user_id):
            return None  # 不是管理员，不处理
        
        # 处理查看日志的命令
        if message.strip() == "小天，查看日志":
            return self.get_today_logs()
            
        # 处理测试天文海报的命令
        elif message.startswith("小天，测试天文海报："):
            # 返回特殊标记，让外层调用者处理
            return ("TEST_ASTRONOMY_POSTER", message)
            
        # 处理测试词频统计的命令
        elif message.strip() == "小天，测试词频统计":
            # 返回特殊标记，让外层调用者处理
            return ("TEST_WORDSTATS", None)
            
        # 处理清理数据的命令
        elif message.strip() == "小天，清理数据":
            return ("CLEAN_DATA", None)
            
        return None  # 不是有效的管理员命令
    
    def get_today_logs(self) -> Tuple[str, Optional[str]]:
        """获取今天的日志"""
        today = datetime.datetime.now()
        log_pattern = os.path.join(self.log_dir, f"bot_{today.year}_{today.month:02d}_{today.day:02d}.log")
        
        log_files = glob.glob(log_pattern)
        if not log_files:
            return ("今天还没有日志记录。", None)
        
        # 获取最新的日志文件
        log_file = max(log_files, key=os.path.getmtime)
        
        try:
            # 读取日志内容
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 如果日志太长，只返回最后200行
            lines = content.splitlines()
            if len(lines) > 200:
                content = '\n'.join(lines[-200:])
                return (f"今日日志（最后200行）：\n\n{content}", None)
            else:
                return (f"今日日志：\n\n{content}", None)
        except Exception as e:
            return (f"读取日志失败：{str(e)}", None)
    
    def clean_old_logs(self, days_to_keep: int = 1) -> None:
        """清理旧日志，只保留最近几天的日志"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        
        # 查找所有日志文件
        log_files = glob.glob(os.path.join(self.log_dir, "bot_*.log"))
        
        for log_file in log_files:
            try:
                # 从文件名提取日期
                filename = os.path.basename(log_file)
                match = re.search(r'bot_(\d{4})_(\d{2})_(\d{2})\.log', filename)
                
                if match:
                    year, month, day = map(int, match.groups())
                    file_date = datetime.datetime(year, month, day)
                    
                    # 如果日期早于截止日期，则删除
                    if file_date < cutoff_date:
                        os.remove(log_file)
            except Exception as e:
                print(f"清理日志文件 {log_file} 失败: {str(e)}")
