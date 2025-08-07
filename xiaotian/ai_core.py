"""
小天的核心AI接口模块
负责与Moonshot API的交互
"""

from openai import OpenAI
import json
import os
import re
import time
from typing import List, Dict, Any
from .config import API_KEY, BASE_URL, XIAOTIAN_SYSTEM_PROMPT, GLOBAL_RATE_LIMIT, USER_RATE_LIMIT


class XiaotianAI:
    def __init__(self):
        self.client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL
        )
        # 改为按用户/群组分别存储记忆
        self.memory_storage: Dict[str, List[Dict[str, str]]] = {}
        self.api_calls = {
            'last_reset': time.time(),
            'count': 0,
            'user_counts': {}  # 用户级别的API调用计数
        }
        
    def _get_memory_key(self, user_id: str, group_id: str = None) -> str:
        """生成记忆存储键，区分私聊和群聊"""
        if group_id:
            return f"group_{group_id}"
        else:
            return f"user_{user_id}"
    
    def add_to_memory(self, memory_key: str, role: str, content: str):
        """添加消息到指定的记忆中"""
        if memory_key not in self.memory_storage:
            self.memory_storage[memory_key] = []
        
        self.memory_storage[memory_key].append({"role": role, "content": content})
        
        # 保持记忆在限制范围内
        if len(self.memory_storage[memory_key]) > 20:
            self.memory_storage[memory_key] = self.memory_storage[memory_key][-20:]
    
    def get_memory(self, memory_key: str) -> List[Dict[str, str]]:
        """获取指定的记忆"""
        return self.memory_storage.get(memory_key, [])
    
    def detect_emotion(self, message: str) -> str:
        """检测消息情绪 - 简单的关键词检测"""
        # 冷淡词汇
        cold_keywords = ['无聊', '没意思', '算了', '不想', '懒得', '随便', '无所谓', '冷', '沉默', '不说话']
        # 热情词汇
        hot_keywords = ['激动', '兴奋', '开心', '高兴', '棒', '太好了', 'amazing', '牛逼', '厉害', '哇', '超级']
        
        message_lower = message.lower()
        
        cold_count = sum(1 for word in cold_keywords if word in message_lower)
        hot_count = sum(1 for word in hot_keywords if word in message_lower)
        
        if cold_count > 0:
            cold_count = 0
            return 'cold'
        elif hot_count > 0:
            hot_count = 0
            return 'hot'
        else:
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
        # 检查API调用速率限制
        if not self._check_rate_limit(user_id):
            return "请求过于频繁，请稍后再试~"
            
        try:
            # 获取记忆键
            memory_key = self._get_memory_key(user_id, group_id)
            
            # 构建消息列表
            messages = [
                {"role": "system", "content": XIAOTIAN_SYSTEM_PROMPT}
            ]
            
            # 添加对应的记忆
            messages.extend(self.get_memory(memory_key))
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": user_message})
            
            # 调用API
            model = "moonshot-v1-8k"
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7  # 提高创造性
            )
            
            ai_response = response.choices[0].message.content
            
            # 更新对应的记忆
            self.add_to_memory(memory_key, "user", user_message)
            self.add_to_memory(memory_key, "assistant", ai_response)
            
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
            model = "moonshot-v1-8k"
            
            response = self.client.chat.completions.create(
                model=model,
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
        """保存记忆到文件"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)
    
    def load_memory(self, file_path: str):
        """从文件加载记忆"""
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                self.memory = json.load(f)
