"""
小天的好感度管理模块
负责处理好感度排行、月度清零和奖励发放
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import calendar
from .config import MEMORY_FILE

class LikeManager:
    """管理好感度排行、月度清零和奖励发放"""
    
    def __init__(self, root_manager=None, ai=None):
        """初始化好感度管理器"""
        self.root_manager = root_manager
        self.ai = ai
        
        # 上个月记录
        self.last_month_records = {}
        
        # 奖励设置
        self.reward_percentage = 0.5  # 奖励比例（前30%）
        self.min_reward_count = 3     # 最少奖励人数
        self.max_reward_count = 10    # 最多奖励人数
        
    def export_current_likes(self) -> Dict:
        """
        导出当前所有用户的好感度数据
        
        Returns:
            Dict: 用户ID -> 好感度数据的字典
        """
        if not self.ai:
            return {}
            
        result = {}
        
        # 遍历所有用户的like状态
        self.ai.load_memory(MEMORY_FILE)
        for memory_key, status in self.ai.user_like_status.items():
            # 提取用户ID
            user_id = self.ai._extract_user_id_from_memory_key(memory_key)
            if user_id:
                # 只保存总好感度值和方向
                result[user_id] = {
                    "total_like": status.get("total_like", 0),
                    "direction": status.get("last_change_direction"),
                    "memory_key": memory_key
                }
                
        return result
        
    def save_monthly_record(self) -> str:
        """
        保存当前月度好感度记录
        
        Returns:
            str: 操作结果消息
        """
        # 获取当前好感度数据
        likes_data = self.export_current_likes()
        
        if not likes_data:
            return "⚠️ 没有找到任何好感度数据"
            
        # 获取上个月的年月
        now = datetime.now()
        if now.month == 1:  # 如果是1月，上个月是去年12月
            last_month = 12
            last_year = now.year - 1
        else:
            last_month = now.month - 1
            last_year = now.year
            
        # 构建文件名和路径
        file_name = f"likes_{last_year}_{last_month:02d}.json"
        data_dir = os.path.join("xiaotian", "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        file_path = os.path.join(data_dir, file_name)
        
        # 保存数据
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(likes_data, f, ensure_ascii=False, indent=2)
            
            # 保存为上个月记录
            self.last_month_records = likes_data
            
            return f"✅ 已保存{last_year}年{last_month}月的好感度数据，共 {len(likes_data)} 位用户"
        except Exception as e:
            return f"❌ 保存好感度数据失败: {str(e)}"
            
    def reset_all_likes(self) -> str:
        """
        重置所有用户的好感度
        
        Returns:
            str: 操作结果消息
        """
        try:
            if not self.ai:
                return "⚠️ AI实例未初始化"
            
            # 重置前先保存记录
            save_result = self.save_monthly_record()
            
            # 确保MEMORY_FILE变量存在
            if not MEMORY_FILE or not isinstance(MEMORY_FILE, str):
                return f"{save_result}\n❌ MEMORY_FILE变量不是有效的字符串路径"
                
            self.ai.delete_memory(MEMORY_FILE, keep_user_personality=True)
            return f"{save_result}\n✅ 已重置用户的好感度"
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ 重置好感度时出错: {e}\n{error_trace}")
            return f"❌ 重置好感度失败: {str(e)}"
        
    def calculate_monthly_rewards(self) -> Tuple[List[Dict], str]:
        """
        计算月度好感度奖励名单
        
        Returns:
            Tuple[List[Dict], str]: (获奖用户列表, 结果消息)
        """
        try:
            if not self.last_month_records:
                return [], "⚠️ 没有找到上个月的好感度记录"
                
            # 过滤掉好感度为0的用户
            valid_users = [(user_id, data) for user_id, data in self.last_month_records.items() 
                          if data.get("total_like", 0) != 0]
            
            # 如果没有有效用户，返回空列表
            if not valid_users:
                return [], "⚠️ 上个月没有任何用户有非零好感度"
                
            # 按好感度排序（降序）
            sorted_users = sorted(valid_users, key=lambda x: x[1].get("total_like", 0), reverse=True)
            
            # 确定获奖人数
            total_valid_users = len(sorted_users)
            
            # 确保百分比值有效
            if not isinstance(self.reward_percentage, (int, float)) or self.reward_percentage <= 0:
                self.reward_percentage = 0.3  # 默认值
                
            reward_count = int(total_valid_users * self.reward_percentage)
            
            # 确保最小/最大限制有效
            if not isinstance(self.min_reward_count, int) or self.min_reward_count < 0:
                self.min_reward_count = 3  # 默认值
                
            if not isinstance(self.max_reward_count, int) or self.max_reward_count < self.min_reward_count:
                self.max_reward_count = 10  # 默认值
                
            # 应用最小/最大限制
            if total_valid_users < self.min_reward_count:
                # 如果总人数少于最小奖励人数，全部获奖
                reward_count = total_valid_users
            else:
                # 否则，应用百分比但限制在最小和最大范围内
                reward_count = max(self.min_reward_count, min(reward_count, self.max_reward_count))
            
            # 获取获奖用户
            winners = sorted_users[:reward_count]
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ 计算月度奖励时出错: {e}\n{error_trace}")
            return [], f"❌ 计算月度奖励失败: {str(e)}"
        
        try:
            # 构建获奖列表
            reward_list = []
            for i, (user_id, data) in enumerate(winners):
                reward_list.append({
                    "rank": i + 1,
                    "user_id": user_id,
                    "like": data.get("total_like", 0)
                })
                
            # 生成结果消息
            now = datetime.now()
            if now.month == 1:  # 如果是1月，上个月是去年12月
                last_month = 12
                last_year = now.year - 1
            else:
                last_month = now.month - 1
                last_year = now.year
                
            result_message = f"⚪ {last_year}年{last_month}月好感度排行榜前{reward_count}名（取30%且最多{self.max_reward_count}人）\n\n"
            
            for winner in reward_list:
                result_message += f"🏆 第{winner['rank']}名: [CQ:at,qq={winner['user_id']}], 好感度 {winner['like']:.2f}\n"
                
            result_message += f"\n共有 {reward_count} 位用户获奖。"
            self.last_month_records.clear()
            
            return reward_list, result_message
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ 生成奖励消息时出错: {e}\n{error_trace}")
            return [], f"❌ 生成奖励消息失败: {str(e)}"
        