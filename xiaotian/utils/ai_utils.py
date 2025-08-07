"""
小天的AI工具模块
提供AI文本优化等功能
"""

from typing import Callable, Any, Dict, List, Optional

class AIUtils:
    def __init__(self, ai_core=None):
        """初始化AI工具
        
        参数:
            ai_core: AI核心对象，提供get_response方法
        """
        self.ai_core = ai_core
    
    def optimize_text_length(self, text: str, target_min: int = 400, target_max: int = 550) -> str:
        """优化文本长度，使其在目标字数范围内
        
        参数:
            text: 原始文本
            target_min: 最小目标字数
            target_max: 最大目标字数
            
        返回:
            优化后的文本
        """
        if not self.ai_core:
            raise ValueError("没有设置AI核心，无法进行文本优化")
            
        current_length = len(text)
        
        # 如果文本已在目标范围内，直接返回
        if target_min <= current_length <= target_max:
            return text
            
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
4. 不要添加任何标记、注释或说明
5. 只返回扩展后的完整文本
6.请务必比较原文与期望区间的字数，并根据二者相差的大小来决定拓展的多少

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
5. 不要添加任何标记、注释或说明
6. 只返回压缩后的完整文本
7.请务必比较原文与期望区间的字数，并根据二者相差的大小来决定压缩的多少

请压缩约{need_compress}字的内容。"""
        
        # 调用AI进行文本优化
        try:
            optimized_text = self.ai_core.get_response(prompt, user_id="system")
            
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
