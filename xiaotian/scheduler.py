"""
小天的调度器模块
任务和消息处理
"""

import os
import re
from datetime import datetime as dt, datetime, timedelta
from threading import Thread
from typing import List, Callable, Tuple, Optional, Any, Dict
import time
import requests
import tempfile

from .manage.config import (
    DAILY_WEATHER_TIME, TRIGGER_WORDS,
    DAILY_ASTRONOMY_TIME, MONTHLY_ASTRONOMY_TIME, CLEANUP_TIME,
    MONTHLY_LIKE_REWARD_TIME, MAX_MEMORY_COUNT, MEMORY_FILE,
    DAILY_ASTRONOMY_MESSAGE
)
from .ai.ai_core import XiaotianAI

from .tools.weather_tools import WeatherTools
from .tools.astronomy import AstronomyPoster
from .tools.astronomy_quiz import AstronomyQuiz
from .tools.welcome import WelcomeManager
from .manage.root_manager import RootManager
from .manage.like_manager import LikeManager
from .tools.message import MessageSender


class SimpleScheduler:
    """定时任务调度器"""
    def __init__(self):
        self.tasks = []
        self.is_running = False
    
    def daily_at(self, time_str: str, func):
        """添加每日定时任务"""
        hour, minute = map(int, time_str.split(':'))
        self.tasks.append({
            'type': 'daily',
            'hour': hour,
            'minute': minute,
            'func': func,
            'last_run': None
        })
    
    def run_pending(self):
        """检查并执行待运行的任务"""
        now = dt.now()
        for task in self.tasks:
            if task['type'] == 'daily':
                task_time = now.replace(hour=task['hour'], minute=task['minute'], second=0, microsecond=0)
                
                # 如果当前时间已过任务时间，且今天还没运行过，且不是刚启动
                if (now >= task_time and 
                    (task['last_run'] is None or task['last_run'].date() < now.date()) and
                    task.get('initialized', False)):  # 防止启动时立即执行
                    try:
                        task_name = task['func'].__name__
                        print(f"⏰ {now.strftime('%H:%M:%S')} - 执行定时任务: {task_name}")
                        task['func']()
                        task['last_run'] = now
                        print(f"✅ {now.strftime('%H:%M:%S')} - 定时任务完成: {task_name}")
                    except Exception as e:
                        print(f"❌ 定时任务执行失败：{e}")
                        import traceback
                        print(traceback.format_exc())
                
                # 标记任务已初始化
                if not task.get('initialized', False):
                    task['initialized'] = True


class XiaotianScheduler:
    def __init__(self, root_id: str = None, qq_send_callback=None, ai = None):
        # 初始化核心组件
        self.ai = ai
        
        # 先初始化 RootManager，因为其他组件依赖它
        self.root_manager = RootManager(root_id=root_id)
        
        # 设置AI实例到RootManager
        if ai:
            self.root_manager.set_ai_instance(ai)
        
        # 然后初始化需要 RootManager 的组件
        self.weather_tools = WeatherTools(root_manager=self.root_manager)
        self.scheduler = SimpleScheduler()
        
        # 初始化新功能组件
        self.astronomy = AstronomyPoster(root_manager=self.root_manager)
        self.astronomy_quiz = AstronomyQuiz(root_manager=self.root_manager, ai_core=ai)  # 初始化天文竞答
        self.welcome_manager = WelcomeManager(root_manager=self.root_manager, ai=ai)  # 初始化欢迎管理器
        self.like_manager = LikeManager(root_manager=self.root_manager, ai=ai)  # 初始化好感度管理器
        self.wait_for_wakeup = False
        self.wakeup_time = 0  # 唤醒时间戳
        self.waiting_time = 20  # 默认唤醒超时时间（20秒）
        self.ai_response_time = 0  # AI回复等待时间累计
        self.last_user_id: str = None  # 最后一个用户ID
        self.last_group_id: str = None  # 最后一个群组ID

        # 设置QQ发送回调
        if qq_send_callback:
            self.root_manager.set_qq_callback(qq_send_callback)
        self.message_sender = MessageSender(self.root_manager, self.ai)
        
        self.is_running = False
        
    def add_response_wait_time(self, wait_seconds: float):
        """累加回复等待时间，用于唤醒状态超时计算"""
        if self.wait_for_wakeup:
            self.ai_response_time += wait_seconds
            print(f"⏱️ 累加等待时间: {wait_seconds:.2f}秒，总计: {self.ai_response_time:.2f}秒")
        
    def _check_special_user_commands(self, user_id: str, message: str, group_id: str = None) -> Optional[str]:
        """检查用户特殊提示词命令"""
        memory_key = self.ai._get_memory_key(user_id, group_id)
        
        # 检查天文竞答命令
        if message.strip().startswith("小天 天文竞答") and group_id:
            # 只在群聊中开启竞答
            question_count = 10  # 默认题目数量
            
            # 检查是否有指定题目数量
            match = re.search(r"小天 天文竞答\s*(\d+)?", message.strip())
            if match and match.group(1):
                try:
                    count = int(match.group(1))
                    if 3 <= count <= 50:  # 限制范围在3-50之间
                        question_count = count
                    else:
                        return f'{{"data": [{{"wait_time": 1, "content": "⚠️ 题目数量必须在3-50之间！将使用默认数量10题。"}}], "like": 0}}'
                except ValueError:
                    pass  # 解析失败，使用默认值
                    
            # 获取开始提示和第一题
            result, message = self.astronomy_quiz.start_quiz(group_id, question_count)
            if message:
                # 分开发送这两条消息，中间延迟4秒
                return f'{{"data": [{{"wait_time": 1, "content": "{result}"}}, {{"wait_time": 3, "content": "{message}"}}], "like": 0}}'
            return f'{{"data": [{{"wait_time": 3, "content": "{result}"}}], "like": 0}}'
            
        # 检查是否是竞答结束命令
        if message.strip() in ["结算", "结束竞答"] and group_id and group_id in self.astronomy_quiz.active_quizzes:
            result1, result2 = self.astronomy_quiz.finish_quiz(group_id, user_id)
            # 分开发送结束通知和结果详情，中间延迟4秒
            if result2:
                return f'{{"data": [{{"wait_time": 3, "content": "{result1}"}}, {{"wait_time": 4, "content": "{result2}"}}], "like": 0}}'
            else:
                return f'{{"data": [{{"wait_time": 3, "content": "{result1}"}}], "like": 0}}'
            
        # 检查群组是否处于竞答模式，如果是则将所有消息视为答案
        if group_id and group_id in self.astronomy_quiz.active_quizzes:
            response, next_question = self.astronomy_quiz.process_answer(user_id, message, group_id)
            if response and next_question:
                # 分开发送答题反馈和下一题目，中间延迟4秒
                return f'{{"data": [{{"wait_time": 3, "content": "{response}"}}, {{"wait_time": 4, "content": "{next_question}"}}], "like": 0}}'
            elif response:
                return f'{{"data": [{{"wait_time": 3, "content": "{response}"}}], "like": 0}}'
                    
        # 检查更改性格命令
        if message.startswith("小天，更改性格"):
            # 检查用户like值是否达到条件
            user_like_status = self.ai.get_user_like_status(self.ai._extract_user_id_from_memory_key(memory_key))
            current_like = user_like_status['total_like']
            
            if abs(current_like) < 150:
                return f'{{"wait_time": 3, "content": "❌ 更改性格需要like值达到150或低于-150！\\n你当前的like值：{current_like:.2f}"}}'
            
            # 提取新性格描述
            if len(message) > 7:  # "小天，更改性格" 长度为7
                new_personality = message[7:].strip()
                if new_personality:
                    # 调用AI的性格更改工具
                    result = self.ai.generate_custom_personality(new_personality, memory_key)
                    return f'{"wait_time": 3, "content": "🎭 {result}"}'
                else:
                    return '{"wait_time": 3, "content": "❌ 请提供新的性格描述，例如：小天，更改性格活泼开朗"}'
            else:
                return '{"wait_time": 3, "content": "❌ 请提供新的性格描述，例如：小天，更改性格活泼开朗"}'
        
        # 检查回到最初性格命令
        elif message.strip() == "小天，回到最初的性格":
            # 检查用户like值是否达到条件
            user_like_status = self.ai.get_user_like_status(self.ai._extract_user_id_from_memory_key(memory_key))
            current_like = user_like_status['total_like']
            
            if abs(current_like) < 150:
                return f'{{"wait_time": 3, "content": "❌ 回到最初性格需要like值达到150或低于-150！\\n你当前的like值：{current_like:.2f}"}}'
            
            # 调用AI的恢复性格工具
            result = self.ai.restore_original_personality(memory_key)
            return f'{{"wait_time": 3, "content": "🔄 {result}"}}'
        
        # 检查对冲like值命令
        elif message.startswith("小天，与") and ("对冲" in message):
            # 提取目标用户ID和对冲金额
            try:
                # 首先尝试匹配CQ码格式的@用户 - [CQ:at,qq=123456789]
                at_match = re.search(r'小天，与\s*\[CQ:at,qq=(\d+)\]\s*对冲\s*([0-9.]+)', message)
                if at_match:
                    # 直接从CQ码中提取QQ号
                    target_user_id = at_match.group(1).strip()
                    transfer_amount = float(at_match.group(2).strip())
                    
                    if target_user_id and transfer_amount > 0:
                        # 调用AI的like值转移功能（指定金额）
                        result = self.ai.transfer_like_value(memory_key, target_user_id, transfer_amount, group_id)
                        return f'{{"wait_time": 3, "content": "{result}"}}'
                    else:
                        return '{"wait_time": 3, "content": "❌ 请提供有效的用户和对冲金额"}'
                
                # 如果不是@格式，继续支持原有的QQ号格式
                match = re.search(r'小天，与\s*([^\s]+)\s*对冲\s*([0-9.]+)', message)
                if match:
                    target_partial_id = match.group(1).strip()
                    transfer_amount = float(match.group(2).strip())
                    if target_partial_id and transfer_amount > 0:
                        # 调用AI的like值转移功能（指定金额）
                        result = self.ai.transfer_like_value(memory_key, target_partial_id, transfer_amount, group_id)
                        return f'{{"wait_time": 3, "content": "{result}"}}'
                    else:
                        return '{"wait_time": 3, "content": "❌ 请提供有效的QQ号和对冲金额"}'
                else:
                    return '{"wait_time": 3, "content": "❌ 命令格式错误，请使用：小天，与[@用户]对冲[金额] 或 小天，与[QQ号]对冲[金额]"}'
            except ValueError:
                return '{"wait_time": 3, "content": "❌ 对冲金额必须是数字"}'
            except Exception as e:
                print(f"处理对冲like值命令时发生错误: {e}")
                return '{"wait_time": 3, "content": "❌ 处理命令时发生错误，请稍后重试"}'
        
        return None
        
        
    def start_scheduler(self):
        """启动调度器"""
        # 设置定时任务
        self.scheduler.daily_at(DAILY_WEATHER_TIME, self.weather_tools.daily_weather_task)
        self.scheduler.daily_at(DAILY_ASTRONOMY_TIME, self.astronomy.daily_astronomy_task)
        self.scheduler.daily_at(CLEANUP_TIME, self.daily_cleanup_task)
        
        # 设置月度任务 - 每月1号执行
        # 注意月度合集应该在1号生成上个月的合集
        self.scheduler.daily_at(MONTHLY_ASTRONOMY_TIME, self.astronomy.monthly_astronomy_task)
        
        self.scheduler.daily_at(MONTHLY_LIKE_REWARD_TIME, self.monthly_like_reward_task)

        self.is_running = True
        
        # 在后台线程中运行调度器
        def run_scheduler():
            while self.is_running:
                self.scheduler.run_pending()
                
                # 每5秒检查一次天文海报超时状态
                if self.astronomy.waiting_for_images:
                    last_time = time.time()
                    while self.astronomy.waiting_for_images and (time.time() - last_time < 70):
                        self._check_astronomy_timeout()
                        time.sleep(5)
                
                # 检查是否有活跃的天文竞答
                if hasattr(self, 'astronomy_quiz') and self.astronomy_quiz and self.astronomy_quiz.active_quizzes:
                    # 有活跃竞答，进入频繁检查循环
                    for _ in range(20):  # 20次循环，每次3秒，共60秒
                        time.sleep(3)  # 每3秒检查一次
                        
                        # 检查是否还有活跃竞答
                        if not self.astronomy_quiz.active_quizzes:
                            break
                            
                        # 检查每个活跃竞答的超时
                        for group_id, quiz in list(self.astronomy_quiz.active_quizzes.items()):
                            if quiz and not quiz.get("participants"):  # 只在没人回答时检查超时
                                current_time = datetime.now()
                                if "start_time" in quiz and (current_time - quiz["start_time"]).total_seconds() > quiz["duration"]:
                                    # 如果当前题目已超时，处理超时
                                    result_msg1, result_msg2 = self.astronomy_quiz.handle_question_timeout(group_id)
                                    if self.root_manager.settings.get('qq_send_callback'):
                                        try:
                                            # 先发送超时通知
                                            if result_msg1:
                                                self.root_manager.settings['qq_send_callback']('group', group_id, result_msg1, None)
                                            
                                            # 延迟5秒后发送下一题或结果
                                            if result_msg2:
                                                time.sleep(5)
                                                self.root_manager.settings['qq_send_callback']('group', group_id, result_msg2, None)
                                        except Exception as e:
                                            print(f"发送题目超时消息失败: {e}")
                else:
                    # 没有活跃竞答，直接睡眠60秒
                    time.sleep(60)

        scheduler_thread = Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print("🤖 小天调度器已启动...")
    
    def stop_scheduler(self):
        """停止调度器"""
        self.is_running = False
        print("🤖 小天调度器已停止")


    def process_message(self, user_id: str, message: str, group_id: str = None, image_data: bytes = None) -> tuple[str, str, str]:
        """处理用户消息"""
        
        # 检查唤醒状态是否超时
        current_time = time.time()
        if self.wait_for_wakeup and (current_time - self.wakeup_time - self.ai_response_time) > self.waiting_time:
            self.wait_for_wakeup = False
            self.ai_response_time = 0  # 重置AI回复时间累计
            print(f"唤醒状态超时，已自动关闭")
        
        # 检查用户特殊提示词
        special_command_result = self._check_special_user_commands(user_id, message, group_id)
        if special_command_result:
            return special_command_result
            
        # 快速路径：检查是否是唤醒状态中的同一用户
        is_wakeup_continue = (self.wait_for_wakeup and 
                             self.last_user_id == user_id and 
                             self.last_group_id == group_id)
        
        # 快速路径：检查是否包含唤醒词（优化：避免重复检测）
        has_trigger_word = False
        trigger_word_used = None
        for trigger in TRIGGER_WORDS:
            if message.startswith(trigger):
                has_trigger_word = True
                trigger_word_used = trigger
                break
        # 私聊消息的处理
        if group_id is None:
            # 私聊中只处理Root命令和"每日天文"命令
            if self.root_manager.is_root(user_id):
                root_result = self.root_manager.process_root_command(user_id, message, group_id, image_data)
                if root_result:
                    command, data = root_result
                    # 处理特殊Root命令
                    if command == "SEND_WEATHER":
                        self.weather_tools.daily_weather_task()
                        return "✅ 天气报告已发送"
                    elif command == "SEND_ASTRONOMY":
                        self.astronomy.daily_astronomy_task()
                        return "✅ 天文海报已发送"
                    elif command == "GENERATE_MONTHLY":
                        self.astronomy.monthly_astronomy_task()
                        return "✅ 月度合集已生成"
                    elif command == "CLEANUP_NOW":
                        self.daily_cleanup_task()
                        return "✅ 清理任务已执行"
                    elif command == "RESET_LIKE_SYSTEM":
                        # 重置指定用户的like系统
                        result = self.ai.reset_user_like_system(data)
                        return f'{{"wait_time": 3, "content": "{result}"}}'
                    
                    elif command == "RESET_ALL_LIKE_SYSTEMS":
                        # 重置所有用户的like系统
                        count = 0
                        for memory_key in list(self.ai.user_like_status.keys()):
                            self.ai.reset_user_like_system(memory_key)
                            count += 1
                        return f'{{"wait_time": 3, "content": "✅ 已重置 {count} 个用户的like系统"}}'
                    else:
                        # 返回普通Root命令结果
                        return f'{{"wait_time": 3, "content": "{command}"}}'
            else:
                # 私聊中处理特殊指令 - 天文海报
                if message.startswith("小天，每日天文做好啦："):
                    # 否则就是普通天文内容处理
                    result = self.astronomy._handle_astronomy_poster(message, user_id)
                    return f'{{"wait_time": 3, "content": "{result}"}}'

                # 检查是否是给天文海报添加图片的消息
                if self.astronomy.waiting_for_images:
                    # 检测CQ图片码
                    if "[CQ:image" in message:
                        print(f"检测到用户 {user_id} 发送了图片CQ码: {message[:100]}...")
                        # 从CQ码中提取图片URL
                        url_match = re.search(r'url=(https?://[^,\]]+)', message)
                        if url_match:
                            image_url = url_match.group(1)
                            image_url = image_url.replace("&amp;", "&")  # 解码HTML实体
                            print(f"从CQ码中提取到图片URL: {image_url}")
                            
                            # 下载图片
                            try:
                                response = requests.get(image_url, timeout=10)
                                if response.status_code == 200:
                                    # 保存到临时文件
                                    temp_dir = tempfile.gettempdir()
                                    image_path = os.path.join(temp_dir, f"astronomy_user_image_{user_id}_{int(time.time())}.jpg")
                                    
                                    with open(image_path, 'wb') as f:
                                        f.write(response.content)
                                    print(f"已下载并保存用户图片到: {image_path}")
                                    
                                    # 处理用户消息和图片
                                    result = self.astronomy._handle_astronomy_image(user_id, image_path)
                                    return f'{{"wait_time": 3, "content": "{result}"}}'
                                else:
                                    print(f"图片下载失败，状态码: {response.status_code}")
                            except Exception as e:
                                import traceback
                                print(f"处理CQ图片失败: {e}")
                                print(traceback.format_exc())
                    
                    # 处理"立即生成"或"不需要图片"等指令
                    elif "不需要图片" in message or "立即生成" in message or "直接生成" in message:
                        print(f"用户 {user_id} 请求立即生成海报: {message}")
                        # 调用天文海报模块处理用户指令
                        poster_path, response_message = self.astronomy.process_user_message(message, None)
                        if poster_path:
                            # 保存最近的海报路径和消息，供定时任务使用
                            self.astronomy.last_astronomy_post = (poster_path, DAILY_ASTRONOMY_MESSAGE)

                            # 向发送天文内容的用户直接回复海报
                            if self.root_manager.settings['qq_send_callback']:
                                try:
                                    print(f"尝试向用户 {user_id} 发送立即生成的天文海报")
                                    self.root_manager.settings['qq_send_callback']('private', user_id, None, poster_path)
                                    time.sleep(2)  # 短暂延时
                                    self.root_manager.settings['qq_send_callback']('private', user_id, f"🌌 天文海报已生成！\n\n{response_message}", None)
                                    print(f"已向用户 {user_id} 发送立即生成的天文海报")
                                except Exception as send_err:
                                    print(f"向用户发送立即生成的天文海报失败: {send_err}")

                            return f'{{"wait_time": 3, "content": "🎨 海报制作成功！\\n{response_message}"}}'
                        else:
                            return f'{{"wait_time": 3, "content": "⚠️ {response_message}"}}'
                    
                    # 处理常规图片数据
                    elif image_data:
                        print(f"用户 {user_id} 正在为天文海报添加图片...")
                        temp_dir = tempfile.gettempdir()
                        image_path = os.path.join(temp_dir, f"astronomy_user_image_{user_id}_{int(time.time())}.jpg")
                        try:
                            with open(image_path, 'wb') as f:
                                f.write(image_data)
                            print(f"已保存用户图片到: {image_path}")
                            
                            # 处理用户消息和图片
                            result = self.astronomy._handle_astronomy_image(user_id, image_path)
                            return f'{{"wait_time": 3, "content": "{result}"}}'
                        except Exception as e:
                            print(f"处理用户图片失败: {e}")
                
                # root用户私聊正常聊天功能 - 但优先检查是否是root命令
                is_triggered = any(message.startswith(trigger) for trigger in TRIGGER_WORDS)
                
                if is_triggered:
                    # 先检查这是否是一个root命令
                    if self.root_manager.is_root(user_id):
                        # 对于root用户，再次尝试处理命令
                        root_result = self.root_manager.process_root_command(user_id, message, None, image_data)
                        if root_result:
                            command, data = root_result
                            return f'{{"wait_time": 3, "content": "{command}"}}'
                    
                    # 如果不是root命令，或者不是root用户，则当作普通聊天
                    for trigger in TRIGGER_WORDS:
                        if message.startswith(trigger):
                            parts = message.split(trigger, 1)
                            if len(parts) > 1 and len(parts[1]) > 0 and parts[1][0] in ".,!?;:，。！？；：":
                                content = ''.join(parts[1:]).strip()
                                break
                            else:
                                content = parts[1].strip()
                                break
                    
                    # 只有root用户可以私聊
                    if self.root_manager.is_root(user_id):
                        response = self.ai.get_response(content, user_id=user_id, group_id=None)
                        return response
                
                # 非root用户私聊需要唤醒词
                return f'{{"data": [{{"wait_time": 0, "content": ""}}], "like": 0}}'
        else:
            """处理普通聊天消息"""
        
        # 检测情绪并考虑自动触发（仅在群聊中）
        should_auto_trigger = False
        if group_id:
            emotion = self.ai.detect_emotion(message)
            if emotion in ('cold', 'hot'):
                # if self.root_manager.can_auto_trigger(group_id):
                should_auto_trigger = True
                self.root_manager.record_auto_trigger(group_id)
                print(f"群 {group_id} 自动触发响应，情绪: {emotion}")
        else:
            emotion = None
        
        # 检查是否包含唤醒词或需要自动触发，或者是在唤醒状态中的后续对话
        is_triggered = (has_trigger_word or 
                       should_auto_trigger or 
                       is_wakeup_continue)
        
        if is_triggered:
            # 提取唤醒词后的内容
            content = message
            if has_trigger_word:
                # 使用已找到的触发词
                trigger = trigger_word_used
                if message == trigger:
                    content = trigger
                elif message.startswith(trigger):
                    parts = message.split(trigger, 1)
                    if len(parts) > 1 and len(parts[1]) > 0 and parts[1][0] in ".,!?;:，。！？；：":
                        content = ''.join(parts[1:]).strip()
                    else:
                        content = parts[1].strip()
                # 设置唤醒状态，持续一段时间
                self.wait_for_wakeup = True
                self.wakeup_time = time.time()  # 记录唤醒时间
                self.ai_response_time = 0  # 重置AI回复时间累计
                self.waiting_time = 25  # 重置为25秒
                print(f"用户 {user_id} 唤醒了小天，超时时间: {self.waiting_time}秒")
            elif is_wakeup_continue:
                # 唤醒状态中的后续对话
                if self.last_user_id == user_id and self.last_group_id == group_id:
                    # 同一用户继续发消息，重新计时
                    self.wakeup_time = time.time()
                    self.ai_response_time = 0  # 重置AI回复时间累计
                    self.waiting_time = 15  # 重置为15秒
                    print(f"用户 {user_id} 继续对话，重新计时: {self.waiting_time}秒")

            # 如果是自动触发，生成合适的回复
            if should_auto_trigger and not has_trigger_word:
                if emotion == 'cold':
                    content = f"看起来有点冷淡呢，来聊聊天吧！原消息：{message}"
                elif emotion == 'hot':
                    content = f"感觉很激动呢，一起开心一下！原消息：{message}"
            
            # 更新最后交互的用户信息
            self.last_user_id = user_id
            self.last_group_id = group_id
            
            # AI对话，传入群组信息以支持分别记忆
            # 在群聊中允许使用工具，在私聊中只能聊天
            use_tools = group_id is not None
            
            # 记录AI响应开始时间
            ai_start_time = time.time()
            response = self.ai.get_response(content, user_id=user_id, group_id=group_id, use_tools=use_tools)
            ai_end_time = time.time()
            
            # 累计AI回复等待时间
            ai_duration = ai_end_time - ai_start_time
            self.ai_response_time += ai_duration
            print(f"AI回复耗时: {ai_duration:.2f}秒，累计: {self.ai_response_time:.2f}秒")
            
            return response
        elif self.wait_for_wakeup and self.last_group_id == group_id and self.last_user_id != user_id:
            # 在唤醒状态中，其他用户发消息，缩短超时时间到5秒
            self.waiting_time = 5
            print(f"其他用户 {user_id} 在群 {group_id} 发消息，缩短超时时间到 {self.waiting_time}秒")
            
        return f'{{"data": [{{"wait_time": 0, "content": ""}}], "like": 0}}'  # 未触发时返回空字符串

    def daily_cleanup_task(self):
        """每日数据清理任务"""
        print(f"🧹 {dt.now().strftime('%H:%M')} - 执行每日数据清理任务")
        
        try:
            # 清理旧的天文海报数据
            self.astronomy.cleanup_old_data(days_to_keep=30)
            
            # 清理临时管理员
            temp_admin_count = self.root_manager.clear_temp_admins()
            print(f"🧹 已清理临时管理员：{temp_admin_count}人")
            
            # 清理过多的用户记忆
            memory_cleaned = 0
            if self.ai and hasattr(self.ai, 'memory_storage'):
                # 确保每个用户的记忆不超过MAX_MEMORY_COUNT
                for memory_key, memories in self.ai.memory_storage.items():
                    if len(memories) > MAX_MEMORY_COUNT:
                        # 保留最新的MAX_MEMORY_COUNT条记忆
                        original_count = len(memories)
                        self.ai.memory_storage[memory_key] = memories[-MAX_MEMORY_COUNT:]
                        memory_cleaned += (original_count - len(self.ai.memory_storage[memory_key]))
                
                # 保存清理后的记忆
                self.ai.save_memory(MEMORY_FILE)
                print(f"🧹 已清理过多的用户记忆：{memory_cleaned}条")
            
            print("🧹 数据清理完成")
        except Exception as e:
            print(f"❌ 数据清理失败：{str(e)}")
    
    def monthly_like_reward_task(self):
        """月度好感度奖励发放任务（每月1号执行）"""
        # 只在每月1号执行
        if dt.now().day != 1:
            return
            
        print(f"🏆 {dt.now().strftime('%Y-%m-%d %H:%M')} - 执行月度好感度奖励任务 - 执行月度好感度重置任务")
        
        try:
            # 重置所有用户的好感度
            result = self.like_manager.reset_all_likes()
        
            # 发送结果给root管理员 - 安全检查settings字典中的键是否存在
            if (self.root_manager and hasattr(self.root_manager, 'settings') and
                isinstance(self.root_manager.settings, dict) and
                self.root_manager.settings.get('qq_send_callback')):
                
                root_id = os.getenv("NCATBOT_ADMIN")
                message = f"⏱️ 月度好感度重置任务执行结果：\n{result}"
                try:
                    self.root_manager.settings['qq_send_callback']('private', root_id, message, None)
                    print(f"已发送好感度重置结果给root管理员 {root_id}")
                except Exception as e:
                    print(f"发送好感度重置结果失败: {e}")
            else:
                print("⚠️ 无法发送好感度重置结果：未设置qq_send_callback")
            print("📊 月度好感度重置完成")
            
            # 计算月度好感度奖励名单
            winners, result_message = self.like_manager.calculate_monthly_rewards()
            
            # 向目标群组发送获奖名单 - 安全检查settings字典中的键是否存在
            if winners and self.root_manager and hasattr(self.root_manager, 'settings'):
                target_groups = self.root_manager.settings.get('target_groups', [])
                qq_send_callback = self.root_manager.settings.get('qq_send_callback')
                
                if target_groups and qq_send_callback:
                    for group_id in target_groups:
                        try:
                            # 发送获奖消息到群组
                            public_message = (f"🌟 上个月好感度排行榜出炉啦！\n\n{result_message}\n\n"
                                             f"🎁 获奖用户请前往摊位或私聊小天领取可爱文创奖励喵~")
                            qq_send_callback('group', group_id, public_message, None)
                            print(f"已发送好感度奖励名单到群组 {group_id}")
                        except Exception as e:
                            print(f"发送好感度奖励名单到群组 {group_id} 失败: {e}")
                else:
                    print("⚠️ 无法发送好感度奖励名单：未设置target_groups或qq_send_callback")
                    
            print("🏆 月度好感度奖励任务完成")
        except Exception as e:
            print(f"❌ 月度好感度奖励任务和重置失败：{str(e)}")
            

