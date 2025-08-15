"""
小天的Root超级管理员模块
负责处理Root用户的所有高级管理功能
"""

import os
import json
import shutil
import base64
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
    
    def is_root(self, user_id: str) -> bool:
        """检查是否是Root用户"""
        return user_id == self.root_id
    
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
        
        # 查看用户like状态
        if message.startswith("小天，查看like状态："):
            user_key = message.replace("小天，查看like状态：", "").strip()
            return ("CHECK_LIKE_STATUS", user_key)
        
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
        """设置目标群组"""
        self.settings['target_groups'] = groups
        self.save_settings()
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
            return ("⚠️ 指定的群组不在目标群组列表中", None)
    
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
            'k2': 'kimi-k2-0711-preview',
            'k1': 'moonshot-v1-8k',
            'kimi': 'kimi-k2-0711-preview',
            'moonshot': 'moonshot-v1-8k',
            'v1-8k': 'moonshot-v1-8k',
            'v1-32k': 'moonshot-v1-32k',
            'v1-128k': 'moonshot-v1-128k'
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
            import re
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