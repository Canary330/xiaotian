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

from .config import (
    DAILY_WEATHER_TIME, DAILY_STATS_TIME, TRIGGER_WORDS,
    DAILY_ASTRONOMY_TIME, MONTHLY_ASTRONOMY_TIME, CLEANUP_TIME
)
from .ai_core import XiaotianAI
from .tools import XiaotianTools
from .message_stats import MessageStats
from .astronomy import AstronomyPoster
from .wordstats import WordFrequencyAnalyzer
from .admin import AdminTools
from .root_manager import RootManager
from .utils.ai_utils import AIUtils


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
        self.tools = XiaotianTools()
        self.stats = MessageStats()
        self.scheduler = SimpleScheduler()
        
        # 初始化新功能组件
        self.astronomy = AstronomyPoster()
        self.word_analyzer = WordFrequencyAnalyzer()
        self.ai_utils = AIUtils(ai_core=self.ai)
        self.admin = AdminTools(root_id=root_id)
        self.root_manager = RootManager(root_id=root_id)
        
        # 设置QQ发送回调
        if qq_send_callback:
            self.root_manager.set_qq_callback(qq_send_callback)
        
        self.is_running = False
        
        # 储存最近一次处理的天文文本和图片路径
        self.last_astronomy_post = None
        self.last_wordstats_chart = None
        
    def start_scheduler(self):
        """启动调度器"""
        # 设置定时任务
        self.scheduler.daily_at(DAILY_WEATHER_TIME, self.daily_weather_task)
        # self.scheduler.daily_at(DAILY_STATS_TIME, self.daily_stats_task)
        # self.scheduler.daily_at(DAILY_STATS_TIME, self.daily_wordstats_task)  # 添加词频统计任务，与统计任务同时执行
        self.scheduler.daily_at(DAILY_ASTRONOMY_TIME, self.daily_astronomy_task)
        self.scheduler.daily_at(CLEANUP_TIME, self.daily_cleanup_task)
        
        # 设置月度任务 - 每月1号执行
        # 注意月度合集应该在1号生成上个月的合集
        self.scheduler.daily_at(MONTHLY_ASTRONOMY_TIME, self.monthly_astronomy_task)
        
        self.is_running = True
        
        # 在后台线程中运行调度器
        def run_scheduler():
            while self.is_running:
                self.scheduler.run_pending()
                # 每10秒检查一次天文海报超时状态
                self._check_astronomy_timeout()
                time.sleep(10)  # 每10秒检查一次
                time.sleep(60)  # 每分钟检查一次
        
        scheduler_thread = Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print("🤖 小天调度器已启动...")
    
    def stop_scheduler(self):
        """停止调度器"""
        self.is_running = False
        print("🤖 小天调度器已停止")
    
    def daily_weather_task(self):
        """每日天气任务"""
        if not self.root_manager.is_feature_enabled('daily_weather'):
            return
            
        print(f"🌤️ {datetime.now().strftime('%H:%M')} - 执行每日天气任务")
        
        # 获取天气信息
        city = self.root_manager.get_weather_city()
        weather_info = self.tools.get_weather_info(city)
        
        if "error" not in weather_info:
            # 生成天气报告
            weather_report = self._format_weather_report(weather_info)
            print(f"📢 天气播报：\n{weather_report}")
            
            # 发送到目标群组
            target_groups = self.root_manager.get_target_groups()
            if target_groups:
                self.root_manager.send_message_to_groups(weather_report)
            else:
                print("⚠️ 没有设置目标群组，天气报告未发送。请使用命令'小天，设置目标群组：群号1,群号2'来设置目标群组。")
        else:
            print(f"❌ 天气获取失败：{weather_info['error']}")
    
    def daily_stats_task(self):
        """每日统计任务"""
        if not self.root_manager.is_feature_enabled('daily_stats'):
            return
            
        print(f"📊 {datetime.now().strftime('%H:%M')} - 执行每日统计任务")
        
        # 生成统计报告
        stats_report = self.stats.generate_daily_report()
        print(f"📢 统计报告：\n{stats_report}")
        
        # 生成统计图表
        daily_stats = self.stats.get_daily_stats(7)
        chart_path = None
        if daily_stats:
            chart_result = self.tools.create_stats_chart(daily_stats, "line")
            print(f"📈 图表结果：{chart_result}")
            
            # 处理返回结果，提取实际路径
            if isinstance(chart_result, str):
                if "：" in chart_result:  # 如果包含中文冒号，说明是描述信息，需要提取路径
                    chart_path = chart_result.split("：")[-1].strip()
                else:
                    chart_path = chart_result
                    
            print(f"📈 实际使用的图表路径：{chart_path}")
        
        # 如果chart_path是一个文本文件，尝试读取其内容并附加到消息中
        chart_content = ""
        if chart_path and chart_path.endswith(".txt") and os.path.exists(chart_path):
            try:
                with open(chart_path, 'r', encoding='utf-8') as f:
                    chart_content = f"\n\n📊 统计图表：\n{f.read()}"
                print("已读取文本图表内容并附加到消息")
                # 由于是文本图表，不作为图片发送
                chart_path = None
            except Exception as e:
                print(f"读取图表文件失败: {e}")
                
                
        # 发送到目标群组
        target_groups = self.root_manager.get_target_groups()
        if target_groups:
            self.root_manager.send_message_to_groups(stats_report + chart_content, chart_path)
        else:
            print("⚠️ 没有设置目标群组，统计报告未发送。请使用命令'小天，设置目标群组：群号1,群号2'来设置目标群组。")
    
    def _format_weather_report(self, weather_info: dict) -> str:
        """格式化天气报告"""
        # 检查是否有错误信息
        if 'error' in weather_info:
            return f"🌤️ 天气预报服务暂时不可用\n\n{weather_info.get('error', '无法获取天气数据')}\n\n稍后再试喵~"
            
        return f"""🌤️ 今晚观星天气预报

📍 地点：{weather_info['location']}
🌡️ 温度：{weather_info['temperature']}°C
☁️ 天气：{weather_info['weather']}
💧 湿度：{weather_info['humidity']}%
💨 风速：{weather_info['wind_speed']}km/h
👁️ 能见度：{weather_info['visibility']}

{weather_info['stargazing_advice']}

🔭 喵喵喵！"""
    
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
                        self.daily_weather_task()
                        return "✅ 天气报告已发送"
                    elif command == "SEND_STATS":
                        self.daily_stats_task()
                        time.sleep(1)
                        self.daily_wordstats_task()
                        return "✅ 统计报告已发送"
                    elif command == "SEND_ASTRONOMY":
                        self.daily_astronomy_task()
                        return "✅ 天文海报已发送"
                    elif command == "GENERATE_MONTHLY":
                        self.monthly_astronomy_task()
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
                    return self._handle_astronomy_poster(message, user_id)
                
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
                                import requests
                                import tempfile
                                
                                response = requests.get(image_url, timeout=10)
                                if response.status_code == 200:
                                    # 保存到临时文件
                                    temp_dir = tempfile.gettempdir()
                                    image_path = os.path.join(temp_dir, f"astronomy_user_image_{user_id}_{int(time.time())}.jpg")
                                    
                                    with open(image_path, 'wb') as f:
                                        f.write(response.content)
                                    print(f"已下载并保存用户图片到: {image_path}")
                                    
                                    # 处理用户消息和图片
                                    return self._handle_astronomy_image(user_id, image_path)
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
                            self.last_astronomy_post = (poster_path, "今天的每日天文来啦")
                            
                            # 向发送天文内容的用户直接回复海报
                            if self.root_manager.settings['qq_send_callback']:
                                try:
                                    print(f"尝试向用户 {user_id} 发送立即生成的天文海报")
                                    self.root_manager.settings['qq_send_callback']('private', user_id, None, poster_path)
                                    time.sleep(1)  # 短暂延时
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
                        # 保存图片到临时文件
                        import tempfile
                        temp_dir = tempfile.gettempdir()
                        image_path = os.path.join(temp_dir, f"astronomy_user_image_{user_id}_{int(time.time())}.jpg")
                        try:
                            with open(image_path, 'wb') as f:
                                f.write(image_data)
                            print(f"已保存用户图片到: {image_path}")
                            
                            # 处理用户消息和图片
                            return self._handle_astronomy_image(user_id, image_path)
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
            return self._handle_chat(user_id, message, group_id)
        
    def _handle_chat(self, user_id: str, message: str, group_id: str = None) -> str:
        """处理普通聊天消息"""
        # 记录词频统计
        self.word_analyzer.add_message(message)
        
        # 记录消息统计（非AI触发）
        self.stats.record_message(user_id, message, False)
        
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
        
        if is_triggered:
            # 提取唤醒词后的内容
            content = message
            if any(message.startswith(trigger) for trigger in TRIGGER_WORDS):
                for trigger in TRIGGER_WORDS:
                    if message.startswith(trigger):
                        parts = message.split(trigger, 1)
                        if len(parts) > 1 and len(parts[1]) > 0 and parts[1][0] in ".,!?;:，。！？；：":
                            content = ''.join(parts[1:]).strip()
                            break
                        else:
                            content = parts[1].strip()
                            break

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
            
            # 记录AI触发的消息
            self.stats.record_message("xiaotian_ai", response, True)
            
            # 直接返回回复，不加前缀
            return response
        
        return ""  # 未触发时返回空字符串
    
    def _handle_astronomy_poster(self, content: str, user_id: str) -> str:
        """处理天文海报制作请求"""
        try:
            # 处理天文内容并创建海报
            poster_path, message = self.astronomy.process_astronomy_content(
                content, 
                user_id=user_id,
                ai_optimizer=self.ai_utils.optimize_text_length
            )
            
            if poster_path:
                # 保存最近的海报路径和消息，供定时任务使用
                self.last_astronomy_post = (poster_path, message)
                
                # 向发送天文内容的用户直接回复海报
                if self.root_manager.settings['qq_send_callback']:
                    try:
                        print(f"尝试向用户 {user_id} 发送私聊天文海报")
                        
                        # 使用传入的user_id而不是尝试从消息中提取
                        # 向制作天文海报的用户发送私聊消息
                        self.root_manager.settings['qq_send_callback']('private', user_id, None, poster_path)
                        time.sleep(1)  # 短暂延时
                        self.root_manager.settings['qq_send_callback']('private', user_id, f"🌌 天文海报已生成！\n\n{message}", None)
                        
                        print(f"已向用户 {user_id} 发送私聊天文海报")
                    except Exception as send_err:
                        import traceback
                        print(f"向用户发送私聊天文海报失败: {send_err}")
                        print(traceback.format_exc())
                
                return f"🎨 海报制作成功！\n{message}\n路径：{poster_path}"
            else:
                return f"⚠️ {message}"
                
        except Exception as e:
            return f"❌ 海报制作失败：{str(e)}"
            
    def _handle_astronomy_image(self, user_id: str, image_path: str) -> str:
        """处理用户发送的天文海报图片"""
        try:
            print(f"处理用户 {user_id} 发送的图片: {image_path}")
            
            # 检查天文海报模块是否处于等待图片状态
            if not self.astronomy.waiting_for_images:
                print("当前不在等待图片状态，忽略此图片")
                return "您需要先发送天文内容（以\"小天，每日天文做好啦：\"开头），再上传图片"
            
            # 调用天文海报模块处理用户消息和图片
            poster_path, message = self.astronomy.process_user_message("", [image_path])
            
            if poster_path:
                # 保存最近的海报路径和消息，供定时任务使用
                self.last_astronomy_post = (poster_path, message)
                
                # 向发送天文内容的用户直接回复海报
                if self.root_manager.settings['qq_send_callback']:
                    try:
                        print(f"尝试向用户 {user_id} 发送图片处理后的天文海报")
                        
                        # 向用户发送处理后的海报
                        self.root_manager.settings['qq_send_callback']('private', user_id, None, poster_path)
                        
                        time.sleep(1)  # 短暂延时
                        self.root_manager.settings['qq_send_callback']('private', user_id, f"🌌 添加图片后的天文海报已生成！\n\n{message}", None)
                        
                        print(f"已向用户 {user_id} 发送处理后的天文海报")
                    except Exception as send_err:
                        print(f"向用户发送处理后的天文海报失败: {send_err}")
                        import traceback
                        print(traceback.format_exc())
                
                return f"🎨 图片已添加，海报制作成功！\n{message}\n路径：{poster_path}"
            else:
                # 如果没有生成海报，检查等待状态（包括超时自动生成）
                waiting_status, remaining, auto_poster_path, auto_message = self.astronomy.check_waiting_status()
                if auto_poster_path:
                    # 超时自动生成了海报，发送给用户
                    return f"🎨 {auto_message}\n路径：{auto_poster_path}"
                elif waiting_status:
                    return f"✅ {message} 还剩 {remaining} 秒等待时间。"
                else:
                    return f"✅ {message}"
                
        except Exception as e:
            import traceback
            print(f"处理图片失败: {str(e)}")
            print(traceback.format_exc())
            return f"❌ 图片处理失败：{str(e)}"
    
    def _handle_wordstats(self) -> str:
        """处理词频统计请求"""
        try:
            # 强制保存当前数据
            self.word_analyzer.force_save_current_data()
            
            # 生成今日词频图表
            chart_path = self.word_analyzer.generate_daily_barchart()
            
            if chart_path:
                return f"📊 词频统计图表已生成：{chart_path}"
            else:
                return "⚠️ 没有足够的数据生成词频统计"
                
        except Exception as e:
            return f"❌ 词频统计失败：{str(e)}"
    
    def daily_astronomy_task(self):
        """每日天文海报任务"""
        if not self.root_manager.is_feature_enabled('daily_astronomy'):
            return
            
        print(f"🔭 {datetime.now().strftime('%H:%M')} - 执行每日天文海报任务")
        
        if self.last_astronomy_post:
            # 如果有上次处理的天文海报，使用它
            image_path, message = self.last_astronomy_post
            
            print(f"📢 发送天文海报：{image_path}")
            
            # 发送到目标群组
            target_groups = self.root_manager.get_target_groups()
            if target_groups:
                self.root_manager.send_message_to_groups(message, image_path)
                
                # 延时2秒后发送AI点评
                if hasattr(self, 'astronomy') and self.astronomy and self.astronomy.latest_ai_comment:
                    import threading
                    def send_ai_comment():
                        time.sleep(2)  # 延时2秒
                        try:
                            ai_comment_message = f"🌟 小天点评：{self.astronomy.latest_ai_comment}"
                            self.root_manager.send_message_to_groups(ai_comment_message, None)
                            print(f"📝 已发送AI点评到群聊")
                        except Exception as e:
                            print(f"❌ 发送AI点评失败：{e}")
                    
                    # 在后台线程中发送AI点评
                    comment_thread = threading.Thread(target=send_ai_comment)
                    comment_thread.start()
                
            else:
                print("⚠️ 没有设置目标群组，天文海报未发送。请使用命令'小天，设置目标群组：群号1,群号2'来设置目标群组。")
        else:
            print("⚠️ 没有可用的天文海报")
    
    def monthly_astronomy_task(self):
        """月度天文海报合集任务"""
        if not self.root_manager.is_feature_enabled('monthly_astronomy'):
            return
            
        # 只在每月1号执行
        if datetime.now().day != 1:
            return
            
        print(f"📚 {datetime.now().strftime('%H:%M')} - 执行月度天文海报合集任务")
        
        try:
            collection_path = self.astronomy.create_monthly_collection()
            if collection_path:
                print(f"📢 生成月度天文海报合集：{collection_path}")
                
                # 发送到目标群组
                self.root_manager.send_message_to_groups("🌌 上个月的天文海报合集来啦喵~", collection_path)
        except Exception as e:
            print(f"❌ 生成月度天文海报合集失败：{str(e)}")
    
    def daily_wordstats_task(self):
        """每日词频统计任务"""
        print(f"📊 {datetime.now().strftime('%H:%M')} - 执行每日词频统计任务")
        
        try:
            # 强制保存当天的词频数据
            print("正在保存当天词频数据...")
            self.word_analyzer.force_save_current_data()
            print("当天词频数据保存完成")
            
            # 生成词频条形图
            print("开始生成词频条形图...")
            try:
                # 检查是否有足够的消息数据
                if len(self.word_analyzer.daily_messages) == 0:
                    print("⚠️ 警告: 今日没有收集到消息数据，尝试使用历史数据")
                
                chart_path = self.word_analyzer.generate_daily_barchart()
                print(f"条形图生成结果: {chart_path}")
            except Exception as e:
                import traceback
                print(f"❌ 生成条形图时发生异常: {str(e)}")
                print(traceback.format_exc())
                chart_path = None
                
            if chart_path:
                print(f"📢 生成词频统计图表成功：{chart_path}")
                
                # 保存最近的词频图表路径，供消息处理使用
                self.last_wordstats_chart = chart_path
                
                # 检查图表是否实际存在
                if os.path.exists(chart_path):
                    print(f"确认图表文件存在: {chart_path}")
                    # 发送到目标群组
                    self.root_manager.send_message_to_groups("📊 今日热词统计出炉啦喵~", chart_path)
                else:
                    print(f"⚠️ 警告: 图表文件不存在，无法发送: {chart_path}")
                
                # 尝试生成词云图
                try:
                    print("开始生成词云图...")
                    wordcloud_path = self.word_analyzer.generate_daily_wordcloud()
                    print(f"词云图生成结果: {wordcloud_path}")
                    
                    if not wordcloud_path:
                        print("⚠️ 词云图生成失败，返回为空")
                    elif not isinstance(wordcloud_path, str):
                        print(f"⚠️ 词云图路径类型不正确: {type(wordcloud_path)}")
                    else:
                        # 处理路径字符串
                        if "：" in wordcloud_path:  # 如果包含中文冒号，可能是描述信息
                            actual_path = wordcloud_path.split("：")[-1].strip()
                        else:
                            actual_path = wordcloud_path
                        
                        print(f"词云图实际路径: {actual_path}")
                        
                        if os.path.exists(actual_path):
                            print(f"📢 生成词云图成功，确认文件存在：{actual_path}")
                            # 发送到目标群组
                            self.root_manager.send_message_to_groups("☁️ 今日词云图也来啦喵~", actual_path)
                        else:
                            print(f"⚠️ 警告: 词云图文件不存在: {actual_path}")
                except Exception as cloud_err:
                    print(f"❌ 生成词云图失败：{str(cloud_err)}")
                    import traceback
                    print(traceback.format_exc())
            else:
                print("⚠️ 条形图生成失败，但仍将尝试生成词云图")
                
                # 即使条形图生成失败，也尝试生成词云图
                try:
                    print("开始生成词云图（在条形图失败后）...")
                    wordcloud_path = self.word_analyzer.generate_daily_wordcloud()
                    print(f"词云图生成结果: {wordcloud_path}")
                    
                    if not wordcloud_path:
                        print("⚠️ 词云图生成失败，返回为空")
                    elif not isinstance(wordcloud_path, str):
                        print(f"⚠️ 词云图路径类型不正确: {type(wordcloud_path)}")
                    else:
                        # 处理路径字符串
                        if "：" in wordcloud_path:  # 如果包含中文冒号，可能是描述信息
                            actual_path = wordcloud_path.split("：")[-1].strip()
                        else:
                            actual_path = wordcloud_path
                        
                        print(f"词云图实际路径: {actual_path}")
                        
                        if os.path.exists(actual_path):
                            print(f"📢 生成词云图成功，确认文件存在：{actual_path}")
                            # 发送到目标群组
                            self.root_manager.send_message_to_groups("☁️ 今日词云图来啦喵~", actual_path)
                        else:
                            print(f"⚠️ 警告: 词云图文件不存在: {actual_path}")
                except Exception as cloud_err:
                    print(f"❌ 生成词云图失败：{str(cloud_err)}")
                    import traceback
                    print(traceback.format_exc())
        except Exception as e:
            print(f"❌ 生成词频统计失败：{str(e)}")
            import traceback
            print(traceback.format_exc())
    
    def daily_cleanup_task(self):
        """每日数据清理任务"""
        print(f"🧹 {datetime.now().strftime('%H:%M')} - 执行每日数据清理任务")
        
        try:
            # 清理旧的天文海报数据
            self.astronomy.cleanup_old_data(days_to_keep=30)
            
            # 清理旧的词频统计数据
            self.word_analyzer.cleanup_old_data(days_to_keep=30)
            
            # 清理旧的日志
            self.admin.clean_old_logs(days_to_keep=1)
            
            print("🧹 数据清理完成")
        except Exception as e:
            print(f"❌ 数据清理失败：{str(e)}")
    
    def _check_astronomy_timeout(self):
        """检查天文海报超时状态并自动发送"""
        if not hasattr(self, 'astronomy') or not self.astronomy:
            return
        
        waiting_status, remaining, auto_poster_path, auto_message = self.astronomy.check_waiting_status()
        if auto_poster_path and self.astronomy.waiting_user_id:
            # 超时自动生成了海报
            self.last_astronomy_post = (auto_poster_path, "今天的每日天文来啦")
            
            # 发送给等待的用户
            user_id = self.astronomy.waiting_user_id
            group_id = self.astronomy.waiting_group_id
            
            if hasattr(self.root_manager, 'settings') and 'qq_send_callback' in self.root_manager.settings:
                try:
                    print(f"自动向用户 {user_id} 发送超时天文海报")
                    
                    if group_id is None:
                        # 私聊发送：先发图片，再发提示消息，最后发点评
                        self.root_manager.settings['qq_send_callback']('private', user_id, None, auto_poster_path)
                        
                        # 延时发送提示消息和点评
                        import threading
                        def send_delayed_messages():
                            time.sleep(2)  # 延时2秒
                            try:
                                # 发送提示消息
                                self.root_manager.settings['qq_send_callback']('private', user_id, "🎨 等待图片超时，已自动生成海报", None)
                                
                                # 如果有AI点评，再发送点评
                                if self.astronomy.latest_ai_comment:
                                    time.sleep(1)  # 再延时1秒
                                    ai_comment_message = f"🌟 小天点评：{self.astronomy.latest_ai_comment}"
                                    self.root_manager.settings['qq_send_callback']('private', user_id, ai_comment_message, None)
                                    print(f"已发送超时海报的AI点评给用户 {user_id}")
                            except Exception as e:
                                print(f"发送延时消息失败: {e}")
                        
                        # 在后台线程中发送延时消息
                        threading.Thread(target=send_delayed_messages).start()
                        
                    else:
                        # 群聊发送：先发图片，再发提示消息，最后发点评
                        self.root_manager.settings['qq_send_callback']('group', group_id, None, auto_poster_path)
                        
                        # 延时发送提示消息和点评
                        import threading
                        def send_delayed_messages():
                            time.sleep(2)  # 延时2秒
                            try:
                                # 发送提示消息
                                self.root_manager.settings['qq_send_callback']('group', group_id, "🎨 等待图片超时，已自动生成海报", None)
                                
                                # 如果有AI点评，再发送点评
                                if self.astronomy.latest_ai_comment:
                                    time.sleep(1)  # 再延时1秒
                                    ai_comment_message = f"🌟 小天点评：{self.astronomy.latest_ai_comment}"
                                    self.root_manager.settings['qq_send_callback']('group', group_id, ai_comment_message, None)
                                    print(f"已发送超时海报的AI点评到群 {group_id}")
                            except Exception as e:
                                print(f"发送延时消息失败: {e}")
                        
                        # 在后台线程中发送延时消息
                        threading.Thread(target=send_delayed_messages).start()
                    
                    # 清除等待状态
                    self.astronomy.waiting_user_id = None
                    self.astronomy.waiting_group_id = None
                    
                except Exception as send_err:
                    print(f"自动发送超时海报失败: {send_err}")
            else:
                print("无法发送超时海报：回调函数不可用")
