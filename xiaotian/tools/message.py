import os
import time
import random
from ..manage.root_manager import RootManager
from ..ai.ai_core import XiaotianAI
from ..manage.config import TRIGGER_WORDS


class MessageSender:
    def __init__(self, root_manager: RootManager, ai_core: XiaotianAI):
        self.root_manager = root_manager
        self.ai = ai_core

    def send_message_to_groups(self, message: str = None, image_path: str = None, group_id: str = None):
        """向目标群组发送消息
        
        Args:
            message: 要发送的文本消息
            image_path: 要发送的图片路径
            group_id: 指定的群组ID，如果提供则只发送到这个群组
        """
        if self.root_manager.settings['qq_send_callback']:
            all_target_groups = self.root_manager.get_target_groups()
            
            # 如果指定了group_id，则只发送到该群组，但前提是它在目标群组列表中
            if group_id:
                if group_id in all_target_groups:
                    target_groups = [group_id]
                else:
                    print(f"警告：尝试向非目标群组 {group_id} 发送消息，已阻止。")
                    return
            else:
                target_groups = all_target_groups

            for group_id in target_groups:
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
