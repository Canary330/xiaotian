"""
小天的核心AI接口模块
"""

from openai import OpenAI
import json
import os
import re
import time
import random
from typing import List, Dict, Any
from ..manage.config import (
    API_KEY, BASE_URL, XIAOTIAN_SYSTEM_PROMPT, GLOBAL_RATE_LIMIT, USER_RATE_LIMIT, 
    MAX_MEMORY_COUNT, MEMORY_FILE, CHANGE_PERSONALITY_PROMPT, USE_MODEL, BASIC_PROMPT, 
    LIKE_THRESHOLDS, LIKE_PERSONALITY_CHANGE_THRESHOLD, LIKE_RESET_THRESHOLD, 
    GENTLE_PERSONALITY_LIKE_MULTIPLIER, SHARP_PERSONALITY_LIKE_MULTIPLIER, 
    GENTLE_PERSONALITY_INDICES, SHARP_PERSONALITY_INDICES, ENHANCED_GENTLE_PERSONALITIES, 
    ENHANCED_SHARP_PERSONALITIES, LIKE_EMOTIONS, LIKE_SPEED_DECAY_RATE, 
    LIKE_MIN_SPEED_MULTIPLIER, SYSTEM_PROMPT, LAST_PROMOT,RECYCLE_BIN
)

class XiaotianAI:
    def __init__(self):
        self.client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL
        )
        # 改为按用户/群组分别存储记忆
        self.memory_storage: Dict[str, List[Dict[str, str]]] = {}
        # 存储每个用户的固定性格索引或自定义性格文本
        self.user_personality: Dict[str, Any] = {}
        # 存储每个用户的like状态
        self.user_like_status: Dict[str, Dict] = {}
        self.api_calls = {
            'last_reset': time.time(),
            'count': 0,
            'user_counts': {}  # 用户级别的API调用计数
        }
        
        # 记录文件最后修改时间，用于判断是否需要重新加载
        self.memory_file_mtime = 0
        
        # 初始化时加载记忆
        self.load_memory(MEMORY_FILE)
        
        # 当前使用的模型（动态可变）
        self.current_model = USE_MODEL
        
    def change_model(self, new_model: str) -> str:
        """动态更换AI模型"""
        try:
            self.current_model = new_model
            return f"✅ 模型已更换为 {new_model}"
        except:
            return f"wrong"
            
    def _should_reload_memory(self, file_path: str) -> bool:
        """检查是否需要重新加载记忆文件"""
        try:
            if not os.path.exists(file_path):
                return False
            
            current_mtime = os.path.getmtime(file_path)
            if current_mtime > self.memory_file_mtime:
                self.memory_file_mtime = current_mtime
                return True
            return False
        except Exception:
            return False
    
    def _get_memory_key(self, user_id: str, group_id: str = None) -> str:
        """生成记忆存储键，区分私聊和群聊"""
        if group_id:
            return f"group_{group_id}_user_{user_id}" if user_id else f"group_{group_id}"
        else:
            return f"user_{user_id}"
    
    def add_to_memory(self, memory_key: str, role: str, content: str):
        """添加消息到指定的记忆中"""
        if memory_key not in self.memory_storage:
            self.memory_storage[memory_key] = []
        
        self.memory_storage[memory_key].append({"role": role, "content": content})
        
        # 保持记忆在限制范围内
        if len(self.memory_storage[memory_key]) > MAX_MEMORY_COUNT:
            self.memory_storage[memory_key] = self.memory_storage[memory_key][-MAX_MEMORY_COUNT:]
    
    def get_user_personality(self, memory_key: str) -> str:
        """获取或生成用户的固定性格"""
        # 如果用户还没有分配性格，随机选择一个内置性格
        if memory_key not in self.user_personality:
            personality_index = random.randint(0, len(XIAOTIAN_SYSTEM_PROMPT) - 1)
            self.user_personality[memory_key] = personality_index
            print(f"为用户 {memory_key} 分配性格索引: {personality_index}")
        
        # 获取用户的性格设定
        user_personality_data = self.user_personality[memory_key]
        
        # 如果是整数，说明是内置性格的索引
        if isinstance(user_personality_data, int):
            return XIAOTIAN_SYSTEM_PROMPT[user_personality_data]
        # 如果是字符串，说明是自定义性格文本
        elif isinstance(user_personality_data, str):
            return user_personality_data
        else:
            # 兜底：使用第一个内置性格
            return XIAOTIAN_SYSTEM_PROMPT[0]

    def generate_custom_personality(self, userprompt: str, memory_key: str) -> str:
        """根据用户需求为特定用户生成自定义性格"""
        try:
            generation_prompt = CHANGE_PERSONALITY_PROMPT
            generation_prompt = generation_prompt.replace("{userprompt}", userprompt)
            model = self.current_model

            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": generation_prompt}
                ],
                temperature=0.3
            )

            generated_personality = BASIC_PROMPT + response.choices[0].message.content.strip() + LAST_PROMOT

            # 直接为该用户设置自定义性格
            self.user_personality[memory_key] = generated_personality
            
            print(f"✨ 成功为用户 {memory_key} 生成专属自定义性格")
            
            return generated_personality
            
        except Exception as e:
            print(f"❌ 生成自定义性格失败: {e}")
            return None
    
    def get_personality_info(self, memory_key: str) -> dict:
        """获取用户当前性格信息"""
        if memory_key in self.user_personality:
            user_personality_data = self.user_personality[memory_key]
            
            if isinstance(user_personality_data, int):
                personality_type = "内置性格"
                personality_index = user_personality_data
            else:
                personality_type = "自定义性格"
                personality_index = -1  # 自定义性格没有索引
            
            return {
                "has_personality": True,
                "personality_index": personality_index,
                "personality_type": personality_type,
                "total_builtin": len(XIAOTIAN_SYSTEM_PROMPT),
                "is_custom": isinstance(user_personality_data, str)
            }
        else:
            return {
                "has_personality": False,
                "total_builtin": len(XIAOTIAN_SYSTEM_PROMPT),
                "is_custom": False
            }
    
    def reset_user_personality(self, memory_key: str) -> str:
        """重置用户性格（随机分配新的内置性格）"""
        if len(XIAOTIAN_SYSTEM_PROMPT) > 0:
            new_personality_index = random.randint(0, len(XIAOTIAN_SYSTEM_PROMPT) - 1)
            self.user_personality[memory_key] = new_personality_index
            self.save_memory(MEMORY_FILE)
            
            return f"✨ 已为你重新分配内置性格！新的性格索引：{new_personality_index}"
        else:
            return "❌ 没有可用的内置性格配置"
    
    def _extract_user_id_from_memory_key(self, memory_key: str) -> str:
        """从memory_key中提取纯用户ID"""
        if memory_key.startswith("group_"):
            # 格式: group_{group_id}_user_{user_id}
            parts = memory_key.split("_user_")
            if len(parts) == 2:
                return parts[1]
        elif memory_key.startswith("user_"):
            # 格式: user_{user_id}
            return memory_key[5:]  # 去掉"user_"前缀
        
        # 如果都不匹配，返回原始key
        return memory_key
    
    def get_user_like_status(self, user_id: str) -> Dict:
        """获取用户的like状态，从文件中读取（使用纯用户ID，不包含群聊信息）"""
        # 将memory_key中的用户ID提取出来，用于like状态存储
        like_key = f"user_{user_id}" if not user_id.startswith("user_") else user_id
        
        if like_key not in self.user_like_status:
            self.user_like_status[like_key] = {
                'total_like': 0.0,  # 改为浮点数，支持小数
                'last_change_direction': None,  # 记录上次性格改变的方向：'positive' 或 'negative'
                'reset_count': 0,  # 连续重置计数
                'original_personality': None,  # 保存原始性格
                'notified_thresholds': [],  # 已通知过的阈值列表
                'speed_multiplier': 1.0,  # 当前like变化速度倍率
                'personality_change_count': 0  # 性格变化次数
            }
        return self.user_like_status[like_key]
    
    def update_user_like(self, memory_key: str, like_change: int):
        """更新用户的like状态并保存到文件"""
        # 从memory_key中提取用户ID用于like状态
        user_id = self._extract_user_id_from_memory_key(memory_key)
        status = self.get_user_like_status(user_id)
        
        # 获取当前用户的性格类型，判断是温柔还是锐利（使用完整memory_key）
        personality_multiplier = self._get_personality_like_multiplier(memory_key)
        
        # 获取当前速度倍率
        speed_multiplier = status.get('speed_multiplier', 1.0)
        
        # 如果是负值（减少），乘以5倍，使减少永远比增加快
        if like_change < 0:
            like_change = like_change * 5
        
        # 应用性格倍率和速度倍率到like变化
        adjusted_like_change = round(like_change * personality_multiplier * speed_multiplier, 2)
        
        # 更新总like值（保留两位小数）
        status['total_like'] = round(status['total_like'] + adjusted_like_change, 2)
        
        # 检查是否需要调整性格
        should_reset = False
        notification_message = ""
        
        # 检查是否达到性格变化阈值
        if status['total_like'] >= LIKE_PERSONALITY_CHANGE_THRESHOLD and status.get('last_change_direction') == 'natural':
            # 保存原始性格（如果还没保存过）
            if status.get('original_personality') is None:
                status['original_personality'] = self.user_personality.get(memory_key)
            
            # 切换到正向增强性格
            self._adjust_personality_positive(memory_key)
            status['last_change_direction'] = 'positive'
            status['total_like'] = 0.0  # 清理like值
            
            # 应用速度衰减
            old_speed = status.get('speed_multiplier', 1.0)
            new_speed = max(old_speed * (1 - LIKE_SPEED_DECAY_RATE*0.2), LIKE_MIN_SPEED_MULTIPLIER)
            status['speed_multiplier'] = round(new_speed, 3)
            status['personality_change_count'] = status.get('personality_change_count', 0) + 1
            
            should_reset = True
            notification_message = f"🎉 你的好感度达到了{LIKE_PERSONALITY_CHANGE_THRESHOLD}～下次性格变化需要达到0（回到原性格）或-{abs(LIKE_RESET_THRESHOLD)}（恶劣性格）哦！\n💫 由于性格变化，好感度增长速度现在是原来的{status['speed_multiplier']:.1%}"
            
        elif status['total_like'] <= LIKE_RESET_THRESHOLD and status.get('last_change_direction') == 'natural':
            # 保存原始性格（如果还没保存过）
            if status.get('original_personality') is None:
                status['original_personality'] = self.user_personality.get(memory_key)
            
            # 切换到负向恶劣性格
            self._adjust_personality_negative(memory_key)
            status['last_change_direction'] = 'negative'
            status['total_like'] = 0.0  # 清理like值
            
            # 应用速度衰减
            old_speed = status.get('speed_multiplier', 1.0)
            new_speed = max(old_speed * (1 - LIKE_SPEED_DECAY_RATE*0.2), LIKE_MIN_SPEED_MULTIPLIER)
            status['speed_multiplier'] = round(new_speed, 3)
            status['personality_change_count'] = status.get('personality_change_count', 0) + 1
            
            should_reset = True
            notification_message = f"💔 哎呀...好感度降到了{LIKE_RESET_THRESHOLD}，我变得有点暴躁了...想要我变回来的话，需要达到0或者你主动要求哦\n💫 由于性格变化，好感度增长速度现在是原来的{status['speed_multiplier']:.1%}"
            
        elif status['total_like'] == 0 and status.get('original_personality') is not None and status.get('last_change_direction') != 'natural':
            # 回到原始性格
            self.user_personality[memory_key] = status['original_personality']
            status['last_change_direction'] = 'natural'
            status['original_personality'] = None
            status['speed_multiplier'] = 1.0
            should_reset = True
            notification_message = "😌 好感度回到了0，我也恢复成原来的样子啦～"
        
        # 检查是否达到新的阈值节点（需要通知用户）
        current_like = status['total_like']
        notified_thresholds = status.get('notified_thresholds', [])
        
        for threshold in LIKE_THRESHOLDS:
            # 正向阈值
            if current_like >= 5 and threshold not in notified_thresholds and current_like >= threshold:
                    next_threshold = self._get_next_threshold(threshold, True)
                    if next_threshold >= current_like:
                        continue
                    else:
                        notified_thresholds.append(threshold)
                        new_speed = LIKE_THRESHOLDS[threshold]  # 直接取固定值
                        status['speed_multiplier'] = new_speed
                        if next_threshold:
                            gap = round(next_threshold - current_like, 2)
                            notification_message += f"\n🎯 已达到好感度{threshold}！距离下一级还差{gap}点～"
                        else:
                            notification_message += f"\n🏆 恭喜达到好感度{threshold}！你已经是最高等级啦！"
                        break
            elif current_like <= -5 and threshold not in notified_thresholds and current_like <= threshold:
                next_threshold = self._get_next_threshold(threshold, False)
                if next_threshold >= current_like:
                    continue
                else:
                    notified_thresholds.append(threshold)
                    new_speed = LIKE_THRESHOLDS[threshold]  # 直接取固定值
                    status['speed_multiplier'] = new_speed
                    if next_threshold:
                        notification_message += f"\n⚠️ 好感度降到了{threshold}...下一个节点是{next_threshold}"
                    else:
                        notification_message += f"\n💥 好感度已经降到了{threshold}，已经是最低点了..."
                    break
        
        status['notified_thresholds'] = notified_thresholds
        
        # 保存状态到文件
        self.save_memory(MEMORY_FILE)
        
        return notification_message
    
    def _get_next_threshold(self, current_threshold: int, is_positive: bool) -> int:
        """获取下一个阈值"""
        if is_positive:
            # 正向：寻找比当前阈值大的最小值
            for threshold in sorted(LIKE_THRESHOLDS):
                if threshold > current_threshold:
                    return threshold
        else:
            # 负向：寻找比当前阈值小的最大值
            negative_thresholds = [t for t in sorted(LIKE_THRESHOLDS) if t < current_threshold]
            if negative_thresholds:
                return max(negative_thresholds)
        return None
    
    def get_like_emotion_and_attitude(self, like_value: float) -> tuple:
        """根据like值获取对应的表情和态度"""
        for (min_val, max_val), data in LIKE_EMOTIONS.items():
            if min_val <= like_value < max_val:
                return data["emoji"], data["attitude"]
        
        # 如果没有匹配到，使用默认值
        if like_value >= 0:
            return "😊", "友好平和"
        else:
            return "😐", "态度平淡"
    
    def format_like_display(self, like_value: float) -> str:
        """格式化like值显示，包含表情"""
        emoji, attitude = self.get_like_emotion_and_attitude(like_value)
        return f"{emoji}{like_value:.2f}"
    
    def _get_personality_like_multiplier(self, memory_key: str) -> float:
        user_personality_data = self.user_personality.get(memory_key)
        
        # 如果是整数索引（内置性格）
        if isinstance(user_personality_data, int):
            if user_personality_data in GENTLE_PERSONALITY_INDICES:
                return GENTLE_PERSONALITY_LIKE_MULTIPLIER
            elif user_personality_data in SHARP_PERSONALITY_INDICES:
                return SHARP_PERSONALITY_LIKE_MULTIPLIER
            else:
                return 0.5  # 默认倍率
        else:
            # 自定义性格，默认使用中等倍率
            return 0.5
    
    def _adjust_personality_positive(self, memory_key: str):
        """正向性格调整（温柔增强）"""
        # 随机选择一个增强温和性格
        new_personality = random.choice(ENHANCED_GENTLE_PERSONALITIES)
        # 存储为自定义性格文本
        self.user_personality[memory_key] = new_personality
        print(f"已为用户 {memory_key} 调整为增强温和性格")
    
    def _adjust_personality_negative(self, memory_key: str):
        """负向性格调整（锐利增强）"""
        # 随机选择一个增强锐利性格
        new_personality = random.choice(ENHANCED_SHARP_PERSONALITIES)
        # 存储为自定义性格文本
        self.user_personality[memory_key] = new_personality
        print(f"已为用户 {memory_key} 调整为增强锐利性格")
    
    def find_user_by_partial_id(self, partial_id: str, current_group_id: str = None) -> list:
        """根据部分用户ID查找完整的用户ID（搜索全局like状态中的用户）"""
        matches = []
        
        # 如果提供的是完整QQ号，直接返回
        if partial_id.isdigit() and len(partial_id) >= 5:
            # 检查这个用户是否存在于我们的系统中
            if f"user_{partial_id}" in self.user_like_status:
                return [partial_id]
            # 如果没有，但是看起来像有效的QQ号，也返回它
            if len(partial_id) >= 5 and len(partial_id) <= 10:
                return [partial_id]
        
        # 清理旧格式的数据并搜索用户
        keys_to_remove = []
        for like_key in list(self.user_like_status.keys()):
            if like_key.startswith("user_"):
                user_id = like_key[5:]  # 去掉"user_"前缀
                if partial_id in user_id:
                    matches.append(user_id)
            elif like_key.startswith("group_") and "_user_" in like_key:
                # 发现旧格式的group数据，需要清理
                print(f"发现旧格式的like数据: {like_key}，将被清理")
                keys_to_remove.append(like_key)
        
        # 清理旧格式的数据
        for key in keys_to_remove:
            del self.user_like_status[key]
            print(f"已清理旧格式数据: {key}")
        
        # 如果清理了数据，保存文件
        if keys_to_remove:
            self.save_memory(MEMORY_FILE)
            print(f"已清理 {len(keys_to_remove)} 个旧格式的like数据")
        
        return matches
    
    def transfer_like_value(self, source_memory_key: str, target_partial_id: str, transfer_amount: float = None, current_group_id: str = None) -> str:
        """使用自己的like值对冲目标用户的like值"""
        # 获取源用户ID和like状态
        source_user_id = self._extract_user_id_from_memory_key(source_memory_key)
        source_status = self.get_user_like_status(source_user_id)
        source_like = source_status['total_like']
        
        if source_like <= 0:
            return "❌ 你的like值不足，无法进行对冲操作"
        
        # 查找目标用户
        target_matches = self.find_user_by_partial_id(target_partial_id, current_group_id)
        
        if not target_matches:
            return f"❌ 未找到包含ID '{target_partial_id}' 的用户"
        elif len(target_matches) > 1:
            # 如果找到多个匹配，列出让用户选择
            match_list = '\n'.join([f"- {user_id}" for user_id in target_matches])
            return f"🔍 找到多个匹配用户，请提供更精确的ID：\n{match_list}"
        
        target_user_id = target_matches[0]
        target_status = self.get_user_like_status(target_user_id)
        target_like = target_status['total_like']
        
        # 如果没有指定对冲金额，返回用户当前状态和可选择的范围
        if transfer_amount is None:
            return f"💰 你的like值：{source_like:.2f}\\n🎯 目标用户like值：{target_like:.2f}\\n💫 可对冲范围：0.1 - {source_like:.2f}\\n📝 请使用：小天，与[@用户]对冲[金额]"
        
        # 验证对冲金额
        if transfer_amount <= 0:
            return "❌ 对冲金额必须大于0"
        if transfer_amount > source_like:
            return f"❌ 对冲金额不能超过你的like值 {source_like:.2f}"
        
        # 计算实际效果：被动方扣除8折金额（这里应该是减少，不是增加）
        actual_effect = transfer_amount * 0.8
        fee = transfer_amount - actual_effect
        
        # 检查被动方是否会低于-150
        new_target_like = target_like - actual_effect  # 对冲是减少目标用户的like值
        if new_target_like < -150:
            # 调整实际效果，使目标用户不低于-150
            max_effect = target_like + 150  # 最多只能减少到-150
            actual_effect = max_effect
            transfer_amount = actual_effect / 0.8
            fee = transfer_amount - actual_effect
            new_target_like = -150
            
            if transfer_amount > source_like:
                return f"❌ 目标用户like值接近下限，你的like值不足以进行有效对冲"
        
        # 执行对冲操作
        source_status['total_like'] = round(source_like - transfer_amount, 2)
        target_status['total_like'] = round(new_target_like, 2)
        
        # 保存状态
        self.save_memory(MEMORY_FILE)
        
        # 返回结果
        return f"✅ 对冲成功！\n💰 你的like值：{source_like:.2f} → {source_status['total_like']:.2f} (-{transfer_amount:.2f})\n🎯 目标用户like值：{target_like:.2f} → {target_status['total_like']:.2f} (-{actual_effect:.2f})\n💫 手续费：{fee:.2f}"
    
    def reset_user_like_system(self, memory_key: str) -> str:
        """重置用户的like系统（管理员功能）"""
        # 从memory_key中提取用户ID用于like状态
        user_id = self._extract_user_id_from_memory_key(memory_key)
        like_key = f"user_{user_id}"
        
        if like_key in self.user_like_status:
            # 重置like状态但保留基本结构
            self.user_like_status[like_key] = {
                'total_like': 0.0,
                'last_change_direction': None,
                'reset_count': 0,
                'original_personality': None,
                'notified_thresholds': [],
                'speed_multiplier': 1.0,
                'personality_change_count': 0
            }
            # 保存到文件
            self.save_memory(MEMORY_FILE)
            return f"✅ 已重置用户 {user_id} 的like系统"
        else:
            return f"⚠️ 用户 {user_id} 没有like记录"
    
    def restore_original_personality(self, memory_key: str) -> str:
        """恢复用户的原始性格（用户主动要求时调用）"""
        # 从memory_key中提取用户ID用于like状态
        user_id = self._extract_user_id_from_memory_key(memory_key)
        status = self.get_user_like_status(user_id)
        
        if status.get('original_personality') is not None:
            # 恢复原始性格
            self.user_personality[memory_key] = status['original_personality']
            status['last_change_direction'] = None
            status['original_personality'] = None
            status['total_like'] = 0.0  # 重置like值为浮点数
            
            # 保存状态
            self.save_memory(MEMORY_FILE)
            return "😌 好的，我已经恢复成原来的性格啦～感谢你的包容！"
        else:
            return "😊 我现在就是原来的性格哦，没有需要恢复的～"
    
    def parse_ai_response_for_like(self, ai_response: str) -> tuple:
        """解析AI回复中的JSON格式，返回(cleaned_response, like_value, wait_time, not_even_wrong)"""
        like_value = None
        wait_time = []
        content = []
        not_even_wrong = False
        
        if not ai_response:
            return "", None, None, False
            
        try:
            # 预处理：自动修复JSON中的未转义换行符
            cleaned_response = ai_response.strip()
            
            # 检查是否是JSON格式（包含花括号）
            if '{' in cleaned_response and '}' in cleaned_response:
                # 智能转义：只转义未转义的特殊字符
                def smart_escape_json_strings(text):
                    
                    field = 'content'
                    # 匹配特定字段的值：处理多行内容
                    field_pattern = f'("{field}"\\s*:\\s*")(.*?)("\\s*[,}}])'
                    
                    def smart_escape_field_value(match):
                        prefix = match.group(1)
                        value = match.group(2)
                        suffix = match.group(3)
                        # 智能转义：只转义未转义的字符
                        fixed_value = value
                        # 处理换行符：只转义未转义的 \n
                        # 使用负向前瞻，确保不转义已经转义的 \\n
                        fixed_value = re.sub(r'(?<!\\)\n', '\\\\n', fixed_value)
                        # 处理双引号：只转义未转义的 "
                        fixed_value = re.sub(r'(?<!\\)"', '\\\\"', fixed_value)
                        return prefix + fixed_value + suffix
                    text = re.sub(field_pattern, smart_escape_field_value, text, flags=re.DOTALL)
                    return text
                cleaned_response = smart_escape_json_strings(cleaned_response)
            
            # 尝试直接解析整个响应为JSON
            full_data = json.loads(cleaned_response)
            
            # 检查是否是新格式：{"data": [...], "like": 数字}
            if isinstance(full_data, dict) and 'data' in full_data:
                data_array = full_data['data']
                
                # 处理data数组中的每个对象
                for item in data_array:
                    if isinstance(item, dict):
                        if 'like' in item:
                            like_value = int(item['like'])
                        if 'wait_time' in item:
                            wait_time.append(int(item['wait_time']))
                        if 'content' in item:
                            cleaned_content = self._strip_md(item['content'])
                            content.append(cleaned_content)
                        if 'not_even_wrong' in item:
                            not_even_wrong = bool(item['not_even_wrong'])
                
                # 检查顶层是否有like字段
                if 'like' in full_data:
                    like_value = int(full_data['like'])
                    
                return content, like_value, wait_time, not_even_wrong
                
            # 如果是旧格式的单个JSON对象
            elif isinstance(full_data, dict):
                if 'like' in full_data:
                    like_value = int(full_data['like'])
                if 'wait_time' in full_data:
                    wait_time.append(int(full_data['wait_time']))
                if 'content' in full_data:
                    cleaned_content = self._strip_md(full_data['content'])
                    content.append(cleaned_content)
                if 'not_even_wrong' in full_data:
                    not_even_wrong = bool(full_data['not_even_wrong'])
                    
                return content, like_value, wait_time, not_even_wrong
        except Exception:
            pass
        
        # 如果没有解析到任何内容，返回原始响应
        if not content and not wait_time and like_value is None:
            content_ = self._strip_md(ai_response)
            return content_, None, None, False

        # 确保like_value有默认值
        if like_value is None:
            like_value = 0

        # 返回解析结果
        cleaned_response = content if content else ""
        
        # 如果标记为not_even_wrong，返回空字符串表示不回复
        if not_even_wrong:
            cleaned_response = ""
        
        return cleaned_response, like_value, wait_time, not_even_wrong
    
    def get_memory(self, memory_key: str) -> List[Dict[str, str]]:
        """获取指定的记忆"""
        return self.memory_storage.get(memory_key, [])
    
    def detect_emotion(self, message: str) -> str:
        """检测消息情绪 - 简单的关键词检测，优化性能"""
        # 冷淡词汇
        cold_keywords = ['无聊', '没意思', '算了', '不想', '冷', '沉默', '不说话']
        # 热情词汇  
        hot_keywords = ['激动', '兴奋', '开心', '高兴', '棒', '太好了', 'amazing', '牛逼', '厉害', '哇', '超级']
        
        message_lower = message.lower()
        
        # 快速检测，一旦找到就返回
        for word in cold_keywords:
            if word in message_lower:
                return 'cold'
                
        for word in hot_keywords:
            if word in message_lower:
                return 'hot'
                
        return 'neutral'
    
    def _check_rate_limit(self, user_id: str = None) -> bool:
        """检查API调用速率限制
        返回True表示允许调用，False表示已达到限制
        """
        now = time.time()
        
        # 每分钟重置计数
        if now - self.api_calls['last_reset'] > 60:
            self.api_calls['last_reset'] = now
            self.api_calls['count'] = 0
            self.api_calls['user_counts'] = {}
        
        # 检查全局速率限制
        if self.api_calls['count'] >= GLOBAL_RATE_LIMIT:
            return False
        
        # 检查用户级别速率限制
        if user_id:
            user_count = self.api_calls['user_counts'].get(user_id, 0)
            if user_count >= USER_RATE_LIMIT:
                return False
            self.api_calls['user_counts'][user_id] = user_count + 1
            
        # 增加全局计数
        self.api_calls['count'] += 1
        return True
            
    def get_response(self, user_message: str, user_id: str = None, group_id: str = None, use_tools: bool = False) -> str:
        """获取AI回复，支持按用户/群组分别记忆"""
        # 检查是否需要重新加载记忆
        if self._should_reload_memory(MEMORY_FILE):
            print("🔄 检测到记忆文件更新，重新加载...")
            self.load_memory(MEMORY_FILE)
        
        # 检查API调用速率限制
        if not self._check_rate_limit(user_id):
            return "请求过于频繁，请稍后再试~"
            
        try:
            # 获取记忆键
            memory_key = self._get_memory_key(user_id, group_id)
            
            # 获取用户的固定性格
            user_prompt = self.get_user_personality(memory_key)
            
            # 获取用户当前的like状态（使用提取的用户ID）
            extracted_user_id = self._extract_user_id_from_memory_key(memory_key)
            like_status = self.get_user_like_status(extracted_user_id)
            current_like = like_status['total_like']
            
            # 在系统提示词中添加当前好感度信息
            emoji, attitude = self.get_like_emotion_and_attitude(current_like)
            if current_like >= 0:
                like_info = f"\n\n请以{attitude}的说话方式回复, 说话方式有（友好平和，友好开心，开心愉快，很开心，特别亲近，超级喜欢，非常宠爱，深深喜爱，无比珍视，视为最重要的人，你是我的全世界，超越一切的爱这些），根据现在的好感度调整回复语气，每种方式不会改变回复字数）"
            else:
                like_info = f"\n\n请以{attitude}的说话方式回复, 说话方式有（极度愤怒，几乎不想理你，非常生气，态度恶劣，很不高兴，语气冲，不耐烦，敷衍回应，有些厌烦，冷淡疏远，态度平淡，略有不满，有些疑惑，还算友善，友好平和，中性平和这些），根据现在的好感度调整回复语气，每种方式不会改变回复字数）"
            user_prompt_with_like = user_prompt + like_info
            if user_id != "system":
            # 构建消息列表
                messages = [
                    {"role": "system", "content": user_prompt_with_like}
                ]

                # 添加对应的记忆
                messages.extend(self.get_memory(memory_key))

                # 添加当前用户消息
                messages.append({"role": "user", "content": user_message})

                # 不使用工具的普通调用
                model = self.current_model
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.6,
                    response_format={"type": "json_object"}
                )
                ai_response = response.choices[0].message.content
            else:
                # model = "moonshot-v1-8k"
                messages = [ {"role": "system", "content": SYSTEM_PROMPT[0]},
                    {"role": "user", "content": user_message}]
                response = self.client.chat.completions.create(
                    model=USE_MODEL,
                    messages=messages,
                    temperature=0.6,
                    )
                ai_response = response.choices[0].message.content


            # 更新对应的记忆
            self.add_to_memory(memory_key, "user", user_message)
            self.add_to_memory(memory_key, "assistant", ai_response)
            
            # 每次处理完消息后保存记忆
            self.save_memory(MEMORY_FILE)
            
            return ai_response
            
        except Exception as e:
            print(f"🔍 调试信息：")
            print(f"   - API密钥存在: {'是' if API_KEY else '否'}")
            print(f"   - 基础URL: {BASE_URL}")
            print(f"   - 错误类型: {type(e).__name__}")
            print(f"   - 错误详情: {str(e)}")
            
            # 根据错误类型提供不同的提示
            if "Connection error" in str(e) or "network" in str(e).lower():
                return "网络连接失败，请检查网络连接或稍后重试。"
            elif "authentication" in str(e).lower() or "api key" in str(e).lower():
                return "API密钥验证失败，请检查API密钥环境变量。"
            elif "rate limit" in str(e).lower():
                return "API调用频率超限，请稍后重试。"
            else:
                return f"抱歉，我遇到了一些问题：{str(e)}"
    
    
    def query_with_prompt(self, system_prompt: str, user_query: str) -> str:
        """使用自定义系统提示词进行查询，主要用于天气等功能"""
        try:
            # 调用API
            # model = "moonshot-v1-8k"
            
            response = self.client.chat.completions.create(
                model=USE_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"❌ 查询API失败: {str(e)}")
            return '{}'
    
    def save_memory(self, file_path: str):
        """保存记忆、用户性格和like状态到文件"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 在保存前，确保每个用户的记忆不超过最大限制
            for memory_key, memories in self.memory_storage.items():
                if len(memories) > MAX_MEMORY_COUNT:
                    # 保留最新的MAX_MEMORY_COUNT条记忆，删除最早的
                    self.memory_storage[memory_key] = memories[-MAX_MEMORY_COUNT:]
                    print(f"⚠️ 用户 {memory_key} 的记忆超过限制，已删除最早的 {len(memories) - MAX_MEMORY_COUNT} 条记忆")
            
            # 保存记忆、性格映射和like状态
            save_data = {
                'memory_storage': self.memory_storage,
                'user_personality': self.user_personality,
                'user_like_status': self.user_like_status
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            print(f"💾 记忆已保存，包含 {len(self.memory_storage)} 个用户记忆")
            
        except Exception as e:
            print(f"❌ 保存记忆文件失败: {e}")
            
    def delete_memory(self, file_path: str, keep_user_personality: bool = True):
        """将指定文件移动到回收站，并在源目录创建新文件，可选择是否保留user_personality"""
        try:
            if not os.path.isfile(file_path):
                print(f"文件不存在: {file_path}")
                return
            # 读取原文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            user_personality = {}
            if keep_user_personality and isinstance(data, dict):
                user_personality = data.get('user_personality', {})

            # 移动到回收站
            dest_dir = RECYCLE_BIN
            os.makedirs(dest_dir, exist_ok=True)
            filename = os.path.basename(file_path)
            dest_file = os.path.join(dest_dir, filename)
            os.rename(file_path, dest_file)
            print(f"已移动文件: {file_path} -> {dest_file}")
            print(f"✅ 已将文件 {file_path} 移动到回收站 {dest_dir}")

            if keep_user_personality:
                # 在源目录创建新文件
                new_data = {
                    "memory_storage": {},
                    "user_personality": user_personality,
                    "user_like_status": {}
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                print(f"✅ 已在源目录创建新文件: {file_path}，是否保留user_personality: {keep_user_personality}")
        except Exception as e:
            print(f"❌ 移动文件或创建新文件失败: {e}")
    
    def load_memory(self, file_path: str):
        """从文件加载记忆、用户性格和like状态"""
        try:
            if os.path.exists(file_path):
                # 更新文件修改时间
                self.memory_file_mtime = os.path.getmtime(file_path)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 兼容旧版本的内存文件格式
                    if isinstance(data, dict) and 'memory_storage' in data:
                        # 新格式
                        memory_storage = data.get('memory_storage', {})
                        # 在加载时检查每个用户的记忆数量，确保不超过限制
                        for memory_key, memories in memory_storage.items():
                            if len(memories) > MAX_MEMORY_COUNT:
                                memory_storage[memory_key] = memories[-MAX_MEMORY_COUNT:]
                                print(f"⚠️ 加载记忆时：用户 {memory_key} 的记忆超过限制，已截取最近的 {MAX_MEMORY_COUNT} 条")
                        
                        self.memory_storage = memory_storage
                        self.user_personality = data.get('user_personality', {})
                        self.user_like_status = data.get('user_like_status', {})
                    elif isinstance(data, list):
                        # 旧格式：直接是memory列表，需要迁移
                        # 在加载时确保旧格式记忆也不超过限制
                        if len(data) > MAX_MEMORY_COUNT:
                            data = data[-MAX_MEMORY_COUNT:]
                            print(f"⚠️ 加载旧格式记忆时：记忆数量超过限制，已截取最近的 {MAX_MEMORY_COUNT} 条")
                        self.memory_storage = {'default': data}  # 将旧记忆放入默认键
                        self.user_personality = {}
                        self.user_like_status = {}
                    else:
                        # 其他旧格式
                        self.memory_storage = data if isinstance(data, dict) else {}
                        self.user_personality = {}
                        self.user_like_status = {}
                        
                print(f"✅ 成功加载记忆文件，包含 {len(self.memory_storage)} 个用户记忆")
            else:
                print(f"📁 记忆文件不存在，将创建新的记忆文件: {file_path}")
                # 重置文件修改时间
                self.memory_file_mtime = 0
                
        except Exception as e:
            print(f"❌ 加载记忆文件失败: {e}")
            # 初始化为空，不影响程序运行
            self.memory_storage = {}
            self.user_personality = {}
            self.user_like_status = {}
            self.memory_file_mtime = 0



    # 移除可能的markdown格式
    def _strip_md(self, t: str) -> str:
        if not t:
            return t
        # 移除代码块
        t = re.sub(r'```.*?```', '', t, flags=re.DOTALL)
        # 移除行内代码
        t = re.sub(r'`([^`]+)`', r'\1', t)
        # 链接与图片: ![alt](url) 或 [text](url)
        t = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', t)
        t = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', t)
        # 粗体 / 斜体 / 删除线
        t = re.sub(r'\*\*\*([^*]+)\*\*\*', r'\1', t)
        t = re.sub(r'___([^_]+)___', r'\1', t)
        t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
        t = re.sub(r'__([^_]+)__', r'\1', t)
        t = re.sub(r'\*([^*]+)\*', r'\1', t)
        t = re.sub(r'_([^_]+)_', r'\1', t)
        t = re.sub(r'~~([^~]+)~~', r'\1', t)
        # 标题前缀
        t = re.sub(r'^\s{0,3}#{1,6}\s*', '', t, flags=re.MULTILINE)
        # 引用符号
        t = re.sub(r'^\s{0,3}>\s?', '', t, flags=re.MULTILINE)
        # 列表项目符号
        t = re.sub(r'^\s*[-*+]\s+', '', t, flags=re.MULTILINE)
        t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)
        # 水平线
        t = re.sub(r'^\s*([-*_]\s*){3,}$', '', t, flags=re.MULTILINE)
        # 多余空行
        t = re.sub(r'\n{3,}', '\n\n', t)
        return t.strip()
    

    def optimize_text_length(self, text: str, target_min: int = 400, target_max: int = 550) -> str:
        """优化文本长度，使其在目标字数范围内
        
        参数:
            text: 原始文本
            target_min: 最小目标字数
            target_max: 最大目标字数
            
        返回:
            优化后的文本
        """
        
        # 如果文本已在目标范围内，直接返回
        if target_min <= current_length <= target_max:
            return text
        
        
        current_length = len(text)
            
        # 计算需要调整的字数
        if current_length < target_min:
            # 需要扩展
            need_expand = target_min - current_length
            target_length = (target_min + target_max) // 2  # 目标长度设为中间值
            
            prompt = f"""请扩展以下文本，原文{current_length}字，需要扩展到{target_length}字左右（{target_min}-{target_max}字之间）。

原文内容：
{text}

要求：
1. 保持原文意思和结构
2. 自然地添加相关细节、描述或补充信息
3. 确保扩展后的内容与原文风格一致
4. 不要添加任何标记、注释或说明，以及markdown格式
5. 只返回扩展后的完整文本
6.请务必比较原文与期望区间的字数，并根据二者相差的大小来决定拓展的多少
7.请确保扩展后的文本与原文在语气和风格上保持一致，这是一篇海报
8.如果原文有过多的小标题，请尽可能去除它们

请扩展约{need_expand}字的内容。"""
        else:  # current_length > target_max
            # 需要压缩
            need_compress = current_length - target_max
            target_length = (target_min + target_max) // 2  # 目标长度设为中间值
            
            prompt = f"""请压缩以下文本，原文{current_length}字，需要压缩到{target_length}字左右（{target_min}-{target_max}字之间）。

原文内容：
{text}

要求：
1. 保留最重要的信息和核心内容
2. 删除冗余、重复或次要的内容
3. 确保压缩后的文本仍然连贯完整
4. 保持原文的主要观点和结构
5. 不要添加任何标记、注释或说明，以及markdown格式
6. 只返回压缩后的完整文本
7. 请务必比较原文与期望区间的字数，并根据二者相差的大小来决定压缩的多少
8. 请确保压缩后的文本与原文在语气和风格上保持一致，这是一篇海报
9. 如果原文有过多的小标题，请尽可能去除它们

请压缩约{need_compress}字的内容。"""
        
        # 调用AI进行文本优化
        try:
            print(f"正在优化文本长度：原{current_length}字，目标{target_min}-{target_max}字")
            model = self.current_model
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            optimized_text = response.choices[0].message.content
            
            # 清理可能的额外内容（如果AI添加了一些不需要的说明）
            lines = optimized_text.split("\n")
            cleaned_lines = []
            skip_patterns = ["扩展后的文本", "压缩后的文本", "字数：", "字数:", "以下是", "已扩展", "已压缩", "优化后"]
            
            for line in lines:
                line_lower = line.lower().strip()
                # 跳过包含标记词的行
                if any(pattern in line_lower for pattern in skip_patterns):
                    continue
                # 跳过纯数字行或很短的标记行
                if len(line.strip()) < 5 and not any(char in line for char in "。！？"):
                    continue
                cleaned_lines.append(line)
            
            result = "\n".join(cleaned_lines).strip()
            
            # 验证结果长度
            result_length = len(result)
            print(f"文本优化结果：原{current_length}字 -> {result_length}字")
            
            # 如果结果仍然不在理想范围内，但至少有改善，就接受
            if result_length > 0 and abs(result_length - target_length) < abs(current_length - target_length):
                return result
            elif target_min <= result_length <= target_max:
                return result
            else:
                # 如果优化失败，返回原文
                print(f"警告：AI优化未达到预期效果，返回原文")
                return text
                
        except Exception as e:
            print(f"AI文本优化失败: {e}")
            return text