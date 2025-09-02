"""
小天的Root超级管理员模块
负责处理Root用户的所有高级管理功能
"""

import os
import json
import shutil
import base64
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
import glob
from .config import ROOT_ADMIN_DATA_FILE, ASTRONOMY_IMAGES_DIR, ASTRONOMY_FONTS_DIR


class RootManager:
    def __init__(self, root_id: str):
        self.root_id = root_id
        self.settings_file = ROOT_ADMIN_DATA_FILE
        self.load_settings()
        
        # AI实例（运行时设置）
        self.ai = None
        
        # 等待图片的用户命令
        self.pending_operations = {}  # user_id: {"type": "image", "name": "filename"}

        # 确保必要的目录存在
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        os.makedirs(ASTRONOMY_IMAGES_DIR, exist_ok=True)
        os.makedirs(ASTRONOMY_FONTS_DIR, exist_ok=True)
    
    def load_settings(self):
        """加载Root设置"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
            
            # 默认设置
            self.settings = {
                'auto_trigger_groups': data.get('auto_trigger_groups', [815140803]),  # 自动气氛调节的群组
                'daily_trigger_limit': data.get('daily_trigger_limit', 2),  # 每日触发限制
                'today_trigger_count': data.get('today_trigger_count', {}),  # 今日已触发次数
                'last_trigger_date': data.get('last_trigger_date', ''),  # 上次触发日期
                'qq_send_callback': None,  # QQ发送回调函数（运行时设置）
                'target_groups': data.get('target_groups', [815140803]),  # 目标群组
                'weather_city': data.get('weather_city', '双流'),  # 天气城市
                'permanent_admins': data.get('permanent_admins', []),  # 常驻管理员QQ号列表
                'enabled_features': data.get('enabled_features', {
                    'daily_weather': True,
                    'daily_astronomy': True,
                    'monthly_astronomy': True,
                    'auto_trigger': True
                })
            }
        except Exception as e:
            print(f"加载Root设置失败：{e}")
            self.settings = {
                'auto_trigger_groups': [],
                'daily_trigger_limit': 2,
                'today_trigger_count': {},
                'last_trigger_date': '',
                'qq_send_callback': None,
                'target_groups': [],
                'weather_city': '双流',
                'permanent_admins': [],  # 常驻管理员QQ号列表
                'enabled_features': {
                    'daily_weather': True,
                    'daily_astronomy': True,
                    'monthly_astronomy': True,
                    'auto_trigger': True
                }
            }
    
    def save_settings(self):
        """保存Root设置"""
        try:
            # 移除不需要持久化的设置
            save_data = self.settings.copy()
            save_data.pop('qq_send_callback', None)
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存Root设置失败：{e}")
    
    # 临时管理员系统
    def __init__(self, root_id: str):
        self.root_id = root_id
        self.settings_file = ROOT_ADMIN_DATA_FILE
        self.load_settings()
        
        # AI实例（运行时设置）
        self.ai = None
        
        # 临时管理员列表（仅在内存中）
        self.temp_admins = []
        
        # 等待图片的用户命令
        self.pending_operations = {}  # user_id: {"type": "image", "name": "filename"}

        # 确保必要的目录存在
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        os.makedirs(ASTRONOMY_IMAGES_DIR, exist_ok=True)
        os.makedirs(ASTRONOMY_FONTS_DIR, exist_ok=True)
    
    def is_root(self, user_id: str) -> bool:
        """检查是否是Root用户或管理员"""
        if user_id == self.root_id:
            return True
        # 检查是否是常驻管理员
        if user_id in self.settings.get('permanent_admins', []):
            return True
        # 检查是否是临时管理员
        if user_id in self.temp_admins:
            return True
        return False
        
    def add_temp_admin(self, admin_id: str) -> bool:
        """添加临时管理员"""
        if admin_id not in self.temp_admins:
            self.temp_admins.append(admin_id)
            print(f"✅ 已添加临时管理员: {admin_id}")
            return True
        return False
        
    def remove_temp_admin(self, admin_id: str) -> bool:
        """移除临时管理员"""
        if admin_id in self.temp_admins:
            self.temp_admins.remove(admin_id)
            print(f"✅ 已移除临时管理员: {admin_id}")
            return True
        return False
        
    def add_permanent_admin(self, admin_id: str) -> bool:
        """添加常驻管理员"""
        if admin_id not in self.settings.get('permanent_admins', []):
            if 'permanent_admins' not in self.settings:
                self.settings['permanent_admins'] = []
            self.settings['permanent_admins'].append(admin_id)
            self.save_settings()
            print(f"✅ 已添加常驻管理员: {admin_id}")
            return True
        return False
        
    def remove_permanent_admin(self, admin_id: str) -> bool:
        """移除常驻管理员"""
        if admin_id in self.settings.get('permanent_admins', []):
            self.settings['permanent_admins'].remove(admin_id)
            self.save_settings()
            print(f"✅ 已移除常驻管理员: {admin_id}")
            return True
        return False
        
    def clear_temp_admins(self) -> int:
        """清除所有临时管理员"""
        count = len(self.temp_admins)
        self.temp_admins.clear()
        print(f"✅ 已清除所有临时管理员: {count}人")
        return count
    
    def set_qq_callback(self, callback):
        """设置QQ消息发送回调函数"""
        self.settings['qq_send_callback'] = callback
    
    def set_ai_instance(self, ai):
        """设置AI实例"""
        self.ai = ai
    
    def process_root_command(self, user_id: str, message: str, group_id: str = None, image_data: bytes = None) -> Optional[Tuple[str, Any]]:
        """处理Root命令"""
        if not self.is_root(user_id):
            return None
        
        message = message.strip()
        
        # 检查是否有等待处理的上传操作
        if user_id in self.pending_operations and image_data:
            op = self.pending_operations[user_id]
            if op["type"] == "image":
                result = self._save_image(op["name"], image_data)
                del self.pending_operations[user_id]
                return result
        
        # 保存图片命令 - 第一步
        if message.startswith("小天，保存图片："):
            filename = message.replace("小天，保存图片：", "").strip()
            # 记录等待上传图片
            self.pending_operations[user_id] = {"type": "image", "name": filename}
            return ("📸 请发送要保存的图片", None)
        
        
        # 设置目标群组
        if message.startswith("小天，设置目标群组："):
            groups = message.replace("小天，设置目标群组：", "").strip().split(',')
            return self._set_target_groups([g.strip() for g in groups if g.strip()])
        
        # 移除目标群组
        if message.startswith("小天，移除目标群组："):
            groups = message.replace("小天，移除目标群组：", "").strip().split(',')
            return self._remove_target_groups([g.strip() for g in groups if g.strip()])
        
        # 添加自动触发群组
        if message.startswith("小天，添加自动触发群组："):
            groups = message.replace("小天，添加自动触发群组：", "").strip().split(',')
            return self._add_auto_trigger_groups([g.strip() for g in groups if g.strip()])
        
        # 移除自动触发群组
        if message.startswith("小天，移除自动触发群组："):
            groups = message.replace("小天，移除自动触发群组：", "").strip().split(',')
            return self._remove_auto_trigger_groups([g.strip() for g in groups if g.strip()])
        
        # 设置每日触发限制
        if message.startswith("小天，设置触发限制："):
            try:
                limit = int(message.replace("小天，设置触发限制：", "").strip())
                return self._set_trigger_limit(limit)
            except ValueError:
                return ("❌ 触发限制必须是数字", None)
        
        # 重置今日触发次数
        if message == "小天，重置触发次数":
            return self._reset_trigger_count()
        
        # 设置天气城市
        if message.startswith("小天，设置天气城市："):
            city = message.replace("小天，设置天气城市：", "").strip()
            return self._set_weather_city(city)
        
        # 更换模型
        if message.startswith("小天，更换模型"):
            # 提取模型参数
            model_param = message.replace("小天，更换模型", "").strip()
            if model_param.startswith("：") or model_param.startswith(":"):
                model_param = model_param[1:].strip()
            
            return self._change_model(model_param)
        
        # 清理输出文件
        if message == "小天，清理输出":
            return self._cleanup_outputs()
        
        # 查看设置
        if message == "小天，查看设置":
            return self._show_settings()
            
        # 管理员命令
        # 添加临时管理员
        if message.startswith("小天，添加临时管理员："):
            admin_id = message.replace("小天，添加临时管理员：", "").strip()
            return self._add_temp_admin(admin_id)
            
        # 添加常驻管理员
        if message.startswith("小天，添加常驻管理员："):
            admin_id = message.replace("小天，添加常驻管理员：", "").strip()
            return self._add_permanent_admin(admin_id)
            
        # 移除临时管理员
        if message.startswith("小天，移除临时管理员："):
            admin_id = message.replace("小天，移除临时管理员：", "").strip()
            return self._remove_temp_admin(admin_id)
            
        # 移除常驻管理员
        if message.startswith("小天，移除常驻管理员："):
            admin_id = message.replace("小天，移除常驻管理员：", "").strip()
            return self._remove_permanent_admin(admin_id)
            
        # 查看管理员列表
        if message == "小天，查看管理员":
            return self._list_admins()
            
        # 题库管理命令
        # 添加题目
        if message.startswith("小天，添加题目：") and self.ai:
            content = message.replace("小天，添加题目：", "").strip()
            return self._add_quiz_question(content)
            
        # 修改题目
        if message.startswith("小天，修改题目：") and self.ai:
            content = message.replace("小天，修改题目：", "").strip()
            return self._edit_quiz_question(content)
            
        # 删除题目
        if message.startswith("小天，删除题目：") and self.ai:
            content = message.replace("小天，删除题目：", "").strip()
            return self._delete_quiz_question(content)
            
        # 查看题库
        if message == "小天，查看题库" and self.ai:
            return self._list_quiz_questions()
        
        # 启用/禁用功能
        if message.startswith("小天，启用功能："):
            feature = message.replace("小天，启用功能：", "").strip()
            return self._toggle_feature(feature, True)
        
        if message.startswith("小天，禁用功能："):
            feature = message.replace("小天，禁用功能：", "").strip()
            return self._toggle_feature(feature, False)
        
        # 列出可用图片和字体
        if message == "小天，列出图片":
            return self._list_images()
        
        if message == "小天，列出字体":
            return self._list_fonts()
        
        # 发送天气报告
        if message == "小天，发送天气":
            return ("SEND_WEATHER", None)
        
        # 发送天文海报
        if message == "小天，发送海报":
            return ("SEND_ASTRONOMY", None)
        
        # 生成月度合集
        if message == "小天，生成月度合集":
            return ("GENERATE_MONTHLY", None)
        
        # 立即执行清理
        if message == "小天，立即清理":
            return ("CLEANUP_NOW", None)
        
        # 重置用户like系统
        if message.startswith("小天，重置like系统："):
            user_key = message.replace("小天，重置like系统：", "").strip()
            return ("RESET_LIKE_SYSTEM", user_key)
        
        # 重置所有like系统
        if message == "小天，重置所有like系统":
            return ("RESET_ALL_LIKE_SYSTEMS", None)
        
        return None
    
    def _save_image(self, filename: str, image_data: bytes) -> Tuple[str, None]:
        """保存图片文件"""
        try:
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                filename += '.jpg'
            
            file_path = os.path.join(ASTRONOMY_IMAGES_DIR, filename)
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            return (f"✅ 图片已保存：{filename}", None)
        except Exception as e:
            return (f"❌ 保存图片失败：{str(e)}", None)
    
    def _set_target_groups(self, groups: List[str]) -> Tuple[str, None]:
        """添加目标群组，如果群组已存在则忽略"""
        added_groups = []
        for group in groups:
            if group not in self.settings['target_groups']:
                self.settings['target_groups'].append(group)
                added_groups.append(group)
        
        if not added_groups:
            return ("⚠️ 指定的群组已经在目标群组列表中", None)
            
        self.save_settings()
        
        # 向新添加的目标群组发送欢迎图片和文字
        if self.settings['qq_send_callback'] and self.ai and added_groups:
            try:
                # 欢迎图片路径
                welcome_image = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "welcome", "hello.png")
                # 欢迎文字
                welcome_message = "✨ 你好！我是小天，很高兴能为你服务！\n我可以提供天文知识、天气查询、天文竞答等功能，请多多关照～在群聊中输入小天就可以唤醒我啦"
                
                # 仅向新添加的群组发送欢迎消息
                for group in added_groups:
                    self._send_welcome_message_to_groups(welcome_message, welcome_image, group_id=group)
            except Exception as e:
                print(f"向新群组发送欢迎消息失败：{e}")
                pass
                
        
        return (f"✅ 目标群组已设置：{', '.join(groups)}", None)
    
    def _remove_target_groups(self, groups: List[str]) -> Tuple[str, None]:
        """移除目标群组"""
        removed_groups = []
        for group in groups:
            if group in self.settings['target_groups']:
                self.settings['target_groups'].remove(group)
                removed_groups.append(group)
                
        if removed_groups:
            self.save_settings()
            return (f"✅ 已移除目标群组：{', '.join(removed_groups)}", None)
        else:
            return ("⚠️ 未找到指定的目标群组", None)
                
    def _send_welcome_message_to_groups(self, message: str = None, image_path: str = None,group_id: str = None):
        """向目标群组发送欢迎消息和图片
        参考 MessageSender.send_message_to_groups 的实现
        """
        import os
        import time
        import random
        
        if self.settings['qq_send_callback'] and group_id:
            try:
                print(f"正在发送欢迎消息到群组 {group_id}...")
                # 处理图片路径
                wait_time = 3
                time.sleep(wait_time + random.uniform(-1, 1))
                # 先发送图片，后发送文本
                print(f"先发送图片到群组 {group_id}")
                self.settings['qq_send_callback']('group', group_id, None, image_path )
                    # 添加短暂延时，确保图片发送完成
                time.sleep(10 + random.uniform(0, 1))
                # 如果有文本消息，再发送文本
                if message:
                    print(f"再发送文本到群组 {group_id}")
                    self.settings['qq_send_callback']('group', group_id, message, None)
            except Exception as e:
                print(f"发送欢迎消息到群组 {group_id} 失败：{e}")
                # 静默处理错误
        

    
    def _add_auto_trigger_groups(self, groups: List[str]) -> Tuple[str, None]:
        """添加自动触发群组"""
        for group in groups:
            if group not in self.settings['auto_trigger_groups']:
                self.settings['auto_trigger_groups'].append(group)
        
        self.save_settings()
        return (f"✅ 已添加自动触发群组：{', '.join(groups)}", None)
    
    def _remove_auto_trigger_groups(self, groups: List[str]) -> Tuple[str, None]:
        """移除自动触发群组"""
        for group in groups:
            if group in self.settings['auto_trigger_groups']:
                self.settings['auto_trigger_groups'].remove(group)
        
        self.save_settings()
        return (f"✅ 已移除自动触发群组：{', '.join(groups)}", None)
    
    def _set_trigger_limit(self, limit: int) -> Tuple[str, None]:
        """设置触发限制"""
        self.settings['daily_trigger_limit'] = limit
        self.save_settings()
        return (f"✅ 每日触发限制已设置为：{limit}次", None)
    
    def _reset_trigger_count(self) -> Tuple[str, None]:
        """重置触发次数"""
        self.settings['today_trigger_count'] = {}
        self.save_settings()
        return ("✅ 今日触发次数已重置", None)
    
    def _set_weather_city(self, city: str) -> Tuple[str, None]:
        """设置天气城市"""
        self.settings['weather_city'] = city
        self.save_settings()
        return (f"✅ 天气城市已设置为：{city}", None)
    
    def _cleanup_outputs(self) -> Tuple[str, None]:
        """清理输出文件"""
        try:
            deleted_count = 0
            
            # 清理海报输出
            poster_files = glob.glob("xiaotian/output/posters/*")
            for file in poster_files:
                os.remove(file)
                deleted_count += 1
            
            # 清理图表输出
            chart_files = glob.glob("xiaotian/output/charts/*")
            for file in chart_files:
                os.remove(file)
                deleted_count += 1
            
            return (f"✅ 已清理 {deleted_count} 个输出文件", None)
        except Exception as e:
            return (f"❌ 清理失败：{str(e)}", None)
    
    def _show_settings(self) -> Tuple[str, None]:
        """显示当前设置"""
        settings_text = f"""📋 当前Root设置：

🎯 目标群组：{', '.join(self.settings['target_groups']) if self.settings['target_groups'] else '未设置'}
🔥 自动触发群组：{', '.join(self.settings['auto_trigger_groups']) if self.settings['auto_trigger_groups'] else '未设置'}
⚡ 每日触发限制：{self.settings['daily_trigger_limit']}次
📊 今日已触发：{sum(self.settings['today_trigger_count'].values())}次
🌤️ 天气城市：{self.settings['weather_city']}

🔧 启用的功能：
"""
        for feature, enabled in self.settings['enabled_features'].items():
            status = "✅" if enabled else "❌"
            settings_text += f"  {status} {feature}\n"
        
        return (settings_text.strip(), None)
    
    def _toggle_feature(self, feature: str, enabled: bool) -> Tuple[str, None]:
        """启用/禁用功能"""
        if feature in self.settings['enabled_features']:
            self.settings['enabled_features'][feature] = enabled
            self.save_settings()
            status = "启用" if enabled else "禁用"
            return (f"✅ 功能 {feature} 已{status}", None)
        else:
            available = ', '.join(self.settings['enabled_features'].keys())
            return (f"❌ 未知功能：{feature}\n可用功能：{available}", None)
    
    def _list_images(self) -> Tuple[str, None]:
        """列出可用图片"""
        try:
            images = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']:
                images.extend(glob.glob(os.path.join(ASTRONOMY_IMAGES_DIR, ext)))
            
            if images:
                image_names = [os.path.basename(img) for img in images]
                return (f"📸 可用图片：\n{chr(10).join(image_names)}", None)
            else:
                return ("📸 暂无可用图片", None)
        except Exception as e:
            return (f"❌ 列出图片失败：{str(e)}", None)
    
    def _list_fonts(self) -> Tuple[str, None]:
        """列出可用字体"""
        try:
            fonts = []
            for ext in ['*.ttf', '*.otf', '*.woff', '*.woff2']:
                fonts.extend(glob.glob(os.path.join(ASTRONOMY_FONTS_DIR, ext)))
            
            if fonts:
                font_names = [os.path.basename(font) for font in fonts]
                return (f"🔤 可用字体：\n{chr(10).join(font_names)}", None)
            else:
                return ("🔤 暂无可用字体", None)
        except Exception as e:
            return (f"❌ 列出字体失败：{str(e)}", None)
    
    def can_auto_trigger(self, group_id: str) -> bool:
        """检查是否可以在指定群组自动触发"""
        if not self.settings['enabled_features'].get('auto_trigger', True):
            return False
        
        if group_id not in self.settings['auto_trigger_groups']:
            return False
        
        # 检查日期，如果是新的一天则重置计数
        today = datetime.now().strftime('%Y-%m-%d')
        if self.settings['last_trigger_date'] != today:
            self.settings['today_trigger_count'] = {}
            self.settings['last_trigger_date'] = today
            self.save_settings()
        
        # 检查今日在该群的触发次数
        group_count = self.settings['today_trigger_count'].get(group_id, 0)
        return group_count < self.settings['daily_trigger_limit']
    
    def record_auto_trigger(self, group_id: str):
        """记录自动触发"""
        today = datetime.now().strftime('%Y-%m-%d')
        if self.settings['last_trigger_date'] != today:
            self.settings['today_trigger_count'] = {}
            self.settings['last_trigger_date'] = today
        
        self.settings['today_trigger_count'][group_id] = self.settings['today_trigger_count'].get(group_id, 0) + 1
        self.save_settings()
    
    def is_feature_enabled(self, feature: str) -> bool:
        """检查功能是否启用"""
        return self.settings['enabled_features'].get(feature, True)
    
    def _change_model(self, model_param: str) -> Tuple[str, Any]:
        """更换AI模型"""
        # 模型映射表
        model_mapping = {
            'k1': 'moonshot-v1-8k',
            'k2': 'kimi-k2-0711-preview',
        }
        
        if not model_param:
            # 显示当前模型和可用选项
            current_model = self.ai.current_model if self.ai else "未知"
            available_models = ', '.join([f"{k}({v})" for k, v in model_mapping.items()])
            return (f"📋 当前模型: {current_model}\n\n可用快捷指令:\n{available_models}\n\n或直接输入完整模型名", None)
        
        if not self.ai:
            return ("❌ AI实例未初始化，无法更换模型", None)
        
        # 检查是否是快捷指令
        if model_param.lower() in model_mapping:
            target_model = model_mapping[model_param.lower()]
            model_name = model_param.lower()
        else:
            # 直接使用输入的模型名
            target_model = model_param
            model_name = model_param
        
        try:
            # 使用AI实例的动态更换功能
            result = self.ai.change_model(target_model)
            
            # 同时更新配置文件以便下次重启时生效
            config_path = os.path.join(os.path.dirname(__file__), 'config.py')
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找并替换USE_MODEL行
            pattern = r'USE_MODEL\s*=\s*["\'][^"\']*["\']'
            new_line = f'USE_MODEL = "{target_model}"'
            
            if re.search(pattern, content):
                new_content = re.sub(pattern, new_line, content)
                
                # 写回文件
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                return (f"🚀 {result}\n快捷指令: {model_name}\n📝 配置文件已同步更新", None)
            else:
                return (f"🚀 {result}\n快捷指令: {model_name}\n⚠️ 配置文件更新失败，但当前会话已生效", None)
                
        except Exception as e:
            return (f"❌ 更换模型失败: {str(e)}", None)
    
    def get_weather_city(self) -> str:
        """获取天气城市"""
        return self.settings['weather_city']

    def get_target_groups(self) -> List[str]:
        """获取目标群组"""
        return self.settings['target_groups']
        
    # 管理员相关命令处理
    def _add_temp_admin(self, admin_id: str) -> Tuple[str, Any]:
        """添加临时管理员"""
        try:
            if not admin_id or not admin_id.strip().isdigit():
                return ("❌ 无效的QQ号！", None)
            
            admin_id = admin_id.strip()
            if self.add_temp_admin(admin_id):
                return (f"✅ 已添加临时管理员: {admin_id}", None)
            else:
                return (f"⚠️ {admin_id} 已经是临时管理员", None)
        except Exception as e:
            return (f"❌ 添加临时管理员失败: {str(e)}", None)
    
    def _add_permanent_admin(self, admin_id: str) -> Tuple[str, Any]:
        """添加常驻管理员"""
        try:
            if not admin_id or not admin_id.strip().isdigit():
                return ("❌ 无效的QQ号！", None)
            
            admin_id = admin_id.strip()
            if self.add_permanent_admin(admin_id):
                return (f"✅ 已添加常驻管理员: {admin_id}", None)
            else:
                return (f"⚠️ {admin_id} 已经是常驻管理员", None)
        except Exception as e:
            return (f"❌ 添加常驻管理员失败: {str(e)}", None)
    
    def _remove_temp_admin(self, admin_id: str) -> Tuple[str, Any]:
        """移除临时管理员"""
        try:
            if not admin_id or not admin_id.strip().isdigit():
                return ("❌ 无效的QQ号！", None)
            
            admin_id = admin_id.strip()
            if self.remove_temp_admin(admin_id):
                return (f"✅ 已移除临时管理员: {admin_id}", None)
            else:
                return (f"⚠️ {admin_id} 不是临时管理员", None)
        except Exception as e:
            return (f"❌ 移除临时管理员失败: {str(e)}", None)
    
    def _remove_permanent_admin(self, admin_id: str) -> Tuple[str, Any]:
        """移除常驻管理员"""
        try:
            if not admin_id or not admin_id.strip().isdigit():
                return ("❌ 无效的QQ号！", None)
            
            admin_id = admin_id.strip()
            if self.remove_permanent_admin(admin_id):
                return (f"✅ 已移除常驻管理员: {admin_id}", None)
            else:
                return (f"⚠️ {admin_id} 不是常驻管理员", None)
        except Exception as e:
            return (f"❌ 移除常驻管理员失败: {str(e)}", None)
    
    def _list_admins(self) -> Tuple[str, Any]:
        """列出所有管理员"""
        try:
            temp_admins = self.temp_admins
            permanent_admins = self.settings.get('permanent_admins', [])
            
            result = "🔑 管理员列表：\n"
            
            if permanent_admins:
                result += "📌 常驻管理员：\n"
                for admin in permanent_admins:
                    result += f" - {admin}\n"
            else:
                result += "📌 常驻管理员：无\n"
            
            if temp_admins:
                result += "⏱️ 临时管理员：\n"
                for admin in temp_admins:
                    result += f" - {admin}\n"
            else:
                result += "⏱️ 临时管理员：无\n"
            
            return (result.strip(), None)
        except Exception as e:
            return (f"❌ 获取管理员列表失败: {str(e)}", None)
            
    # 题库管理相关命令处理
    def _add_quiz_question(self, content: str) -> Tuple[str, Any]:
        """添加题目到竞答题库"""
        try:
            if not content.strip():
                return ("❌ 题目内容不能为空！", None)
            
            # 解析用户输入
            question_data = self._parse_question_from_text(content)
            if not question_data:
                return ("❌ 无法解析题目内容！请使用正确的格式。\n选择题例如：题目：太阳系中最大的行星是？\n选项：A:木星 B:土星 C:天王星 D:海王星\n答案：A\n难度：1\n\n填空题例如：题目：人类首次载人登月的区域是？\n答案：静海\n难度：2", None)
            
            # 添加到JSON文件
            result = self._add_question_to_json(question_data)
            return (f"✅ {result}", None)
        except Exception as e:
            return (f"❌ 添加题目失败: {str(e)}", None)
    
    def _parse_question_from_text(self, text: str) -> Optional[dict]:
        """解析用户输入的题目格式"""
        try:
            lines = text.strip().split('\n')
            question_data = {
                "difficulty": "normal",
                "reference": ""
            }
            
            has_options = False
            
            for line in lines:
                if "：" in line or ":" in line:
                    key, value = line.replace("：", ":").split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key in ["题目", "问题"]:
                        question_data["question"] = value
                    elif key in ["选项"]:
                        has_options = True
                        # 解析选项格式：A:选项1 B:选项2 C:选项3 D:选项4
                        options = []
                        # 按字母分割选项
                        pattern = r'([A-E]):([^A-E]*?)(?=[A-E]:|$)'
                        matches = re.findall(pattern, value.upper())
                        
                        if matches:
                            # 按字母顺序排序
                            sorted_matches = sorted(matches, key=lambda x: x[0])
                            options = [match[1].strip() for match in sorted_matches]
                        
                        if len(options) >= 2:
                            question_data["options"] = options
                            question_data["type"] = "multiple_choice"
                        else:
                            return None
                    elif key in ["答案"]:
                        if has_options:
                            # 选择题：答案为字母
                            if value.upper() in "ABCDE":
                                question_data["correct"] = ord(value.upper()) - ord('A')
                            else:
                                return None
                        else:
                            # 填空题：答案为文本
                            question_data["answer"] = value
                            question_data["type"] = "fill_blank"
                    elif key in ["难度"]:
                        if value in ["1", "简单", "easy"]:
                            question_data["difficulty"] = "easy"
                        elif value in ["2", "普通", "normal", "一般"]:
                            question_data["difficulty"] = "normal"
                        elif value in ["3", "困难", "difficult", "hard"]:
                            question_data["difficulty"] = "difficult"
                    elif key in ["参考", "reference"]:
                        question_data["reference"] = value
            
            # 检查必要字段
            if "question" not in question_data:
                return None
                
            if has_options:
                # 选择题：需要选项和正确答案索引
                if "options" not in question_data or "correct" not in question_data:
                    return None
                # 验证答案索引不超过选项数量
                if question_data["correct"] >= len(question_data["options"]):
                    return None
            else:
                # 填空题：需要答案文本
                if "answer" not in question_data:
                    return None
                question_data["type"] = "fill_blank"
                
            return question_data
        except Exception:
            return None
    
    def _add_question_to_json(self, question_data: dict) -> str:
        """添加题目到JSON文件"""
        try:
            # 获取JSON文件路径（上上级目录下的data目录）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)  # xiaotian目录
            grandparent_dir = os.path.dirname(parent_dir)  # xiaotian目录
            json_path = os.path.join(grandparent_dir, "data", "astronomy_quiz.json")
            
            # 确保data目录存在
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            
            # 读取现有数据
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
            else:
                questions = []
            
            # 添加新题目
            questions.append(question_data)
            
            # 写回文件
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(questions, f, ensure_ascii=False, indent=2)
            
            return f"题目已添加到题库，当前共有 {len(questions)} 道题目"
        except Exception as e:
            raise Exception(f"写入JSON文件失败: {str(e)}")
    
    def _edit_quiz_question(self, content: str) -> Tuple[str, Any]:
        """修改竞答题库中的题目"""
        try:
            if not content.strip():
                return ("❌ 请提供要修改的题目关键词和新的内容！", None)
            
            # 解析输入，格式：关键词：xxx\n题目：新内容...
            parts = content.strip().split('\n', 1)
            if len(parts) != 2:
                return ("❌ 格式错误！请使用格式：\n关键词：xxx\n题目：新题目内容\n选项：...\n答案：...", None)
            
            keyword = parts[0].replace("关键词：", "").replace("关键字：", "").strip()
            new_content = parts[1].strip()
            
            if not keyword or not new_content:
                return ("❌ 关键词和新内容不能为空！", None)
            
            # 解析新题目内容
            new_question_data = self._parse_question_from_text(new_content)
            if not new_question_data:
                return ("❌ 无法解析新的题目内容！", None)
            
            # 修改JSON文件中的题目
            result = self._edit_question_in_json(keyword, new_question_data)
            return (f"✅ {result}", None)
        except Exception as e:
            return (f"❌ 修改题目失败: {str(e)}", None)
    
    def _edit_question_in_json(self, keyword: str, new_question_data: dict) -> str:
        """修改JSON文件中的题目"""
        try:
            # 获取JSON文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            grandparent_dir = os.path.dirname(parent_dir)
            json_path = os.path.join(grandparent_dir, "data", "astronomy_quiz.json")
            
            if not os.path.exists(json_path):
                return "题库文件不存在"
            
            # 读取现有数据
            with open(json_path, 'r', encoding='utf-8') as f:
                questions = json.load(f)
            
            # 查找匹配的题目
            found = False
            for i, question in enumerate(questions):
                if keyword.lower() in question.get("question", "").lower():
                    questions[i] = new_question_data
                    found = True
                    break
            
            if not found:
                return f"未找到包含关键词 '{keyword}' 的题目"
            
            # 写回文件
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(questions, f, ensure_ascii=False, indent=2)
            
            return f"题目已修改，当前共有 {len(questions)} 道题目"
        except Exception as e:
            raise Exception(f"修改JSON文件失败: {str(e)}")
    
    def _delete_quiz_question(self, content: str) -> Tuple[str, Any]:
        """从竞答题库中删除题目"""
        try:
            keyword = content.strip()
            if not keyword:
                return ("❌ 请提供要删除的题目关键词！", None)
            
            # 从JSON文件中删除题目
            result = self._delete_question_from_json(keyword)
            return (f"✅ {result}", None)
        except Exception as e:
            return (f"❌ 删除题目失败: {str(e)}", None)
    
    def _delete_question_from_json(self, keyword: str) -> str:
        """从JSON文件中删除题目"""
        try:
            # 获取JSON文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            grandparent_dir = os.path.dirname(parent_dir)
            json_path = os.path.join(grandparent_dir, "data", "astronomy_quiz.json")
            
            if not os.path.exists(json_path):
                return "题库文件不存在"
            
            # 读取现有数据
            with open(json_path, 'r', encoding='utf-8') as f:
                questions = json.load(f)
            
            # 查找并删除匹配的题目
            original_count = len(questions)
            questions = [q for q in questions if keyword.lower() not in q.get("question", "").lower()]
            deleted_count = original_count - len(questions)
            
            if deleted_count == 0:
                return f"未找到包含关键词 '{keyword}' 的题目"
            
            # 写回文件
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(questions, f, ensure_ascii=False, indent=2)
            
            return f"已删除 {deleted_count} 道题目，当前共有 {len(questions)} 道题目"
        except Exception as e:
            raise Exception(f"删除JSON文件失败: {str(e)}")
    
    def _list_quiz_questions(self) -> Tuple[str, Any]:
        """列出题库中的题目"""
        try:
            quiz = None
            
            if hasattr(self.ai, 'astronomy_quiz'):
                quiz = self.ai.astronomy_quiz
            
            if not quiz:
                # 导入需要的类
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from xiaotian.tools.astronomy_quiz import AstronomyQuiz
                quiz = AstronomyQuiz(self, self.ai)
            
            # 获取题目统计
            stats = quiz.get_question_bank_stats()
            return (f"📊 {stats}", None)
        except Exception as e:
            return (f"❌ 获取题库统计失败: {str(e)}", None)