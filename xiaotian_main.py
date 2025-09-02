"""
小天AI智能体 - QQ机器人版
使用NcatBot框架实现
"""

import sys
import os
import random
import threading
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Set

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入NcatBot相关库
from ncatbot.core import BotClient, GroupMessage, PrivateMessage, Request, At
from ncatbot.utils import get_log

# 导入小天相关模块
from xiaotian.scheduler import XiaotianScheduler
from xiaotian.manage.config import ADMIN_USER_IDS, BLACKLIST_USER_IDS
from xiaotian.ai.ai_core import XiaotianAI


class XiaotianQQBot:
    def __init__(self):
        """初始化小天QQ机器人"""
        self._log = get_log()
        self.root_id = None  # 将在start()中设置
        self.scheduler = None  # 将在start()中初始化
        self.ai = None
        self.bot = BotClient()
        
        # API调用速率限制
        self.rate_limits: Dict[str, Dict] = {
            'global': {
                'last_call': 0,
                'interval': 0.1,  # 全局每秒最多10次调用
                'counter': 0,
                'max_burst': 10   # 最大突发请求数
            }
        }
        self.user_cooldowns: Dict[str, float] = {}  # 用户冷却时间
        self.user_blacklist: Set[str] = set(BLACKLIST_USER_IDS)  # 黑名单用户
        
        # 回复状态管理
        self.replying_users: Set[str] = set()  # 正在回复的用户集合
        self.reply_locks: Dict[str, asyncio.Lock] = {}  # 每个用户的回复锁


        # 注册回调函数
        self.register_handlers()
    def qq_send_callback(self, msg_type: str, target_id: str, message: str = None, image_path: str = None):
        """QQ发送消息的回调函数"""
        try:
            # 检查 target_id 是否为 None
            if target_id is None:
                self._log.error("目标 ID (target_id) 为空，无法发送消息")
                return

            # 添加详细日志
            if message:
                self._log.info(f"发送消息到 {msg_type}({target_id}): {message[:50]}{'...' if len(message) > 50 else ''}")
            else:
                self._log.info(f"发送消息到 {msg_type}({target_id}): [仅图片消息]")

            if image_path:
                self._log.info(f"附带图片: {image_path}")

            # 确保图片路径有效
            valid_image_ = False
            if image_path and os.path.exists(image_path):
                valid_image_ = True
                self._log.info(f"图片文件存在: {image_path}")
                # 确保使用绝对路径
                image_path = os.path.abspath(image_path)
                self._log.info(f"图片绝对路径: {image_path}")
            elif image_path:
                self._log.warning(f"图片文件不存在，无法发送图片: {image_path}")

            # 发送群聊消息
            if msg_type == 'group':
                if valid_image_ and not message:
                    # 仅发送图片消息
                    self.bot.api.post_group_msg_sync(group_id=int(target_id), image=image_path)
                    self._log.info(f"已发送仅图片的群消息到 {target_id}")
                elif valid_image_:
                    # 发送图片和文本消息
                    try:
                        self.bot.api.post_group_msg_sync(group_id=int(target_id), text=message, image=image_path)
                        self._log.info(f"已发送带图片的群消息到 {target_id}")
                    except Exception as img_err:
                        self._log.error(f"发送图片消息失败，尝试发送纯文本: {img_err}")
                        self.bot.api.post_group_msg_sync(group_id=int(target_id), text=message)
                else:
                    # 发送纯文本消息
                    self.bot.api.post_group_msg_sync(group_id=int(target_id), text=message)
                    self._log.info(f"已发送纯文本群消息到 {target_id}")

            # 发送私聊消息
            elif msg_type == 'private':
                if valid_image_ and not message:
                    # 仅发送图片消息
                    self.bot.api.post_private_msg_sync(user_id=int(target_id), image=image_path)
                    self._log.info(f"已发送仅图片的私聊消息到 {target_id}")
                elif valid_image_:
                    # 发送图片和文本消息
                    try:
                        self.bot.api.post_private_msg_sync(user_id=int(target_id), text=message, image=image_path)
                        self._log.info(f"已发送带图片的私聊消息到 {target_id}")
                    except Exception as img_err:
                        self._log.error(f"发送图片消息失败，尝试发送纯文本: {img_err}")
                        self.bot.api.post_private_msg_sync(user_id=int(target_id), text=message)
                else:
                    # 发送纯文本消息
                    self.bot.api.post_private_msg_sync(user_id=int(target_id), text=message)
                    self._log.info(f"已发送纯文本私聊消息到 {target_id}")
        except Exception as e:
            self._log.error(f"发送消息失败：{e}")
            import traceback
            self._log.error(traceback.format_exc())
    def register_handlers(self):
        """注册NcatBot回调函数"""
        # 注册私聊消息处理
        self.bot.add_private_event_handler(self.on_private_message)
        
        # 注册群聊消息处理
        self.bot.add_group_event_handler(self.on_group_message)
        
        # 注册请求处理（好友申请和群邀请）
        self.bot.add_request_event_handler(self.on_request)
        
        # 注册群组通知事件处理（如新成员入群）
        self.bot.add_notice_event_handler(self.on_group_notice)
    
    def handle_response(self, response:str, user_id: str, group_id: str = None) -> tuple:
        # 尝试解析AI回复中的JSON信息并处理
        try:
            memory_key = self.ai._get_memory_key(user_id, group_id)
            cleaned_response, like_value, wait_time, not_even_wrong = self.ai.parse_ai_response_for_like(response)
            
            # 如果标记为not_even_wrong，不进行回复
            if not_even_wrong:
                print(f"🚫 用户 {memory_key} 的消息被标记为not_even_wrong，不进行回复")
                return [], [], ""
            
            if like_value:
                notification_message = ""
                notification_message = self.ai.update_user_like(memory_key, like_value)
                # 获取当前like状态并添加表情显示 - 使用统一的用户ID
                user_id_for_like = self.ai._extract_user_id_from_memory_key(memory_key)
                like_status = self.ai.get_user_like_status(user_id_for_like)
                like_display = self.ai.format_like_display(like_status['total_like'])
                # 组合最终回复：原回复 + like显示 + 可能的通知消息
                like_response = ""
                like_response += f"{like_display}"
                if notification_message:
                    like_response += f"{notification_message}"
            else:
                like_response = ""
            # 返回最终回复
            return wait_time, cleaned_response, like_response
        except Exception as e:
            # 如果解析失败，说明这是一个普通的文本回复（比如root命令结果）
            # 直接返回文本，不处理like值
            self._log.debug(f"解析AI响应失败，当作普通文本处理: {e}")
            return [3], [response], ""  # 返回固定等待时间和原始响应

    async def on_private_message(self, msg: PrivateMessage):
        """处理私聊消息"""
        self._log.info(f"收到私聊消息: {msg.user_id}:{msg.raw_message}")
        
        user_id = str(msg.user_id)
        
        # 检查是否是黑名单用户
        if user_id in self.user_blacklist:
            self._log.info(f"黑名单用户: {msg.user_id}，忽略消息")
            return
        
        # 检查该用户是否正在被回复
        if user_id in self.replying_users:
            self._log.info(f"用户 {msg.user_id} 正在被回复中，忽略新消息")
            return
        
        # 检查速率限制
        if not self._check_rate_limit(user_id):
            self._log.info(f"用户 {msg.user_id} 触发速率限制")
            return

        # 获取用户回复锁
        if user_id not in self.reply_locks:
            self.reply_locks[user_id] = asyncio.Lock()
        
        async with self.reply_locks[user_id]:
            # 标记开始回复
            self.replying_users.add(user_id)
            
            try:
                # 提取图片或文件数据（如果有）- 仅限root用户且仅限私聊
                image_data = None
                # 检查是否为root用户
                is_root = user_id == self.root_id
                
                if is_root and hasattr(msg, 'message') and msg.message:
                    for segment in msg.message:
                        # 处理图片类型
                        if segment.get('type') == 'image':
                            image_url = segment.get('data', {}).get('url')
                            if image_url:
                                try:
                                    import requests
                                    response = requests.get(image_url, timeout=10)
                                    if response.status_code == 200:
                                        image_data = response.content
                                        self._log.info(f"Root用户图片下载成功，大小: {len(image_data)} 字节")
                                    break
                                except Exception as e:
                                    self._log.warning(f"下载图片失败: {e}")
                                    
                # 处理消息（私聊不传group_id）
                response = self.scheduler.process_message(user_id, msg.raw_message, None, image_data)
                self._log.info(f"Scheduler返回响应: '{response}' (类型: {type(response)}, 长度: {len(str(response)) if response else 0})")
                
                # 检查是否有回复
                if response:  # 如果有回复内容
                    self._log.info(f"开始处理响应...")
                    wait_time, cleaned_response, like_response = self.handle_response(response, user_id)
                    self._log.info(f"Handle_response返回 - wait_time: {wait_time}, cleaned_response: {cleaned_response}, like_response: '{like_response}'")
                    
                    # 检查返回值是否有效
                    if wait_time and cleaned_response:
                        self._log.info(f"发送多条消息，共{len(cleaned_response)}条")
                        for i in range(len(wait_time)):
                            if cleaned_response[i]:
                                sleep_time = wait_time[i] + random.uniform(0, 3)
                                self.scheduler.add_response_wait_time(sleep_time)
                                await asyncio.sleep(sleep_time)
                                await msg.reply(text=cleaned_response[i])
                                self._log.info(f"已发送第{i+1}条消息: {cleaned_response[i][:50]}...")
                    elif cleaned_response:
                        # 如果只有cleaned_response，没有wait_time
                        self._log.info(f"发送单条消息: {cleaned_response}")
                        sleep_time = 3 + random.uniform(0, 1)
                        self.scheduler.add_response_wait_time(sleep_time)
                        await asyncio.sleep(sleep_time)
                        await msg.reply(text=cleaned_response)
                        self._log.info(f"已发送消息")
                        
                    if like_response:
                        self._log.info(f"发送like响应: {like_response}")
                        sleep_time = 3 + random.uniform(-1, 2)
                        self.scheduler.add_response_wait_time(sleep_time)
                        await asyncio.sleep(sleep_time)
                        await msg.reply(text=like_response)
                        self._log.info(f"已发送like响应")
                else:
                    self._log.info(f"响应为空，不发送消息")
                    
            finally:
                # 标记回复结束
                self.replying_users.discard(user_id)

    async def on_group_message(self, msg: GroupMessage):
        """处理群聊消息"""
        self._log.info(f"收到群聊消息: {msg.group_id}/{msg.user_id}:{msg.raw_message}")
        
        user_id = str(msg.user_id)
        group_id = str(msg.group_id)
        user_key = f"{user_id}_{group_id}"  # 群聊中的用户唯一标识
        
        # 检查是否是黑名单用户
        if user_id in self.user_blacklist:
            self._log.info(f"黑名单用户: {msg.user_id}，忽略消息")
            return
        
        # 检查该用户是否正在被回复
        if user_key in self.replying_users:
            self._log.info(f"用户 {msg.user_id} 在群 {msg.group_id} 正在被回复中，忽略新消息")
            return
        
        # 检查速率限制
        if not self._check_rate_limit(f"group_{group_id}_{user_id}"):
            self._log.info(f"用户 {msg.user_id} 在群 {msg.group_id} 触发速率限制")
            return
        
        # 获取用户回复锁
        if user_key not in self.reply_locks:
            self.reply_locks[user_key] = asyncio.Lock()
        
        async with self.reply_locks[user_key]:
            # 标记开始回复
            self.replying_users.add(user_key)
            
            try:
                image_data = None

                # 处理消息
                response = self.scheduler.process_message(user_id, msg.raw_message, group_id, image_data)

                wait_time, cleaned_response, like_response = self.handle_response(response, user_id, group_id)
                
                if wait_time and cleaned_response:
                    for i in range(len(wait_time)):
                        if cleaned_response[i]:
                            if i != 0:
                                sleep_time = wait_time[i] + random.uniform(0, 1)
                                # 将等待时间累加到scheduler中，用于唤醒超时计算
                                self.scheduler.add_response_wait_time(sleep_time)
                                await asyncio.sleep(sleep_time)
                            else:
                                sleep_time = 1
                                self.scheduler.add_response_wait_time(sleep_time)
                                await asyncio.sleep(sleep_time)
                            # 检查是否有其他用户请求，如果没有则不使用引用
                            if len(self.replying_users) <= 1:  # 只有当前用户在回复队列中
                                await self.bot.api.post_group_msg(group_id=int(group_id), text=cleaned_response[i])
                            else:
                                await msg.reply(text=cleaned_response[i])
                    self.replying_users.discard(user_key)
                    if like_response:
                        sleep_time = 1 + random.uniform(0, 2)
                        self.scheduler.add_response_wait_time(sleep_time)
                        await asyncio.sleep(sleep_time)
                        if len(self.replying_users) <= 1:
                            await self.bot.api.post_group_msg(group_id=int(group_id), text=like_response)
                        else:
                            await msg.reply(text=like_response)
                elif cleaned_response:
                    sleep_time = 3 + random.uniform(0, 1)
                    self.scheduler.add_response_wait_time(sleep_time)
                    # 检查是否为余额不足错误
                    if cleaned_response == "抱歉，我遇到了一些问题：Error code: 402 - {'error': {'message': 'Insufficient Balance', 'type': 'unknownerror', 'param': None, 'code': 'invalidrequest_error'}}":
                        cleaned_response = "小天包里没钱啦，能不能拜托你联系一下会长，求求啦"
                    await asyncio.sleep(sleep_time)
                    if len(self.replying_users) <= 1:
                        await self.bot.api.post_group_msg(group_id=int(group_id), text=cleaned_response)
                    else:
                        await msg.reply(text=cleaned_response)
                    self.replying_users.discard(user_key)
                else:
                    self.replying_users.discard(user_key)

                self.scheduler.last_user_id = user_id
                self.scheduler.last_group_id = group_id
                
            except Exception as e:
                try:
                    self.replying_users.discard(user_key)
                    self._log.error(f"处理群消息时出错: {e}")
                except Exception:
                    pass

    async def on_request(self, request: Request):
        """处理请求（好友申请和群邀请）"""
        self._log.info(f"收到请求: {request.request_type} - {request.user_id}")
        
        # 处理好友请求（除了黑名单外全部通过）
        if request.is_friend_add():
            # 检查是否在黑名单中
            if request.user_id in self.user_blacklist:
                self._log.info(f"拒绝黑名单用户好友申请: {request.user_id}")
                await request.reply(accept=False, comment="您在黑名单中")
            else:
                self._log.info(f"接受好友申请: {request.user_id}")
                await request.reply(accept=True, comment="")
        
        # 不处理群邀请
        elif request.is_group_add():
            self._log.info(f"忽略群邀请: {request.group_id}")
            # 不做任何操作，忽略群请求
            pass
    
    def _check_rate_limit(self, user_id: str) -> bool:
        """
        检查API调用速率限制
        返回True表示允许调用，False表示拒绝调用
        """
        now = time.time()
        
        # 全局速率限制
        global_limit = self.rate_limits['global']
        elapsed = now - global_limit['last_call']
        
        # 更新全局计数器
        if elapsed > global_limit['interval']:
            # 重置计数器
            if elapsed > global_limit['interval'] * 2:
                global_limit['counter'] = 0
            else:
                # 随时间衰减计数器
                reduction = int(elapsed / global_limit['interval'])
                global_limit['counter'] = max(0, global_limit['counter'] - reduction)
        
        # 检查是否超过全局最大突发请求数
        if global_limit['counter'] >= global_limit['max_burst']:
            return False
        
        # 检查用户冷却时间
        if user_id in self.user_cooldowns:
            user_cooldown = self.user_cooldowns[user_id]
            if now < user_cooldown:
                return False
        
        # 更新全局限制
        global_limit['last_call'] = now
        global_limit['counter'] += 1
        
        # 设置用户冷却时间（每个用户3秒内最多1条消息）
        self.user_cooldowns[user_id] = now + 3.0
        
        return True
    
    def start(self):
        """启动QQ机器人"""
        # 创建必要的目录
        os.makedirs("xiaotian/data", exist_ok=True)
        os.makedirs("xiaotian/output/posters", exist_ok=True)
        os.makedirs("xiaotian/output/charts", exist_ok=True)
        os.makedirs("xiaotian/data/wordstats", exist_ok=True)
        os.makedirs("xiaotian/data/astronomy_images", exist_ok=True)
        os.makedirs("xiaotian/data/fonts", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        bot_uin = os.getenv("NCATBOT_QQ")
        root_id = os.getenv("NCATBOT_ADMIN")
        
        self.root_id = root_id
        
        # 检查API密钥
        if not os.getenv("MOONSHOT_API_KEY"):
            self._log.error("❌ 请设置环境变量 MOONSHOT_API_KEY")
            return
        
        # 初始化AI和调度器
        self.ai = XiaotianAI()
        self.scheduler = XiaotianScheduler(root_id=root_id, qq_send_callback=self.qq_send_callback, ai = self.ai)
        
        # 检查是否有必要的图片和字体文件
        self._check_required_files()
        
        # 启动调度器
        self.scheduler.start_scheduler()
            
        # 运行机器人
        try:
            self._log.info(f"正在启动小天QQ机器人，QQ号: {bot_uin}")
            self.bot.run(bt_uin=bot_uin, root=root_id)
        except Exception as e:
            self._log.error(f"启动失败: {str(e)}")
            
    def _check_required_files(self):
        """检查必要的资源文件是否存在"""
        # 检查月份图片
        images_dir = "xiaotian/data/astronomy_images"
        for month in range(1, 13):
            image_path = os.path.join(images_dir, f"{month}.jpg")
            if not os.path.exists(image_path):
                self._log.warning(f"⚠️ 月份图片 {month}.jpg 不存在，请添加")
        
        # 检查默认图片
        default_image = os.path.join(images_dir, "default.jpg")
        if not os.path.exists(default_image):
            self._log.warning("⚠️ 默认图片 default.jpg 不存在，请添加")
                
        # 检查字体文件
        fonts_dir = "xiaotian/data/fonts"
        required_fonts = ["art.TTF", "ciyun.TTF", "default.ttf", "text.TTF"]
        for font in required_fonts:
            font_path = os.path.join(fonts_dir, font)
            if not os.path.exists(font_path):
                self._log.warning(f"⚠️ 字体文件 {font} 不存在，将使用默认字体")

    
    async def on_group_notice(self, notice):
        """
        处理群组通知事件（如新成员入群）
        
        Args:
            notice: 通知事件数据
        """
        self._log.info(f"收到群组通知: {notice}")
        
        # 检查是否是群成员增加通知
        if notice.get("notice_type") == "group_increase":
            group_id = str(notice.get("group_id"))
            user_id = str(notice.get("user_id"))
            self_id = str(notice.get("self_id"))  # 机器人自己的QQ号
            
            self._log.info(f"检测到新成员 {user_id} 加入群 {group_id}")
            
            # 如果是机器人自己被邀请入群，则不发送欢迎消息
            if user_id == self_id:
                self._log.info(f"机器人自己加入群 {group_id}，不发送欢迎消息")
                return
            
            # 生成欢迎消息
            welcome_message = self.scheduler.welcome_manager.process_group_increase_notice(notice)
            
            if welcome_message:
                # 设置一个短暂的延迟，让新成员有时间看到入群提示
                await asyncio.sleep(5)
                
                try:
                    # 发送欢迎消息
                    await self.bot.api.post_group_msg(group_id=int(group_id), text=welcome_message)
                    self._log.info(f"已发送欢迎消息给新成员 {user_id} 在群 {group_id}")
                except Exception as e:
                    self._log.error(f"发送欢迎消息失败: {e}")


def main():
    """主函数"""
    # 启动QQ机器人
    bot = XiaotianQQBot()
    bot.start()


if __name__ == "__main__":
    main()
