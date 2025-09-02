"""
小天的天文竞答功能模块
负责处理天文知识竞答，增加用户好感度
"""

import os
import random
import time
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta

from ..manage.config import TRIGGER_WORDS
from ..manage.root_manager import RootManager
from ..ai.ai_core import XiaotianAI

class AstronomyQuiz:
    """天文竞答类，处理天文知识问答"""
    
    def __init__(self, root_manager: RootManager = None, ai_core: XiaotianAI = None):
        """初始化天文竞答模块"""
        self.root_manager = root_manager
        self.ai = ai_core
        
        # 竞答状态(每个群独立)
        self.active_quizzes = {}        # 群ID -> 竞答状态字典
        
        # 奖励设置
        self.reward_base = 5           # 基础奖励好感度
        self.reward_first_bonus = 10    # 最快答对奖励
        self.reward_time_bonus = 15     # 时间加成最大值
        self.quiz_duration = 20         # 答题时间
        
        # 用户积分
        self.user_scores = {}           # 用户ID -> 积分记录
        
        # 题库
        self.question_bank = []         # 题库列表
        
        # 题库文件路径
        self.question_bank_path = os.path.join("xiaotian", "data", "astronomy_questions.json")
        
        # 加载题库
        self._load_question_bank()
        self.reward_time_bonus = 15     # 时间加成(越快回答越多)
        self.penalty_wrong = 5          # 答错的惩罚
        self.max_penalty_times = 3      # 答错几次会被扣分
        
        # 积分统计
        self.user_scores = {}           # 用户答题积分 {user_id: {"correct": 正确数, "wrong": 错误数, "points": 积分}}
        
        # 加载题库
        self._load_question_bank()
        
    def _load_question_bank(self):
        """加载天文问题题库"""
        # 初始化题库
        self.question_bank = []
        
        # 题库文件路径
        self.question_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "astronomy_questions.json")
        # 如果文件存在，从文件加载题库
        if os.path.exists(self.question_file):
            try:
                with open(self.question_file, 'r', encoding='utf-8') as f:
                    self.question_bank = json.load(f)
                    
                # 检查每个题目是否有used标记，如果没有则添加
                for question in self.question_bank:
                    if "used" not in question:
                        question["used"] = 0
                    if "difficulty" not in question:
                        question["difficulty"] = "normal"
                        
                print(f"✓ 从文件加载天文竞答题库成功，共 {len(self.question_bank)} 题")
                    
            except Exception as e:
                print(f"❌ 加载题库文件失败: {e}")
                # 创建一个空题库
                self.question_bank = []
                print("⚠️ 题库为空，请确保题库文件存在并格式正确")
        else:
            print("⚠️ 题库文件不存在: {self.question_file}")
            self.question_bank = []
            
        # 计算未使用的题目数量
        unused_count = sum(1 for q in self.question_bank if q.get("used", 0) == 0)
        print(f"✓ 天文竞答题库加载完成，共 {len(self.question_bank)} 题，其中未使用 {unused_count} 题")

        
    def _save_question_bank(self):
        """保存题库到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.question_file), exist_ok=True)
            
            # 保存题库
            with open(self.question_file, 'w', encoding='utf-8') as f:
                json.dump(self.question_bank, f, ensure_ascii=False, indent=2)
                
            print(f"✓ 天文竞答题库已保存至文件")
            
        except Exception as e:
            print(f"❌ 保存题库失败: {e}")
            
    def check_question_bank_status(self):
        """检查题库状态，如果所有题目都已经使用过，则重置所有标记并通知管理员"""
        # 检查是否所有题目都已被使用
        all_used = all(q.get("used", 0) > 0 for q in self.question_bank)
        
        if all_used and self.question_bank:  # 确保题库不为空
            # 重置所有题目的使用标记
            for q in self.question_bank:
                q["used"] = 0
                
            # 保存题库
            self._save_question_bank()
            
            # 构建通知消息
            message = (f"🔄 天文竞答题库已经全部使用完毕，已重置所有题目标记\n"
                      f"📊 题库总题数：{len(self.question_bank)}道\n"
                      f"🕒 重置时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 返回通知消息以便发送给root管理员
            return message
        return None

    def start_quiz(self, group_id: str, question_count: int = 10) -> Tuple[str, str]:
        """
        在指定群组开始天文竞答
        
        Args:
            group_id: 群组ID
            question_count: 题目数量，默认10题
            
        Returns:
            Tuple[str, str]: 竞答开始提示信息和第一题信息
        """
        # 检查该群是否有正在进行的竞答
        if group_id in self.active_quizzes:
            return (f"⚠️ 本群已有一场竞答正在进行中！请等待当前竞答结束。", "")
        # 检查题库中是否有未使用的题目
        unused_questions = [q for q in self.question_bank if q.get("used", 0) == 0]
        
        # 如果所有题目都已使用过，检查并重置
        if not unused_questions and self.question_bank:
            status_message = self.check_question_bank_status()
            if status_message:
                # 通知root管理员（由调用者处理）
                unused_questions = self.question_bank  # 重置后所有题目都是未使用的
        
        # 如果还是没有足够的题目，随机选择题库中的题目
        if len(unused_questions) < question_count:
            available_questions = self.question_bank
        else:
            available_questions = unused_questions
            
        # 按难度分类题目
        easy_questions = [q for q in available_questions if q.get("difficulty", "normal").lower() == "easy"]
        normal_questions = [q for q in available_questions if q.get("difficulty", "normal").lower() == "normal"]
        difficult_questions = [q for q in available_questions if q.get("difficulty", "normal").lower() == "difficult"]
        
        # 如果某个难度级别没有足够的题目，可能需要从其他难度级别借题
        selected_questions = []
        
        # 计算每个难度级别需要的题目数量（从易到难）
        easy_count = (question_count * 2) // 9 + (1 if question_count % 3 > 0 else 0)
        normal_count = (question_count * 6) // 9 + (1 if question_count % 3 > 1 else 0)
        difficult_count = question_count - easy_count - normal_count
        
        # 选择题目 - 增加错误处理和边界检查
        try:
            # 确保计数值不会为负数
            easy_count = max(0, easy_count)
            normal_count = max(0, normal_count)
            difficult_count = max(0, difficult_count)
            
            if len(easy_questions) >= easy_count and easy_count > 0:
                selected_questions.extend(random.sample(easy_questions, easy_count))
            else:
                selected_questions.extend(easy_questions)
                easy_count_borrowed = easy_count - len(easy_questions)
                if easy_count_borrowed > 0:
                    normal_count += easy_count_borrowed  # 不足的部分从normal级别补充
            
            if len(normal_questions) >= normal_count and normal_count > 0:
                selected_questions.extend(random.sample(normal_questions, normal_count))
            else:
                selected_questions.extend(normal_questions)
                normal_count_borrowed = normal_count - len(normal_questions)
                if normal_count_borrowed > 0:
                    difficult_count += normal_count_borrowed  # 不足的部分从difficult级别补充
            
            if len(difficult_questions) >= difficult_count and difficult_count > 0:
                selected_questions.extend(random.sample(difficult_questions, difficult_count))
            else:
                selected_questions.extend(difficult_questions)
            
            # 如果还不够，随机选择
            remaining = question_count - len(selected_questions)
            if remaining > 0:
                remaining_questions = [q for q in available_questions if q not in selected_questions]
                if remaining_questions:
                    # 确保不会尝试采样超过可用数量的元素
                    sample_count = min(remaining, len(remaining_questions))
                    if sample_count > 0:  # 确保采样数量为正
                        selected_questions.extend(random.sample(remaining_questions, sample_count))
        except Exception as e:
            print(f"❌ 选择题目时出错: {e}")
            # 如果出错，直接使用所有可用题目中的前N个
            all_available = easy_questions + normal_questions + difficult_questions
            # 去重
            unique_questions = []
            seen_ids = set()
            for q in all_available:
                q_id = q.get("id", str(hash(str(q))))
                if q_id not in seen_ids:
                    unique_questions.append(q)
                    seen_ids.add(q_id)
            
            selected_questions = unique_questions[:question_count]
        
        # 打乱题目顺序，避免总是先出简单题
        random.shuffle(selected_questions)
        
        # 标记这些题目为已使用
        for q in selected_questions:
            q["used"] = 1
            
        # 确保每个问题都有难度标记
        for q in selected_questions:
            if "difficulty" not in q:
                q["difficulty"] = "normal"
            
        # 保存更新后的题库
        self._save_question_bank()
        
        # 创建新的竞答状态
        quiz_state = {
            "questions": selected_questions,
            "current_question": 0,  # 当前是第几道题
            "start_time": datetime.now(),
            "duration": 20,  # 每题答题时间
            "participants": {},  # 参与者 {user_id: {'answers': [回答列表], 'times': [时间列表], 'score': 得分}}
            "round": 1,  # 当前是第几轮竞答
            "total_rounds": question_count,  # 总共几轮竞答
            "setting_count": False,  # 不再需要设置题目数量
            "scores": {}  # 用户得分 {user_id: 分数}
        }
        
        # 保存竞答状态
        self.active_quizzes[group_id] = quiz_state
        
        # 发送竞答开始提示
        start_message = (f"🌟 天文知识竞答开始！\n"
                         f"📚 本次题目数量：{question_count}题\n"
                         f"⏱️ 每题答题时间：{quiz_state['duration']}秒\n"
                         f"💰 规则：抢答制，且答对题目用时越短奖励越丰厚\n"
                         f" 提示：输入'结算'可提前结束本次竞答\n\n")
        
        # 直接开始第一道题
        first_question_message = self.next_question(group_id)
        return start_message, first_question_message

        
    def next_question(self, group_id) -> str:
        """进入下一题"""
        if group_id not in self.active_quizzes:
            return ""
            
        quiz = self.active_quizzes[group_id]
        
        # 增加当前题目索引
        quiz["current_question"] += 1
        
        # 检查是否已完成所有题目 - 修复题目数量
        # 使用等号而不是大于号，确保只问用户要求的题目数量
        if quiz["current_question"] > quiz["total_rounds"] or quiz["current_question"] > len(quiz["questions"]):
            # 竞答完成，返回结果
            return self.finish_quiz(group_id)
            
        # 获取当前题目
        current_index = quiz["current_question"] - 1
        question_data = quiz["questions"][current_index]
        
        # 重置当前题目的参与者
        quiz["participants"] = {}
        
        # 构建题目消息
        # 获取题目难度
        difficulty = question_data.get("difficulty", "normal")
        difficulty_emoji = {"easy": "🟢", "normal": "🟡", "difficult": "🔴"}.get(difficulty.lower(), "⚪")
        difficulty_text = {"easy": "简单", "normal": "普通", "difficult": "困难"}.get(difficulty.lower(), "未知")
        
        if question_data.get("type") == "fill_blank":
            # 填空题
            message = (f"🌟{quiz['current_question']} {difficulty_emoji}:"
                      f"问题：{question_data['question']}\n\n"
                      f"⏱️{quiz['duration']}秒\n"
                      f"📣 回答方式：请直接输入答案\n")
        else:
            # 选择题 - 随机排序选项
            options = question_data["options"].copy()  # 复制原始选项列表
            correct_option = options[question_data["correct"]]  # 记住正确答案
            
            # 随机打乱选项顺序
            option_mapping = list(range(len(options)))
            random.shuffle(option_mapping)
            
            # 创建新的随机排序选项列表
            shuffled_options = [options[i] for i in option_mapping]
            
            # 找到正确答案在新列表中的位置
            new_correct_index = shuffled_options.index(correct_option)
            
            # 保存新的选项和正确答案索引到题目状态中
            quiz["questions"][current_index]["shuffled_options"] = shuffled_options
            quiz["questions"][current_index]["shuffled_correct"] = new_correct_index
            
            # 生成选项文本
            options_text = ""
            for i, option in enumerate(shuffled_options):
                options_text += f"{chr(65+i)}. {option}\n"
                
            message = (f"🌟{quiz['current_question']} {difficulty_emoji}: "
                      f"问题：{question_data['question']}\n\n"
                      f"{options_text}\n"
                      f"⏱️ 答题时间：{quiz['duration']}秒\n"
                      f"📣 回答方式：请直接发送选项字母(A/B/C/D)\n")
        
        # 添加参考文献（如果有）
        if "reference" in question_data and question_data["reference"]:
            message += f"\n参考：{question_data['reference']}"
        # 更新开始时间
        quiz["start_time"] = datetime.now()
        return message
        
    def handle_question_timeout(self, group_id: str) -> Tuple[str, str]:
        """
        处理单个题目超时，展示答案并进入下一题
        
        Args:
            group_id: 群组ID
            
        Returns:
            Tuple[str, str]: 当前题目结果和下一题信息，分为两个部分返回
        """
        if group_id not in self.active_quizzes:
            return "⚠️ 本群当前没有正在进行的竞答！", ""
            
        quiz = self.active_quizzes[group_id]
        current_index = quiz["current_question"] - 1
        
        if current_index < 0 or current_index >= len(quiz["questions"]):
            return self.finish_quiz(group_id)
            
        question_data = quiz["questions"][current_index]
        
        # 构建结果消息
        difficulty = question_data.get("difficulty", "normal")
        difficulty_emoji = {"easy": "🟢", "normal": "🟡", "difficult": "🔴"}.get(difficulty.lower(), "⚪")
        difficulty_text = {"easy": "简单", "normal": "普通", "difficult": "困难"}.get(difficulty.lower(), "未知")
        
        if question_data.get("type") == "fill_blank":
            # 填空题
            result_message = (f"⏱️ 时间到！{difficulty_emoji} 难度：{difficulty_text}\n"
                             f"✅ 正确答案：{question_data['answer']}\n")
        else:
            # 选择题 - 处理随机排序的选项
            if "shuffled_options" in question_data and "shuffled_correct" in question_data:
                correct_option = question_data["shuffled_options"][question_data["shuffled_correct"]]
                correct_letter = chr(65 + question_data["shuffled_correct"])
            else:
                correct_option = question_data["options"][question_data["correct"]]
                correct_letter = chr(65 + question_data["correct"])
            
            result_message = (f"⏱️ 时间到！{difficulty_emoji} 难度：{difficulty_text}\n"
                             f"✅ 正确答案：{correct_letter}. {correct_option}\n")
        
        # 统计答对和答错的参与者
        correct_participants = []
        wrong_participants = []
        for user_id, data in quiz["participants"].items():
            if data.get("correct", False):
                correct_participants.append((user_id, data.get("time_used", 0)))
            else:
                wrong_participants.append(user_id)
        
        # 如果有人答对，按时间排序
        if correct_participants:
            # 按时间排序 - 最快答对的排在前面
            correct_participants.sort(key=lambda x: x[1])
            fastest_user_id = correct_participants[0][0]
            fastest_time = correct_participants[0][1]
            result_message += f"🥇 最快答对：用户 {fastest_user_id} (用时: {fastest_time:.1f}秒)\n"
            
        # 如果有答错的
        if wrong_participants:
            result_message += f"❌ 答错用户数: {len(wrong_participants)}\n"
        
        # 进入下一题
        next_question = self.next_question(group_id)
        
        # 返回两部分消息，让调用者决定如何发送
        if next_question:
            return result_message, next_question
        else:
            result_message2, final_message = self.finish_quiz(group_id)
            return result_message + "\n" + result_message2, final_message
    
    def finish_quiz(self, group_id: str, user_id: str = None) -> Tuple[str, str]:
        """
        完成整个竞答，计算结果并发放奖励
        
        Args:
            group_id: 群组ID
            user_id: 可选，提前结束竞答的用户ID
            
        Returns:
            Tuple[str, str]: 竞答结果信息的两个部分，用于分开发送
        """
        if group_id not in self.active_quizzes:
            return "⚠️ 本群当前没有正在进行的竞答！", ""
        
        quiz = self.active_quizzes[group_id]

        # 构建结果消息
        if user_id:
            result_message = f"🛑 用户提前结束了本次竞答！\n\n"
        else:
            result_message = f"🏁 天文知识竞答已完成！\n\n"
        
        # 统计所有用户得分
        user_scores = {}
        
        # 从quiz.scores直接获取最终得分
        user_scores = quiz.get("scores", {})
        
        # 如果没有记录，那么从参与者信息中计算
        if not user_scores:
            for u_id in set([u for q in quiz.get("questions", []) for u in quiz.get("participants", {}).keys()]):
                if u_id not in user_scores:
                    user_scores[u_id] = 0
            
        # 排序得分
        ranked_scores = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 根据参与人数计算奖励
        participant_count = len(ranked_scores)
        
        if participant_count >= 3:
            # 分配奖项 - 至少3人参加才有奖项
            result_message += "🏆 竞答排名与奖励：\n"
            
            # 根据排名分配奖励
            for i, (u_id, score) in enumerate(ranked_scores):
                if score <= 0:
                    reward = abs(score)
                    continue
                if i == 0:  # 第一名
                    reward = 500
                    result_message += f"🥇 第1名：[CQ:at,qq={u_id}]:{score:.2f}分，额外奖励 +{reward:.2f} 好感度\n"
                elif i == 1:  # 第二名
                    reward = 300
                    result_message += f"🥈 第2名：[CQ:at,qq={u_id}]:{score:.2f}分，额外奖励 +{reward:.2f} 好感度\n"
                elif i == 2:  # 第三名
                    reward = 100
                    result_message += f"🥉 第3名：[CQ:at,qq={u_id}]:{score:.2f}分，额外奖励 +{reward:.2f} 好感度\n"
                else:
                    reward = 1
                    # 只显示前10名
                    if i == min(10, participant_count):
                        result_message += f"...其余参与者各额外奖励 +{reward:.2f} 好感度\n"
                
                # 添加好感度奖励
                if self.ai:
                    try:
                        user_memory_key = self.ai._get_memory_key(u_id, group_id)
                        self.ai.update_user_like(user_memory_key, reward)
                    except Exception as e:
                        print(f"❌ 更新用户 {u_id} 好感度时出错: {e}")
        else:
            # 参与人数少于3人，按照得分比例奖励
            result_message += "🌱 竞答得分与奖励：\n"
            
            for u_id, score in ranked_scores:
                # 计算奖励
                reward = round(score, 2)
                if reward > 0:
                    # 正分按照得分计算奖励，每1分对应2点好感度
                    result_message += f"👤 [CQ:at,qq={u_id}]：{score:.2f}分，将按比例奖励好感度\n"
                elif score == 0:
                    # 0分给予参与奖励
                    reward = 5
                    result_message += f"👤 [CQ:at,qq={u_id}]：参与奖励 +{reward:.2f} 好感度\n"
                else:
                    result_message += f"👤 [CQ:at,qq={u_id}]：{score:.2f}，将扣除该成绩下1/4好感度\n"
        
        # 清理该群的竞答状态
        try:
            del self.active_quizzes[group_id]
        except Exception as e:
            print(f"❌ 清理竞答状态时发生异常: {e}")
            self.active_quizzes.clear()
        
        # 将结果消息分为两部分，以便分开发送
        # 第一部分：竞答结束标题
        part1 = result_message.split('\n\n')[0] if '\n\n' in result_message else result_message
        # 第二部分：详细结果
        part2 = '\n\n'.join(result_message.split('\n\n')[1:]) if '\n\n' in result_message else ""
        
        return part1, part2
        
    def process_answer(self, user_id: str, message: str, group_id: str) -> Tuple[str, str]:
        """
        处理用户的竞答回答
        
        Args:
            user_id: 用户ID
            message: 用户消息
            group_id: 群组ID
            
        Returns:
            Tuple[str, str]: 回答反馈和下一题/结果消息，如果不是当前群的竞答或不是有效回答则返回空字符串
        """
        # 检查该群是否有正在进行的竞答
        if group_id not in self.active_quizzes:
            return "", ""
            
        # 检查竞答是否已超时
        current_time = datetime.now()
        quiz = self.active_quizzes[group_id]
        
        # 检查当前题目是否已有人答对（抢答模式下，一旦有人答对就不再接受答案）
        has_correct_answer = any(p.get("correct", False) for p in quiz["participants"].values())
        if has_correct_answer:
            return "", ""
            
        # 检查用户是否已经回答过当前题目
        if user_id in quiz["participants"]:
            return "", ""  # 不重复提示，避免刷屏
            
        # 检查命令是否是结算指令
        if message.strip() == "结算" or message.strip().lower() == "结束":
            # 检查是否回答了至少一题
            if quiz.get("current_question", 0) > 1:  # 已经回答了至少一题
                return self.finish_quiz(group_id, user_id)
            else:
                return f"⚠️ 至少需要回答一题才能结算！"
            

        if (current_time - quiz["start_time"]).total_seconds() - 7 > quiz["duration"]:
            # 竞答已结束，触发结束流程并进入下一题或结束
            return self.handle_question_timeout(group_id)
            
        
        
        # 获取当前题目
        current_index = quiz["current_question"] - 1
        if current_index < 0 or current_index >= len(quiz["questions"]):
            return None
        
        question_data = quiz["questions"][current_index]
        
        # 处理选择题回答
        if question_data.get("type", "multiple_choice") == "multiple_choice":
            # 获取选项数量（使用随机排序后的选项列表）
            # 检查回答格式
            message = message.upper().strip()
            options_count = len(question_data.get("shuffled_options", question_data["options"]))
            
            if len(message) != 1 or message not in "ABCD"[:options_count]:
                return f"⚠️ 无效回答！请输入有效的选项字母 (A, B, C, D)"
                
            # 转换字母选项为索引
            answer_index = ord(message) - ord('A')
            
            # 判断是否正确（使用随机排序后的正确答案索引）
            if "shuffled_correct" in question_data:
                is_correct = (answer_index == question_data["shuffled_correct"])
            else:
                is_correct = (answer_index == question_data["correct"])
        
        # 处理填空题回答
        elif question_data.get("type") == "fill_blank":
            # 直接比较答案文本，忽略空格
            user_answer = message.strip()
            correct_answer = question_data["answer"].strip()
            is_correct = (user_answer == correct_answer)
            answer_index = message  # 保存原始答案文本
        
        else:
            return None  # 未知题目类型
            
        # 计算答题用时
        time_used = max(((current_time - quiz["start_time"]).total_seconds() - 7), 0)
        
        # 记录参与者回答
        quiz["participants"][user_id] = {
            "answer": answer_index,
            "time": current_time,
            "time_used": time_used,
            "correct": is_correct
        }
        
        # 初始化用户积分记录（如果不存在）
        if user_id not in self.user_scores:
            self.user_scores[user_id] = {"correct": 0, "wrong": 0, "points": 0}
        
        # 初始化当前竞答的用户得分记录（如果不存在）
        if user_id not in quiz.get("scores", {}):
            quiz.setdefault("scores", {})[user_id] = 0
        
        # 获取题目难度 - 将其移到if语句外面，使其对正确和错误的回答都可用
        difficulty = question_data.get("difficulty", "normal")
        
        # 更新用户积分统计
        if is_correct:
            # 判断是否是第一个答对的（始终为True，因为有人回答后立即进入下一题）
            is_first = True
            
            # 计算奖励分数
            points = self._calculate_reward(time_used, is_first, difficulty)
            
            # 记录积分
            self.user_scores[user_id]["correct"] += 1
            self.user_scores[user_id]["points"] += points
            quiz["scores"][user_id] = quiz["scores"].get(user_id, 0) + points
            response = f"🎉抢答正确！+{points:.2f}分"
            
            # 显示答题时间
            time_used_str = f"用时: {time_used:.1f}秒"
            response += f"\n⏱️ {time_used_str}"
        else:
            # 记录错误答题
            self.user_scores[user_id]["wrong"] += 1
            points = self._calculate_reward(time_used, is_first=False, difficulty=difficulty)
            self.user_scores[user_id]["points"] -= points  
            quiz["scores"][user_id] = quiz["scores"].get(user_id, 0) - points
            response = f"❌ 回答错误! -{points:.2f}分"
        
        # 计算好感度调整
        if self.ai:
            try:
                user_memory_key = self.ai._get_memory_key(user_id, group_id)
                if is_correct and points > 0:
                    # 答对，好感度直接加上分数
                    like_change = points
                    self.ai.update_user_like(user_memory_key, like_change)
                elif not is_correct and points > 0:
                    # 答错，好感度减去分数除以4，保留2位小数
                    like_change = -round(points / 4, 2)
                    self.ai.update_user_like(user_memory_key, like_change)
            except Exception as e:
                print(f"❌ 更新好感度时出错: {e}")
                
        # 无论对错，都立即进入下一题或结束竞答
        next_question = self.next_question(group_id)
        
        # 返回两个独立的消息，让调用者决定如何发送
        if next_question:
            return response, next_question
        else:
            return response, self.finish_quiz(group_id)
    
    def _calculate_reward(self, time_used: float, is_first: bool, difficulty: str = "normal") -> int:
        """
        计算竞答奖励的好感度
        
        Args:
            time_used: 回答用时(秒)
            is_first: 是否是第一个答对的
            difficulty: 题目难度，可以是"easy"、"normal"或"difficult"
            
        Returns:
            int: 奖励的好感度值
        """
        # 基础奖励
        reward = self.reward_base
        # 最快答对奖励
        if is_first:
            reward += self.reward_first_bonus
            
        # 时间加成 (越快回答越多)
        # 使用反比例函数计算时间系数
        if time_used <= self.quiz_duration * 0.8:
            # 定义一个平滑的二次函数
            a = 1000 / (self.quiz_duration * 0.8)**2
            c = 1
            # 计算 time_factor
            time_factor = a * (time_used - self.quiz_duration * 0.8)**2 + c
            # 确保 time_factor 在合理范围内
            time_factor = max(1, time_factor)
        elif time_used < 0:
            time_factor = 1000  # 超过quiz_duration * 0.8时，time_factor为0
        else:
            time_factor = 1
        reward *= time_factor
        print(time_used)


        # 根据难度调整基础奖励
        difficulty_multiplier = {
            "easy": 0.8,      # 简单题目基础奖励为80%
            "normal": 1.0,    # 正常难度基础奖励为100%
            "difficult": 2  # 困难题目基础奖励为200%
        }
        
        # 应用难度系数
        reward = reward * difficulty_multiplier.get(difficulty.lower(), 1.0)
        reward = round(reward, 1)
        # 确保总奖励不超过上限
        return min(reward, 5000)

        
    def check_quiz_timeout(self) -> Dict[str, str]:
        """
        检查所有群组的竞答是否超时，若超时则结束竞答
        
        Returns:
            Dict[str, str]: 群组ID -> 结束消息的字典
        """
        results = {}
        current_time = datetime.now()
        
        # 复制键列表以避免在迭代过程中修改字典
        for group_id in list(self.active_quizzes.keys()):
            quiz = self.active_quizzes[group_id]
            
            # 检查是否在设置题目数量阶段
            if quiz.get("setting_count", False):
                # 检查是否超过10秒
                if quiz.get("auto_start_time") and (current_time - quiz["auto_start_time"]).total_seconds() > 10:
                    # 自动开始竞答
                    quiz["setting_count"] = False
                    results[group_id] = self.next_question(group_id)
                    
            # 检查当前题目是否超时
            elif "start_time" in quiz and (current_time - quiz["start_time"]).total_seconds() > quiz["duration"]:
                results[group_id] = self.handle_question_timeout(group_id)
                
        return results
        
    def add_question(self, question_data: dict) -> str:
        """
        添加自定义竞答问题
        
        Args:
            question_data: 问题数据字典，包含题目内容和相关信息
                对于选择题：
                    {
                        "question": "问题内容",
                        "type": "multiple_choice",
                        "options": ["选项A", "选项B", "选项C", "选项D"],
                        "correct": 正确选项索引
                    }
                对于填空题：
                    {
                        "question": "问题内容",
                        "type": "fill_blank",
                        "answer": "正确答案"
                    }
            
        Returns:
            str: 添加结果信息
        """
        # 验证参数
        if "question" not in question_data:
            return "❌ 错误：缺少问题内容！"
            
        question_type = question_data.get("type", "multiple_choice")
        
        # 处理选择题
        if question_type == "multiple_choice":
            options = question_data.get("options", [])
            correct_index = question_data.get("correct")
            
            if not options:
                return "❌ 错误：选择题必须提供选项！"
                
            if not isinstance(correct_index, int) or not (0 <= correct_index < len(options)):
                return "❌ 错误：正确答案索引超出范围！"
                
            if len(options) < 2 or len(options) > 4:
                return "❌ 错误：选项数量必须在2-4个之间！"
                
        # 处理填空题
        elif question_type == "fill_blank":
            answer = question_data.get("answer")
            if not answer:
                return "❌ 错误：填空题必须提供正确答案！"
                
        else:
            return f"❌ 错误：不支持的题目类型 '{question_type}'！"
            
        # 添加used标记
        question_data["used"] = 0
        
        # 添加到题库
        self.question_bank.append(question_data)
        
        # 保存题库
        self._save_question_bank()
        
        return f"题目已成功添加到题库！当前题库共有 {len(self.question_bank)} 道题目"
    
    def edit_question_by_keyword(self, keyword: str, new_question_data: dict) -> str:
        """
        根据关键词查找并修改题目
        
        Args:
            keyword: 要查找的关键词
            new_question_data: 新的题目数据
            
        Returns:
            str: 修改结果信息
        """
        # 查找包含关键词的题目
        found_indices = []
        for i, q in enumerate(self.question_bank):
            question = q.get("question", "")
            if keyword.lower() in question.lower():
                found_indices.append(i)
                
        if not found_indices:
            return f"未找到包含关键词 '{keyword}' 的题目"
            
        if len(found_indices) > 1:
            # 找到多个匹配项，返回列表供用户选择
            result = f"找到 {len(found_indices)} 个匹配的题目，请使用更精确的关键词："
            for i, idx in enumerate(found_indices):
                question = self.question_bank[idx]["question"]
                result += f"\n{i+1}. {question[:30]}..."
            return result
            
        # 找到唯一匹配项，进行修改
        index = found_indices[0]
        old_question = self.question_bank[index]
        
        # 保留旧题目的使用状态
        new_question_data["used"] = old_question.get("used", 0)
        
        # 更新题目
        self.question_bank[index] = new_question_data
        
        # 保存题库
        self._save_question_bank()
        
        return f"题目已成功修改！原题目：{old_question['question'][:30]}..."
        
    def delete_question_by_keyword(self, keyword: str) -> str:
        """
        根据关键词删除题目
        
        Args:
            keyword: 要查找的关键词
            
        Returns:
            str: 删除结果信息
        """
        # 查找包含关键词的题目
        found_indices = []
        for i, q in enumerate(self.question_bank):
            question = q.get("question", "")
            if keyword.lower() in question.lower():
                found_indices.append(i)
                
        if not found_indices:
            return f"未找到包含关键词 '{keyword}' 的题目"
            
        if len(found_indices) > 1:
            # 找到多个匹配项，返回列表供用户选择
            result = f"找到 {len(found_indices)} 个匹配的题目，请使用更精确的关键词："
            for i, idx in enumerate(found_indices):
                question = self.question_bank[idx]["question"]
                result += f"\n{i+1}. {question[:30]}..."
            return result
            
        # 找到唯一匹配项，进行删除
        index = found_indices[0]
        deleted_question = self.question_bank.pop(index)
        
        # 保存题库
        self._save_question_bank()
        
        return f"题目已成功删除！已删除题目：{deleted_question['question']}"
        
    def get_question_bank_stats(self) -> str:
        """
        获取题库统计信息
        
        Returns:
            str: 题库统计信息
        """
        if not self.question_bank:
            return "题库为空！"
            
        total = len(self.question_bank)
        used = sum(1 for q in self.question_bank if q.get("used", 0) > 0)
        unused = total - used
        
        # 按类型统计
        multiple_choice = sum(1 for q in self.question_bank if q.get("type", "multiple_choice") == "multiple_choice")
        fill_blank = sum(1 for q in self.question_bank if q.get("type") == "fill_blank")
        
        # 按难度统计
        easy = sum(1 for q in self.question_bank if q.get("difficulty", "normal").lower() == "easy")
        normal = sum(1 for q in self.question_bank if q.get("difficulty", "normal").lower() == "normal")
        difficult = sum(1 for q in self.question_bank if q.get("difficulty", "normal").lower() == "difficult")
        
        result = f"天文竞答题库统计：\n"
        result += f"总题目数：{total} 题\n"
        result += f"已使用：{used} 题，未使用：{unused} 题\n\n"
        result += f"题目类型分布：\n"
        result += f"选择题：{multiple_choice} 题\n"
        result += f"填空题：{fill_blank} 题\n\n"
        result += f"题目难度分布：\n"
        result += f"简单题：{easy} 题\n"
        result += f"普通题：{normal} 题\n"
        result += f"困难题：{difficult} 题\n\n"
        
        # 显示前5个题目示例
        if total > 0:
            result += "题目示例：\n"
            for i, q in enumerate(self.question_bank[:5]):
                result += f"{i+1}. {q['question'][:30]}...\n"
            if total > 5:
                result += f"... 还有 {total - 5} 题未显示"
                
        return result

        
    def add_multiple_choice_question(self, question: str, options: List[str], correct_index: int) -> str:
        """
        添加选择题
        
        Args:
            question: 问题内容
            options: 选项列表
            correct_index: 正确答案的索引
            
        Returns:
            str: 添加结果信息
        """
        question_data = {
            "question": question,
            "type": "multiple_choice",
            "options": options,
            "correct": correct_index
        }
        
        return self.add_question(question_data)
        
    def add_fill_blank_question(self, question: str, answer: str) -> str:
        """
        添加填空题
        
        Args:
            question: 问题内容
            answer: 正确答案
            
        Returns:
            str: 添加结果信息
        """
        question_data = {
            "question": question,
            "type": "fill_blank",
            "answer": answer
        }
        
        return self.add_question(question_data)
        
    def delete_question(self, index: int) -> str:
        """
        删除指定索引的题目
        
        Args:
            index: 题目索引（从1开始）
            
        Returns:
            str: 删除结果信息
        """
        # 检查索引是否有效
        if not (1 <= index <= len(self.question_bank)):
            return f"❌ 错误：题目索引超出范围！有效范围: 1-{len(self.question_bank)}"
            
        # 获取要删除的题目信息
        question = self.question_bank[index - 1]["question"]
        
        # 删除题目
        del self.question_bank[index - 1]
        
        # 保存题库
        self._save_question_bank()
        
        return f"✅ 成功删除题目：'{question}'！当前题库共有 {len(self.question_bank)} 道题目。"
        
    def list_questions(self, page: int = 1, page_size: int = 10) -> str:
        """
        列出题库中的题目
        
        Args:
            page: 页码（从1开始）
            page_size: 每页题目数
            
        Returns:
            str: 题目列表信息
        """
        total_questions = len(self.question_bank)
        if total_questions == 0:
            return "📚 题库中暂无题目。"
            
        # 计算总页数
        total_pages = (total_questions + page_size - 1) // page_size
        
        # 验证页码
        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages
            
        # 计算当前页的题目范围
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, total_questions)
        
        # 构建题目列表信息
        result = f"📚 天文竞答题库（第 {page}/{total_pages} 页，共 {total_questions} 题）\n\n"
        
        for i in range(start_index, end_index):
            q = self.question_bank[i]
            q_type = q.get("type", "multiple_choice")
            used = q.get("used", 0)
            
            # 添加题目信息
            result += f"【{i+1}】{q['question']} "
            
            # 显示题目类型和状态
            if q_type == "multiple_choice":
                result += f"[选择题]"
            elif q_type == "fill_blank":
                result += f"[填空题]"
                
            if used > 0:
                result += f" (已使用)"
            else:
                result += f" (未使用)"
                
            result += "\n"
            
        # 添加翻页提示
        result += f"\n📝 查看其他页请使用：小天，天文题库 [页码]"
        
        return result
        
    def get_statistics(self, group_id: str = None) -> str:
        """
        获取竞答统计信息
        
        Args:
            group_id: 可选的群组ID，如果提供则返回该群的竞答信息
            
        Returns:
            str: 统计信息
        """
        # 如果指定了群组ID且该群有进行中的竞答
        if group_id and group_id in self.active_quizzes:
            quiz = self.active_quizzes[group_id]
            elapsed_time = (datetime.now() - quiz["start_time"]).total_seconds()
            remaining_time = max(0, quiz["duration"] - elapsed_time)
            
            correct_count = sum(1 for p in quiz["participants"].values() if p.get("correct", False))
            
            stats = (f"📊 天文竞答统计 (本群)\n"
                    f"⏱️ 状态：进行中，剩余时间 {remaining_time:.1f} 秒\n"
                    f"👥 已参与人数：{len(quiz['participants'])} 人\n"
                    f"✅ 已答对人数：{correct_count} 人\n"
                    f"📝 当前题目：{quiz['question']}")
        else:
            # 统计全局信息
            active_count = len(self.active_quizzes)
            top_users = sorted(self.user_scores.items(), key=lambda x: x[1]["points"], reverse=True)[:5]
            
            stats = (f"📊 天文竞答全局统计\n"
                   f"⏱️ 当前活跃竞答数：{active_count} 个\n"
                   f"📚 题库数量：{len(self.question_bank)} 题\n")
            
            if top_users:
                stats += "\n🏆 积分排行榜：\n"
                for i, (user_id, data) in enumerate(top_users):
                    stats += f"{i+1}. 用户 {user_id}：{data['points']} 分 (答对{data['correct']}题，答错{data['wrong']}题)\n"
            
        return stats
