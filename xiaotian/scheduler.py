"""
小天的调度器模块
负责定时任务和消息处理
"""

import asyncio
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
    def __init__(self, root_id: str = None, qq_send_callback=None):
        # 初始化核心组件
        self.ai = XiaotianAI()
        self.weather_tools = WeatherTools()
        self.scheduler = SimpleScheduler()
        
        # 初始化新功能组件
        self.root_manager = RootManager(root_id=root_id)
        self.astronomy = AstronomyPoster(root_manager=self.root_manager)
        
        # 设置QQ发送回调
        if qq_send_callback:
            self.root_manager.set_qq_callback(qq_send_callback)
        self.message_sender = MessageSender(self.root_manager, self.ai)
        
        self.is_running = False
        
        
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
                # 每70秒检查一次天文海报超时状态
                self._check_astronomy_timeout()
                time.sleep(70)  # 每70秒检查一次

        scheduler_thread = Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print("🤖 小天调度器已启动...")
    
    def stop_scheduler(self):
        """停止调度器"""
        self.is_running = False
        print("🤖 小天调度器已停止")
    
    
    def process_message(self, user_id: str, message: str, group_id: str = None, image_data: bytes = None) -> str:
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
                        import re
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
            return self.message_sender._handle_chat(user_id, message, group_id)

    def daily_cleanup_task(self):
        """每日数据清理任务"""
        print(f"🧹 {datetime.now().strftime('%H:%M')} - 执行每日数据清理任务")
        
        try:
            # 清理旧的天文海报数据
            self.astronomy.cleanup_old_data(days_to_keep=30)

            print("🧹 数据清理完成")
        except Exception as e:
            print(f"❌ 数据清理失败：{str(e)}")
    

