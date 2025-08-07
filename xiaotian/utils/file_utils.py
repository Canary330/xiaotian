"""
小天的文件工具模块
提供文件操作相关的功能
"""

import os
import shutil
import glob
import datetime
from typing import List, Optional


def ensure_directory(path: str) -> None:
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def cleanup_old_files(directory: str, pattern: str, days_to_keep: int = 30) -> List[str]:
    """清理指定目录中的旧文件，只保留最近几天的文件
    
    参数:
        directory: 目录路径
        pattern: 文件名匹配模式，如"*.log"
        days_to_keep: 保留的天数
        
    返回:
        删除的文件列表
    """
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return []
        
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
    deleted_files = []
    
    for file_path in glob.glob(os.path.join(directory, pattern)):
        try:
            # 获取文件修改时间
            mtime = os.path.getmtime(file_path)
            file_date = datetime.datetime.fromtimestamp(mtime)
            
            # 如果文件日期早于截止日期，则删除
            if file_date < cutoff_date:
                os.remove(file_path)
                deleted_files.append(file_path)
        except Exception as e:
            print(f"清理文件 {file_path} 失败: {str(e)}")
            
    return deleted_files
