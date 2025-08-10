import os
from ..manage.root_manager import RootManager
from ..ai.ai_core import XiaotianAI
from ..manage.config import TRIGGER_WORDS


class MessageSender:
    def __init__(self, root_manager: RootManager, ai_core: XiaotianAI):
        self.root_manager = root_manager
        self.ai = ai_core

    def send_message_to_groups(self, message: str = None, image_path: str = None):
        """向目标群组发送消息"""
        if self.root_manager.settings['qq_send_callback'] and self.root_manager.settings['target_groups']:
            for group_id in self.root_manager.settings['target_groups']:
                try:
                    print(f"正在发送消息到群组 {group_id}...")

                    # 处理图片路径
                    valid_image_path = None
                    if image_path:
                        # 首先尝试直接使用路径
                        if os.path.exists(image_path):
                            print(f"图片路径有效: {image_path}")
                            valid_image_path = image_path
                        # 尝试解析路径中的相对路径部分
                        elif ": " in image_path:
                            actual_path = image_path.split(": ")[-1].strip()
                            if os.path.exists(actual_path):
                                print(f"找到实际图片路径: {actual_path}")
                                valid_image_path = actual_path
                            else:
                                print(f"警告: 解析后的图片路径仍无效: {actual_path}")
                        # 尝试使用绝对路径
                        else:
                            abs_path = os.path.abspath(image_path)
                            if os.path.exists(abs_path):
                                print(f"使用绝对路径: {abs_path}")
                                valid_image_path = abs_path
                            else:
                                print(f"警告: 所有图片路径均无效: {image_path}")

                    # 添加延时，避免消息发送过快
                    import time
                    import random
                    wait_time = min(30, max(2, len(message) // 3)) if message else 2
                    time.sleep(wait_time + random.uniform(-1, 1))

                    # 发送消息
                    if valid_image_path:
                        # 先发送图片，后发送文本
                        print(f"先发送图片到群组 {group_id}, 图片路径: {valid_image_path}")
                        self.root_manager.settings['qq_send_callback']('group', group_id, None, valid_image_path)

                        # 添加短暂延时，确保图片发送完成
                        time.sleep(4 + random.uniform(0, 1))

                        # 如果有文本消息，再发送文本
                        if message:
                            print(f"再发送文本到群组 {group_id}")
                            self.root_manager.settings['qq_send_callback']('group', group_id, message, None)
                    else:
                        print(f"发送纯文本消息到群组 {group_id}")
                        self.root_manager.settings['qq_send_callback']('group', group_id, message)
                except Exception as e:
                    print(f"发送消息到群组 {group_id} 失败：{e}")
                    import traceback
                    print(traceback.format_exc())

    def _handle_chat(self, user_id: str, message: str, group_id: str = None) -> str:
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

            # 直接返回回复，不加前缀
            return response
        
        return ""  # 未触发时返回空字符串
