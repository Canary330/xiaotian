"""
小天的消息统计模块
负责记录和分析消息数据
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict
from .config import STATS_FILE


class MessageStats:
    def __init__(self):
        self.stats_data = self.load_stats()
    
    def load_stats(self) -> Dict[str, Any]:
        """加载统计数据"""
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 确保所有字段都是 defaultdict
                return {
                    "daily_count": defaultdict(int, data.get("daily_count", {})),
                    "hourly_count": defaultdict(int, data.get("hourly_count", {})),
                    "user_count": defaultdict(int, data.get("user_count", {})),
                    "keyword_count": defaultdict(int, data.get("keyword_count", {})),
                    "total_messages": data.get("total_messages", 0)
                }
        return {
            "daily_count": defaultdict(int),
            "hourly_count": defaultdict(int),
            "user_count": defaultdict(int),
            "keyword_count": defaultdict(int),
            "total_messages": 0
        }
    
    def save_stats(self):
        """保存统计数据"""
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        # 转换 defaultdict 为普通 dict 以便序列化
        save_data = {
            "daily_count": dict(self.stats_data["daily_count"]),
            "hourly_count": dict(self.stats_data["hourly_count"]),
            "user_count": dict(self.stats_data["user_count"]),
            "keyword_count": dict(self.stats_data["keyword_count"]),
            "total_messages": self.stats_data["total_messages"]
        }
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    def record_message(self, user_id: str, message: str, is_ai_triggered: bool = False):
        """记录消息"""
        now = datetime.now()
        date_key = now.strftime("%Y-%m-%d")
        hour_key = now.strftime("%H")
        
        # 更新各项统计
        self.stats_data["daily_count"][date_key] += 1
        self.stats_data["hourly_count"][hour_key] += 1
        self.stats_data["user_count"][user_id] += 1
        self.stats_data["total_messages"] += 1
        
        # 如果是AI触发的消息，记录特殊标记
        if is_ai_triggered:
            ai_key = f"ai_triggered_{date_key}"
            if ai_key not in self.stats_data:
                self.stats_data[ai_key] = 0
            self.stats_data[ai_key] += 1
        
        # 关键词统计（简单实现）
        keywords = ["天文", "观星", "望远镜", "星座", "月亮", "太阳", "行星"]
        for keyword in keywords:
            if keyword in message:
                self.stats_data["keyword_count"][keyword] += 1
        
        self.save_stats()
    
    def get_daily_stats(self, days: int = 7) -> Dict[str, int]:
        """获取最近几天的统计"""
        result = {}
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            result[date] = self.stats_data["daily_count"].get(date, 0)
        return result
    
    def get_hourly_stats(self) -> Dict[str, int]:
        """获取24小时统计"""
        return dict(self.stats_data["hourly_count"])
    
    def get_user_stats(self) -> Dict[str, int]:
        """获取用户活跃度统计"""
        return dict(self.stats_data["user_count"])
    
    def get_keyword_stats(self) -> Dict[str, int]:
        """获取关键词统计"""
        return dict(self.stats_data["keyword_count"])
    
    def generate_daily_report(self) -> str:
        """生成每日报告"""
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = self.stats_data["daily_count"].get(today, 0)
        total_count = self.stats_data["total_messages"]
        
        # 最活跃用户
        user_stats = self.get_user_stats()
        if user_stats:
            most_active_user = max(user_stats.items(), key=lambda x: x[1])
        else:
            most_active_user = ("无", 0)
        
        # 热门关键词
        keyword_stats = self.get_keyword_stats()
        if keyword_stats:
            top_keyword = max(keyword_stats.items(), key=lambda x: x[1])
        else:
            top_keyword = ("无", 0)
        
        report = f"""📊 小天今日数据报告 ({today})
        
📈 今日消息数：{today_count}
📊 累计消息数：{total_count}
👤 最活跃用户：({most_active_user[1]}条)
🔥 热门关键词：{top_keyword[0]} (出现{top_keyword[1]}次)

💫 感谢大家对天文知识的热爱！"""
        
        return report
