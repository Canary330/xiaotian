"""
小天的案件还原功能模块
负责生成与天文有关的案件，用户作为执政官进行推理
"""
import os
import time
import json
from openai import OpenAI
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

from ..manage.config import TRIGGER_WORDS, MOONSHOT_API_KEY, MOONSHOT_BASE_URL
from ..manage.root_manager import RootManager
from ..ai.ai_core import XiaotianAI


class CriminalCase:
    """案件还原类，处理天文案件推理"""
    
    def __init__(self, root_manager: RootManager = None, ai_core: XiaotianAI = None):
        """初始化案件还原模块"""
        self.root_manager = root_manager
        self.ai = ai_core
        self.client = OpenAI(
            api_key=MOONSHOT_API_KEY,
            base_url=MOONSHOT_BASE_URL
        )
        # 案件状态(每个群独立)
        self.active_cases = {}  # 群ID -> 案件状态字典
        
        # 好感度奖励设置
        self.reward_solve_case = 200  # 成功解决案件的奖励好感度
        
        # 超时时间设置 (4小时)
        self.case_timeout = 10 * 60  # 秒
    
    def start_case(self, group_id: str, user_id: str) -> str:
        """
        在指定群组开始一个新的案件
        
        Args:
            group_id: 群组ID
            user_id: 发起用户ID
            
        Returns:
            str: 新案件的介绍信息
        """
        # 检查该群是否有正在进行的案件
        if group_id in self.active_cases:
            return "⚠️ 本群已有一个正在进行的案件推理，请先完成当前案件或输入'小天 结束案件'来结束当前案件。"
        
        # 使用AI生成一个与天文有关的案件
        case_prompt = (
            "请你创作一个与天文有关的奇特案件，要求：\n"
            "1. 案件必须与天文学、宇宙、星球或天体现象有关\n"
            "2. 案件设定要有趣、奇特且具有想象力\n"
            "3. 小天是案件的探秘者，可以天马行空地发挥想象力\n"
            "4. 案件必须有一个出人意料的结局或真相\n"
            "5. 结局不要太容易猜到，但要合理\n"
            "6. 内容必须简洁，背景不超过150字，线索不超过100字，真相不超过100字\n\n"
            "请严格按以下格式生成：\n"
            "【案件背景】：简明描述案件的背景和发现过程（最多150字）\n"
            "【关键线索】：列出2-3条关键初始线索（总计最多100字）\n"
            "【真相】：案件的真相和结局，简明扼要（最多100字）"
        )
        
        
        try:
            # 使用AI的chat接口生成内容
            response = self.client.chat.completions.create(
                model=self.ai.current_model,
                messages=[
                    {"role": "user", "content": case_prompt}
                ],
                temperature=0.7
            )
            case_content = response.choices[0].message.content
            
            # 解析生成的内容
            background_part = ""
            clues_part = ""
            truth_part = ""
            
            if "【案件背景】" in case_content:
                parts = case_content.split("【关键线索】")
                if len(parts) > 1:
                    background_part = parts[0].replace("【案件背景】", "").strip()
                    
                    remaining = parts[1]
                    if "【真相】" in remaining:
                        clue_truth_parts = remaining.split("【真相】")
                        clues_part = clue_truth_parts[0].strip()
                        if len(clue_truth_parts) > 1:
                            truth_part = clue_truth_parts[1].strip()
            
            # 如果解析失败，使用整个生成的内容
            if not background_part:
                background_part = "一个神秘的天文现象正在发生..."
                clues_part = "初始线索尚不明确，需要执政官下达调查指令。"
                truth_part = "案件真相待揭晓。"
            
            # 创建新的案件状态
            case_state = {
                "background": background_part,
                "initial_clues": clues_part,
                "truth": truth_part,
                "start_time": datetime.now(),
                "initiator_id": user_id,
                "participants": {user_id: {"messages": 0, "guessed_truth": False}},
                "messages_history": [],
                "latest_clues": clues_part,
            }
            
            # 保存案件状态
            self.active_cases[group_id] = case_state
            
            # 生成案件介绍消息
            case_message = (
                f"🔍 天文案件还原开始！\n\n"
                f"🔮【案件背景】{background_part}\n\n"
                f"🫧【初始线索】{clues_part}\n\n"
                f"🌌 执政官大人，请根据线索进行推理并发布调查指令！\n"
                f"提示：输入'小天 结束案件'可提前结束本次案件调查；输入'检查:xxx'则会检查答案的正确性\n"
                f"⭐猜中案件有200好感度的奖励"
            )
            
            return case_message
            
        except Exception as e:
            return f"⚠️ 生成案件时出错：{str(e)}"
    
    def process_investigation(self, user_id: str, message: str, group_id: str) -> Tuple[str, str, bool]:
        """
        处理用户的调查指令
        
        Args:
            user_id: 用户ID
            message: 用户消息
            group_id: 群组ID
            
        Returns:
            Tuple[str, str, bool]: 
                - 调查结果
                - 新线索
                - 是否解决案件
        """
        if group_id not in self.active_cases:
            return "⚠️ 本群当前没有正在进行的案件调查！", "", False
        
        # 检测消息是否包含表情包、图片或其他非文本内容
        if "[CQ:image" in message or "[CQ:face" in message or "file=" in message or "url=" in message:
            return "⚠️ 执政官，请不要发送表情包或图片。案件调查需要明确的文字线索和推理，请使用文字描述您的想法和指令，以便我能正确理解和处理。", "", False
            
        case = self.active_cases[group_id]
        
        # 添加用户到参与者列表
        if user_id not in case["participants"]:
            case["participants"][user_id] = {"messages": 0, "guessed_truth": False}
        
        # 增加用户消息计数
        case["participants"][user_id]["messages"] += 1
        
        # 记录消息历史
        case["messages_history"].append({
            "user_id": user_id,
            "message": message,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 检查是否要结束案件
        if "结束" in message or "结束案件" in message:
            result_message = (
                f"📢 应执政官要求，案件调查已结束！\n\n"
                f"【案件真相】\n{case['truth']}\n\n"
                f"感谢各位执政官的参与！"
            )
            
            # 清理该群的案件
            del self.active_cases[group_id]
            
            return result_message, "", False
        
        try:
            # 检查是否是"检查："格式的命令
            is_check_command = False
            check_content = ""
            
            # 匹配"检查："或"检查:"开头的消息
            if message.strip().startswith(("检查：", "检查:")):
                is_check_command = True
                # 提取检查后面的内容
                check_content = message.strip()[3:].strip()  # 去掉"检查："或"检查:"
                
            # 初始化猜测结果为False
            guessed_truth = False
            
            # 用户使用"检查：xxx"格式发送检查命令
            if is_check_command:
                # 如果用户没有提供要检查的内容
                if not check_content:
                    return "⚠️ 请在检查后面添加您的推理内容，例如'检查：我认为凶手是某某'", "", False
                
                truth_check_prompt = (
                    f"以下是一个案件的真相：\n{case['truth']}\n\n"
                    f"用户的推理是：\n{check_content}\n\n"
                    f"请判断用户的推理是否已经猜中了案件的核心真相？"
                    f"请严格秉公判断，只有用户确实猜中了真相的核心要点才回答'是'。"
                    f"只允许回答'是'或'否'"
                )
                
                # 使用AI的chat接口判断真相
                response = self.client.chat.completions.create(
                    model=self.ai.current_model,
                    messages=[
                        {"role": "user", "content": truth_check_prompt}
                    ],
                        temperature=0.2
                    )
                truth_check_result = response.choices[0].message.content
                guessed_truth = "是" in truth_check_result.lower()
            
            # 更新用户状态
            case["participants"][user_id]["guessed_truth"] = guessed_truth
            
            # 处理"检查"命令
            if is_check_command:
                if guessed_truth:
                    # 用户之前猜中过真相
                    result_message = (
                        f"✅ 检查结果：执政官 [CQ:at,qq={user_id}]，根据您之前的推理，您已经成功猜中案件真相！\n\n"
                        f"【💎 案件真相】\n{case['truth']}\n\n"
                        f"✨ 案件已经解决，感谢各位执政官的参与！"
                    )
                    
                    # 清理该群的案件
                    del self.active_cases[group_id]
                    
                    return result_message, "", True
                else:
                    # 用户之前未猜中过真相
                    result_message = "❌ 检查结果：您目前的推理尚未接近真相，请继续调查。"
                    return result_message, "", False
            
            # 普通调查指令，不是检查命令
            elif guessed_truth:
                # 用户猜中真相
                result_message = (
                    f"🎉 恭喜执政官 [CQ:at,qq={user_id}]成功解开案件真相！\n\n"
                    f"【💎 案件真相】\n{case['truth']}\n\n"
                    f"✨ 案件已经解决，感谢各位执政官的参与！"
                )
                
                # 清理该群的案件
                del self.active_cases[group_id]
                
                return result_message, "", True
            else:
                # 用户未猜中，生成调查结果和新线索
                investigation_prompt = (
                    f"案件背景：{case['background']}\n"
                    f"案件真相：{case['truth']}\n"
                    f"当前线索：{case['latest_clues']}\n"
                    f"用户指令：{message}\n\n"
                    f"请根据用户的调查指令生成两部分内容：\n"
                    f"1. 调查结果：描述执行用户指令后发现的情况\n"
                    f"2. 新线索：提供新的线索，引导用户更接近真相，但不要直接揭示真相\n\n"
                    f"按严格按以下格式回答，不要有其他任何内容：\n"
                    f"【调查结果】\n(调查结果内容，最多50字)\n\n"
                    f"【新线索】\n(新线索内容，最多100字)"
                    f"如果你有非常足够的把握判断用户发送的是乱码，请按照既定格式回复，并将回复内容均改为“请不要乱发送消息”\n"
                )
                
                # 使用AI的chat接口生成调查结果
                response = self.client.chat.completions.create(
                    model=self.ai.current_model,
                    messages=[
                        {"role": "user", "content": investigation_prompt}
                    ],
                    temperature=0.7
                )
                investigation_result = response.choices[0].message.content
                
                # 解析生成的内容
                result_part = ""
                clues_part = ""
                
                if "【调查结果】" in investigation_result and "【新线索】" in investigation_result:
                    parts = investigation_result.split("【新线索】")
                    result_part = parts[0].replace("【调查结果】", "").strip()
                    if len(parts) > 1:
                        clues_part = parts[1].strip()
                
                # 如果解析失败，使用简单的默认回复
                if not result_part:
                    result_part = "调查正在进行中..."
                    clues_part = "需要进一步的调查。"
                
                # 更新最新线索
                case["latest_clues"] = clues_part
                
                return f"🌸【调查结果】{result_part}", f"🐚【新线索】{clues_part}", False
                
        except Exception as e:
            return f"⚠️ 处理调查指令时出错：{str(e)}", "", False
    
    def award_case_solved(self, user_id: str, group_id: str = None) -> int:
        """
        奖励解决案件的用户
        
        Args:
            user_id: 用户ID
            group_id: 群组ID（可选）
            
        Returns:
            int: 奖励的好感度
        """
        if not self.ai:
            return 0
            
        try:
            user_memory_key = self.ai._get_memory_key(user_id, group_id)
            like_change = self.reward_solve_case
            self.ai.update_user_like(user_memory_key, like_change)
            return like_change
        except Exception as e:
            print(f"奖励好感度失败：{str(e)}")
            return 0
    
    def check_case_timeout(self) -> Dict[str, Tuple[str, str]]:
        """
        检查并处理超时的案件
        
        Returns:
            Dict[str, Tuple[str, str]]: 群组ID -> (结束消息, 真相)
        """
        now = datetime.now()
        timeout_groups = {}
        
        for group_id, case in list(self.active_cases.items()):
            start_time = case["start_time"]
            elapsed = (now - start_time).total_seconds()
            
            if elapsed > self.case_timeout:
                # 生成超时消息
                timeout_message = (
                    f"⏱️ 案件调查时间已到！\n"
                    f"本次案件调查已经进行了{elapsed // 3600:.1f}小时，已自动结束。"
                )
                
                truth_message = (
                    f"【💎 案件真相】\n{case['truth']}\n\n"
                    f"✨ 案件已经结束，感谢各位执政官的参与！"
                )
                
                # 记录超时群组
                timeout_groups[group_id] = (timeout_message, truth_message)
                
                # 清理该群的案件
                del self.active_cases[group_id]
        
        return timeout_groups
    
    def daily_cleanup(self) -> int:
        """
        清理所有案件（用于每日清理任务）
        
        Returns:
            int: 清理的案件数量
        """
        count = len(self.active_cases)
        self.active_cases.clear()
        return count
