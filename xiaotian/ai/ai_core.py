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
from ..manage.config import API_KEY, BASE_URL, XIAOTIAN_SYSTEM_PROMPT, GLOBAL_RATE_LIMIT, USER_RATE_LIMIT, MAX_MEMORY_COUNT


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
    
    def get_memory(self, memory_key: str) -> List[Dict[str, str]]:
        """获取指定的记忆"""
        return self.memory_storage.get(memory_key, [])
    
    def detect_emotion(self, message: str) -> str:
        """检测消息情绪 - 简单的关键词检测"""
        # 冷淡词汇
        cold_keywords = ['无聊', '没意思', '算了', '不想', '冷', '沉默', '不说话']
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
            ai_response = self._strip_md(ai_response)
            
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



# 移除可能的markdown格式
    def _strip_md(t: str) -> str:
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
            model = "moonshot-v1-8k"
            response = self.client.chat.completions.create(
                model=model,
                messages=prompt,
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