"""
小天的调度器模块
负责定时任务和消息处理
"""

import os
import re
from datetime import datetime, timedelta
from threading import Thread
from typing import List, Callable, Tuple, Optional, Any, Dict
import time
import requests
import tempfile

from .manage.config import (
    DAILY_WEATHER_TIME, TRIGGER_WORDS,
    DAILY_ASTRONOMY_TIME, MONTHLY_ASTRONOMY_TIME, CLEANUP_TIME
)
from .ai.ai_core import XiaotianAI

from .tools.weather_tools import WeatherTools
from .tools.astronomy import AstronomyPoster
from .manage.root_manager import RootManager
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
        now = datetime.now()
        for task in self.tasks:
            if task['type'] == 'daily':
                task_time = now.replace(hour=task['hour'], minute=task['minute'], second=0, microsecond=0)
                
                # 如果当前时间已过任务时间，且今天还没运行过，且不是刚启动
                if (now >= task_time and 
                    (task['last_run'] is None or task['last_run'].date() < now.date()) and
                    task.get('initialized', False)):  # 防止启动时立即执行
                    try:
                        task['func']()
                        task['last_run'] = now
                    except Exception as e:
                        print(f"❌ 定时任务执行失败：{e}")
                
                # 标记任务已初始化
                if not task.get('initialized', False):
                    task['initialized'] = True


class XiaotianScheduler:
    def __init__(self, root_id: str = None, qq_send_callback=None, ai = None):
        # 初始化核心组件
        self.ai = ai
        self.weather_tools = WeatherTools()
        self.scheduler = SimpleScheduler()
        
        # 初始化新功能组件
        self.root_manager = RootManager(root_id=root_id)
        self.astronomy = AstronomyPoster(root_manager=self.root_manager)
        self.wait_for_wakeup = False
        self.last_user_id: str = None  # 最后一个用户ID
        self.last_group_id: str = None  # 最后一个群组ID

        # 设置QQ发送回调
        if qq_send_callback:
            self.root_manager.set_qq_callback(qq_send_callback)
        self.message_sender = MessageSender(self.root_manager, self.ai)
        
        self.is_running = False
        self.waiting_time = 10
        
        
    def start_scheduler(self):
        """启动调度器"""
        # 设置定时任务
        self.scheduler.daily_at(DAILY_WEATHER_TIME, self.weather_tools.daily_weather_task)
        self.scheduler.daily_at(DAILY_ASTRONOMY_TIME, self.astronomy.daily_astronomy_task)
        self.scheduler.daily_at(CLEANUP_TIME, self.daily_cleanup_task)
        
        # 设置月度任务 - 每月1号执行
        # 注意月度合集应该在1号生成上个月的合集
        self.scheduler.daily_at(MONTHLY_ASTRONOMY_TIME, self.astronomy.monthly_astronomy_task)

        self.is_running = True
        
        # 在后台线程中运行调度器
        def run_scheduler():
            while self.is_running:
                self.scheduler.run_pending()
                # 每20秒检查一次天文海报超时状态
                if self.astronomy.waiting_for_images:
                    last_time = time.time()
                    while self.astronomy.waiting_for_images and (last_time - time.time() < 70):
                        self._check_astronomy_timeout()
                        time.sleep(5)
                time.sleep(60)  # 每60秒检查一次

        scheduler_thread = Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print("🤖 小天调度器已启动...")
    
    def stop_scheduler(self):
        """停止调度器"""
        self.is_running = False
        print("🤖 小天调度器已停止")


    def process_message(self, user_id: str, message: str, group_id: str = None, image_data: bytes = None) -> tuple[str, str, str]:
        """处理用户消息"""
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
                        return result
                    elif command == "CHECK_LIKE_STATUS":
                        # 查看指定用户的like状态
                        status = self.ai.get_user_like_status(data)
                        direction_text = {
                            'positive': '正向(增强)',
                            'negative': '负向(恶劣)',
                            None: '原始'
                        }.get(status.get('last_change_direction'), '未知')
                        
                        # 获取当前like值的表情和态度
                        emoji, attitude = self.ai.get_like_emotion_and_attitude(status['total_like'])
                        
                        # 计算到下一个阈值的距离
                        current_like = status['total_like']
                        next_info = ""
                        if current_like >= 0:
                            # 正向：找下一个正向阈值
                            from xiaotian.manage.config import LIKE_THRESHOLDS, LIKE_PERSONALITY_CHANGE_THRESHOLD
                            for threshold in sorted(LIKE_THRESHOLDS + [LIKE_PERSONALITY_CHANGE_THRESHOLD]):
                                if threshold > current_like:
                                    gap = threshold - current_like
                                    next_info = f"距离下个里程碑({threshold:.2f})还差{gap:.2f}点"
                                    break
                        else:
                            # 负向：找下一个负向阈值
                            from xiaotian.manage.config import LIKE_THRESHOLDS, LIKE_RESET_THRESHOLD
                            current_abs = abs(current_like)
                            for threshold in sorted(LIKE_THRESHOLDS + [abs(LIKE_RESET_THRESHOLD)]):
                                if threshold > current_abs:
                                    gap = threshold - current_abs
                                    next_info = f"距离下个节点(-{threshold:.2f})还差{gap:.2f}点"
                                    break
                        
                        status_text = f"""📊 用户 {data} 的Like状态：
{emoji} 当前好感度：{status['total_like']:.2f}
💭 当前态度：{attitude}
🎭 性格状态：{direction_text}
⚡ 增长速度：{status.get('speed_multiplier', 1.0):.2f}x
� 性格变化次数：{status.get('personality_change_count', 0)}次
🎯 {next_info if next_info else "已达到最高/最低级别"}
📝 已通知阈值：{len(status.get('notified_thresholds', []))}个"""
                        return status_text
                    elif command == "RESET_ALL_LIKE_SYSTEMS":
                        # 重置所有用户的like系统
                        count = 0
                        for memory_key in list(self.ai.user_like_status.keys()):
                            self.ai.reset_user_like_system(memory_key)
                            count += 1
                        return f"✅ 已重置 {count} 个用户的like系统"
                    else:
                        # 返回普通Root命令结果
                        return command
            else:
                # 私聊中处理特殊指令 - 天文海报
                if message.startswith("小天，每日天文做好啦："):
                    # 否则就是普通天文内容处理
                    return self.astronomy._handle_astronomy_poster(message, user_id)

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
                                    return self.astronomy._handle_astronomy_image(user_id, image_path)
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

                            return f"🎨 海报制作成功！\n{response_message}"
                        else:
                            return f"⚠️ {response_message}"
                    
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
                            return self.astronomy._handle_astronomy_image(user_id, image_path)
                        except Exception as e:
                            print(f"处理用户图片失败: {e}")
                
                # 初始化content变量
                is_triggered = any(message.startswith(trigger) for trigger in TRIGGER_WORDS)
                
                if is_triggered:
                    for trigger in TRIGGER_WORDS:
                        if message.startswith(trigger):
                            parts = message.split(trigger, 1)
                            if len(parts) > 1 and len(parts[1]) > 0 and parts[1][0] in ".,!?;:，。！？；：":
                                content = ''.join(parts[1:]).strip()
                                break
                            else:
                                content = parts[1].strip()
                                break
                    response = self.ai.get_response(content, user_id=user_id, group_id=None)
                    return response
                return
        else:
            """处理普通聊天消息"""
        
        # 检测情绪并考虑自动触发
        emotion = self.ai.detect_emotion(message)
        should_auto_trigger = False
        
        # 添加调试信息，查看情绪检测结果
        print(f"消息情绪检测结果: {emotion}, 内容: {message[:20]}...")
        
        # 只在群聊中支持自动触发
        if group_id and (emotion == 'cold' or emotion == 'hot'):
            print(f"检测到可触发情绪: {emotion}")
            if self.root_manager.can_auto_trigger(group_id):
                should_auto_trigger = True
                self.root_manager.record_auto_trigger(group_id)
                print(f"将在群 {group_id} 自动触发响应")
            else:
                print(f"群 {group_id} 不满足自动触发条件")
        
        # 检查是否包含唤醒词或需要自动触发
        is_triggered = any(message.startswith(trigger) for trigger in TRIGGER_WORDS) or should_auto_trigger
        if is_triggered and not (self.wait_for_wakeup and self.last_user_id == user_id and self.last_group_id == group_id):
            # 提取唤醒词后的内容
            content = message
            if any(message.startswith(trigger) for trigger in TRIGGER_WORDS):
                for trigger in TRIGGER_WORDS:
                    if message == trigger:
                        content = trigger
                    elif message.startswith(trigger):
                        parts = message.split(trigger, 1)
                        if len(parts) > 1 and len(parts[1]) > 0 and parts[1][0] in ".,!?;:，。！？；：":
                            content = ''.join(parts[1:]).strip()
                            break
                        else:
                            content = parts[1].strip()
                            break
                self.scheduler.wait_for_wakeup = True

            # 如果是自动触发，生成合适的回复
            if should_auto_trigger and not any(trigger in message for trigger in TRIGGER_WORDS):
                if emotion == 'cold':
                    content = f"看起来有点冷淡呢，来聊聊天吧！原消息：{message}"
                elif emotion == 'hot':
                    content = f"感觉很激动呢，一起开心一下！原消息：{message}"
            
            # AI对话，传入群组信息以支持分别记忆
            # 在群聊中允许使用工具，在私聊中只能聊天
            use_tools = group_id is not None
            response = self.ai.get_response(content, user_id=user_id, group_id=group_id, use_tools=use_tools)
            return response
        elif self.last_user_id != user_id and self.last_group_id == group_id:
            self.waiting_time = 5
        return ""  # 未触发时返回空字符串

    def daily_cleanup_task(self):
        """每日数据清理任务"""
        print(f"🧹 {datetime.now().strftime('%H:%M')} - 执行每日数据清理任务")
        
        try:
            # 清理旧的天文海报数据
            self.astronomy.cleanup_old_data(days_to_keep=30)

            print("🧹 数据清理完成")
        except Exception as e:
            print(f"❌ 数据清理失败：{str(e)}")
    

