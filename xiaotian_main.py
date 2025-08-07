"""
小天AI智能体 - QQ机器人版
使用NcatBot框架实现
"""

import sys
import os
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
import threading

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入NcatBot相关库
from ncatbot.core import BotClient, GroupMessage, PrivateMessage, Request
from ncatbot.utils import get_log

# 导入小天相关模块
from xiaotian.scheduler import XiaotianScheduler
from xiaotian.config import TRIGGER_WORDS, ADMIN_USER_IDS, BLACKLIST_USER_IDS


class XiaotianQQBot:
    def __init__(self):
        """初始化小天QQ机器人"""
        self._log = get_log()
        self.root_id = None  # 将在start()中设置
        self.scheduler = None  # 将在start()中初始化
        self.bot = BotClient()
        
        # API调用速率限制
        self.rate_limits: Dict[str, Dict] = {
            'global': {
                'last_call': 0,
                'interval': 1.0,  # 全局每秒最多1次调用
                'counter': 0,
                'max_burst': 10   # 最大突发请求数
            }
        }
        self.user_cooldowns: Dict[str, float] = {}  # 用户冷却时间
        self.user_blacklist: Set[str] = set(BLACKLIST_USER_IDS)  # 黑名单用户
        
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
        
        # 注册启动事件处理
        self.bot.add_startup_handler(self.on_startup)
    
    async def on_private_message(self, msg: PrivateMessage):
        """处理私聊消息"""
        self._log.info(f"收到私聊消息: {msg.user_id}:{msg.raw_message}")
        
        # 检查是否是黑名单用户
        if str(msg.user_id) in self.user_blacklist:
            self._log.info(f"黑名单用户: {msg.user_id}，忽略消息")
            return
        
        # 检查速率限制
        if not self._check_rate_limit(str(msg.user_id)):
            self._log.info(f"用户 {msg.user_id} 触发速率限制")
            return

        # 提取图片或文件数据（如果有）- 仅限root用户且仅限私聊
        image_data = None
        # 检查是否为root用户
        is_root = str(msg.user_id) == self.root_id
        
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
                
                # 处理文件类型 - 仅下载字体文件
                elif segment.get('type') == 'file':
                    file_name = segment.get('data', {}).get('file')
                    file_id = segment.get('data', {}).get('file_id')
                    file_url = segment.get('data', {}).get('url')
                    
                    # 检查是否为字体文件
                    is_font_file = False
                    if file_name:
                        lower_name = file_name.lower()
                        is_font_file = lower_name.endswith(('.ttf', '.otf', '.woff', '.woff2'))
                    
                    if not is_font_file:
                        self._log.warning(f"非字体文件被忽略: {file_name}")
                        continue
                        
                    if file_url:
                        try:
                            import requests
                            self._log.info(f"Root用户正在下载字体文件: {file_name}")
                            response = requests.get(file_url, timeout=30)
                            if response.status_code == 200:
                                image_data = response.content
                                self._log.info(f"字体文件下载成功，大小: {len(image_data)} 字节")
                            break
                        except Exception as e:
                            self._log.warning(f"下载字体文件失败: {e}")
                    elif file_id:
                        try:
                            # 尝试使用API获取字体文件
                            self._log.info(f"Root用户尝试使用API获取字体文件: {file_id}")
                            file_info = self.bot.api.get_file_sync(file_id=file_id)
                            if file_info and 'url' in file_info:
                                import requests
                                response = requests.get(file_info['url'], timeout=30)
                                if response.status_code == 200:
                                    image_data = response.content
                                    self._log.info(f"通过API下载字体文件成功，大小: {len(image_data)} 字节")
                            else:
                                # 无法获取文件URL，提供手动处理指南
                                self._log.warning(f"API未返回文件URL，无法自动下载文件: {file_name}")
                                await msg.reply(text=f"⚠️ 无法自动下载文件 {file_name}。请尝试用以下方式替代：\n\n1. 将字体文件直接发送到群中作为图片\n2. 或通过FTP/SFTP上传到服务器的xiaotian/data/fonts/目录")
                        except Exception as e:
                            self._log.warning(f"通过API获取字体文件失败: {e}")
        # 处理消息（私聊不传group_id）
        response = self.scheduler.process_message(str(msg.user_id), msg.raw_message, None, image_data)
        
        if response:
            await asyncio.sleep(1)  # 等待1秒（1000毫秒）
            await msg.reply(text=response)
    
    async def on_group_message(self, msg: GroupMessage):
        """处理群聊消息"""
        self._log.info(f"收到群聊消息: {msg.group_id}/{msg.user_id}:{msg.raw_message}")
        
        # 检查是否是黑名单用户
        if str(msg.user_id) in self.user_blacklist:
            self._log.info(f"黑名单用户: {msg.user_id}，忽略消息")
            return
        
        # 检查速率限制
        if not self._check_rate_limit(f"group_{msg.group_id}_{msg.user_id}"):
            self._log.info(f"用户 {msg.user_id} 在群 {msg.group_id} 触发速率限制")
            return
        
        image_data = None

        # 处理消息（传入群组ID以支持分别记忆）
        response = self.scheduler.process_message(str(msg.user_id), msg.raw_message, str(msg.group_id), image_data)
        
        if response:
            await msg.reply(text=response)
    
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
    
    def on_startup(self):
        """机器人启动事件处理"""
        self._log.info("🤖 小天QQ机器人已启动")
        
        # 向管理员发送启动通知
        startup_msg = (f"🤖 小天AI智能体已启动\n⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                     f"🌟 版本: v2.0 - 全新超级管理员系统\n"
                     f"🎯 Root管理员: {self.root_id}\n"
                     f"🔮 支持功能: 天文海报、词频统计、智能气氛调节")
                     
        for admin_id in ADMIN_USER_IDS:
            try:
                self._log.info(f"向管理员 {admin_id} 发送启动通知")
                self.bot.api.post_private_msg_sync(
                    user_id=int(admin_id), 
                    msg=startup_msg
                )
            except Exception as e:
                self._log.error(f"向管理员 {admin_id} 发送启动通知失败: {e}")
    
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
        
        if not os.getenv("MOONSHOT_API_KEY"):
            self._log.error("❌ 请设置环境变量 MOONSHOT_API_KEY")
            return
            
        # 初始化调度器，传入QQ发送回调
        self.scheduler = XiaotianScheduler(root_id=root_id, qq_send_callback=self.qq_send_callback)
        
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
        required_fonts = ["title.ttf", "artistic.ttf", "text.TTF", "simhei.ttf"]
        for font in required_fonts:
            font_path = os.path.join(fonts_dir, font)
            if not os.path.exists(font_path):
                self._log.warning(f"⚠️ 字体文件 {font} 不存在，将使用默认字体")


def main():
    """主函数"""
    # 启动QQ机器人
    bot = XiaotianQQBot()
    bot.start()


if __name__ == "__main__":
    main()
