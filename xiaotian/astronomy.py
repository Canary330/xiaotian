"""
小天的天文海报功能模块
负责处理每日天文海报的生成和管理
"""

import os
import re
import calendar
import datetime
import time
from typing import Tuple, List, Dict, Optional, Union
import textwrap
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

from .config import (
    POSTER_OUTPUT_DIR, ASTRONOMY_IMAGES_DIR, ASTRONOMY_FONTS_DIR,
    DEFAULT_FONT, TITLE_FONT, ARTISTIC_FONT, DATE_FONT
)
from .ai_core import XiaotianAI


class AstronomyPoster:
    def __init__(self, base_path="xiaotian"):
        self.base_path = base_path
        self.images_path = ASTRONOMY_IMAGES_DIR
        self.fonts_path = ASTRONOMY_FONTS_DIR
        self.output_path = POSTER_OUTPUT_DIR
        self.ai_client = XiaotianAI()  # 初始化AI客户端
        
        # Ensure directories exist
        os.makedirs(self.images_path, exist_ok=True)
        os.makedirs(self.fonts_path, exist_ok=True)
        os.makedirs(self.output_path, exist_ok=True)
        
        # 用于等待用户图片的缓存
        self.waiting_for_images = False
        self.waiting_start_time = None
        self.waiting_user_id = None  # 记录等待的用户ID
        self.waiting_group_id = None  # 记录等待的群组ID（如果是群聊）
        self.user_images = []
        self.max_images = 2
        
        # 保存最新的AI点评，供定时任务使用
        self.latest_ai_comment = None
    
    def process_astronomy_content(self, content: str, user_id: str = None, group_id: str = None, ai_optimizer=None) -> Tuple[str, str]:
        """处理天文内容并创建海报"""
        # 提取触发短语后的内容
        match = re.search(r"小天，每日天文做好啦：([\s\S]*)", content)
        if not match:
            return None, "未找到正确格式的内容"
        
        astronomy_text = match.group(1).strip()
        char_count = len(astronomy_text)
        
        if 300 <= char_count <= 600:
            # 字数符合要求，开始等待用户图片
            self.astronomy_text = astronomy_text
            self.waiting_for_images = True
            self.waiting_start_time = time.time()
            self.waiting_user_id = user_id
            self.waiting_group_id = group_id
            self.user_images = []
            
            # 生成AI点评
            comment_prompt = f"请根据以下天文内容，生成一段100字以内的点评，风格可以是有趣、富有启发性或引人深思的：\n\n{astronomy_text}"
            try:
                ai_comment = self.ai_client.get_response(comment_prompt, user_id="system")
                self.latest_ai_comment = ai_comment  # 保存AI点评供定时任务使用
            except Exception as e:
                print(f"AI点评生成失败: {e}")
                ai_comment = "宇宙的奥秘总是令人着迷，每一次天文观测都是对未知世界的探索。"
                self.latest_ai_comment = ai_comment
            
            return None, f"内容已接收（{char_count}字），将在1分钟内等待图片，如需添加图片请直接发送（最多2张），或回复\"立即生成\"立即生成海报。\n\n小天点评：{ai_comment}"
        elif char_count > 100:
            # 需要调整字数，但也开始等待用户图片
            if ai_optimizer:
                try:
                    # 使用AI工具调整字数
                    optimized_text = ai_optimizer(astronomy_text)
                    self.astronomy_text = optimized_text
                    self.waiting_for_images = True
                    self.waiting_start_time = time.time()
                    self.waiting_user_id = user_id
                    self.waiting_group_id = group_id
                    self.user_images = []
                    
                    # 生成AI点评
                    comment_prompt = f"请根据以下天文内容，生成一段100字以内的点评，风格可以是有趣、富有启发性或引人深思的：\n\n{optimized_text}"
                    try:
                        ai_comment = self.ai_client.get_response(comment_prompt, user_id="system")
                        self.latest_ai_comment = ai_comment  # 保存AI点评供定时任务使用
                    except Exception as e:
                        print(f"AI点评生成失败: {e}")
                        ai_comment = "宇宙的奥秘总是令人着迷，每一次天文观测都是对未知世界的探索。"
                        self.latest_ai_comment = ai_comment
                    
                    return None, f"内容已优化（原{char_count}字，现{len(optimized_text)}字），将在1分钟内等待图片，如需添加图片请直接发送（最多2张），或回复\"不需要图片\"立即生成海报。\n\n小天点评：{ai_comment}"
                except Exception as e:
                    # AI优化失败，使用原文等待图片
                    self.astronomy_text = astronomy_text
                    self.waiting_for_images = True
                    self.waiting_start_time = time.time()
                    self.waiting_user_id = user_id
                    self.waiting_group_id = group_id
                    self.user_images = []
                    
                    # 生成AI点评
                    comment_prompt = f"请根据以下天文内容，生成一段100字以内的点评，风格可以是有趣、富有启发性或引人深思的：\n\n{astronomy_text}"
                    try:
                        ai_comment = self.ai_client.get_response(comment_prompt, user_id="system")
                        self.latest_ai_comment = ai_comment  # 保存AI点评供定时任务使用
                    except Exception as e:
                        print(f"AI点评生成失败: {e}")
                        ai_comment = "宇宙的奥秘总是令人着迷，每一次天文观测都是对未知世界的探索。"
                        self.latest_ai_comment = ai_comment
                    
                    return None, f"内容已接收（{char_count}字），将在1分钟内等待图片，如需添加图片请直接发送（最多2张），或回复\"不需要图片\"立即生成海报。\n\n小天点评：{ai_comment}"
            else:
                # 没有提供AI优化器，使用原文等待图片
                self.astronomy_text = astronomy_text
                self.waiting_for_images = True
                self.waiting_start_time = time.time()
                self.waiting_user_id = user_id
                self.waiting_group_id = group_id
                self.user_images = []
                
                # 生成AI点评
                comment_prompt = f"请根据以下天文内容，生成一段100字以内的点评，风格可以是有趣、富有启发性或引人深思的：\n\n{astronomy_text}"
                try:
                    ai_comment = self.ai_client.get_response(comment_prompt, user_id="system")
                    self.latest_ai_comment = ai_comment  # 保存AI点评供定时任务使用
                except Exception as e:
                    print(f"AI点评生成失败: {e}")
                    ai_comment = "宇宙的奥秘总是令人着迷，每一次天文观测都是对未知世界的探索。"
                    self.latest_ai_comment = ai_comment
                
                return None, f"内容已接收（{char_count}字），将在1分钟内等待图片，如需添加图片请直接发送（最多2张），或回复\"不需要图片\"立即生成海报。\n\n小天点评：{ai_comment}"
        else:
            # 内容过短
            return None, f"内容太短，无法生成海报。需要至少100字，当前: {char_count}字"
    
    def process_user_message(self, message: str, image_paths: List[str] = None) -> Tuple[Optional[str], str]:
        """处理用户消息，可能包含图片或终止等待的指令"""
        # 如果没有在等待图片，直接跳过
        if not self.waiting_for_images:
            return None, ""
        
        # 检查是否有终止等待的指令
        if message and ("不需要图片" in message or "立即生成" in message or "直接生成" in message):
            self.waiting_for_images = False
            poster_path = self.create_poster(self.astronomy_text, self.user_images)
            return poster_path, "海报已生成"
        
        # 处理用户发送的图片
        if image_paths and len(image_paths) > 0:
            # 添加新图片到用户图片列表
            for path in image_paths:
                if len(self.user_images) < self.max_images:
                    self.user_images.append(path)
            
            remaining_slots = self.max_images - len(self.user_images)
            
            if remaining_slots > 0:
                return None, f"已接收{len(self.user_images)}张图片，还可以再添加{remaining_slots}张。等待中..."
            else:
                # 图片数量已达上限，直接生成海报
                self.waiting_for_images = False
                poster_path = self.create_poster(self.astronomy_text, self.user_images)
                return poster_path, "已达到图片上限，海报已生成"
        
        # 检查等待时间是否已到
        if time.time() - self.waiting_start_time > 60:  # 60秒等待时间
            self.waiting_for_images = False
            poster_path = self.create_poster(self.astronomy_text, self.user_images)
            return poster_path, "等待图片超时，使用现有内容生成海报"
        
        # 继续等待
        return None, ""
    
    def check_waiting_status(self) -> Tuple[bool, int, Optional[str], str]:
        """检查等待状态，返回(是否在等待, 剩余秒数, 海报路径, 消息)"""
        if not self.waiting_for_images:
            return False, 0, None, ""
            
        elapsed = time.time() - self.waiting_start_time
        remaining = max(0, 60 - elapsed)  # 60秒等待时间
        
        # 如果时间到了，自动结束等待并生成海报
        if remaining <= 0:
            self.waiting_for_images = False
            try:
                poster_path = self.create_poster(self.astronomy_text, self.user_images)
                # 返回海报路径，但不返回提示消息（由调用方决定如何处理）
                return False, 0, poster_path, ""
            except Exception as e:
                print(f"自动生成海报失败: {e}")
                return False, 0, None, f"等待图片超时，自动生成海报失败: {str(e)}"
            
        return True, int(remaining), None, ""
    
    def create_poster(self, text: str, user_images: List[str] = None) -> str:
        """创建天文海报，使用当月对应的图片
        
        Args:
            text: 海报文字内容
            user_images: 用户提供的图片路径列表，最多两张
        """
        today = datetime.datetime.now()
        month = today.month
        date_str = today.strftime("%Y年%m月%d日")
        
        # 获取当月图片
        image_path = os.path.join(self.images_path, f"{month}.jpg")
        if not os.path.exists(image_path):
            # 使用默认图片
            image_path = os.path.join(self.images_path, "default.jpg")
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"无法找到月份图片 {month}.jpg 或默认图片")
        
        # 加载图片
        img = Image.open(image_path).convert("RGBA")
        
        # 调整大小（标准海报尺寸）
        img = img.resize((1200, 1800))
        
        # 创建绘图上下文
        draw = ImageDraw.Draw(img)
        
        # 加载字体（从全局配置）
        try:
            print("加载字体（从配置）")
            
            # 使用全局配置中的字体路径
            text_font_path = DEFAULT_FONT
            title_font_path = TITLE_FONT
            artistic_font_path = ARTISTIC_FONT
            
            # 首先尝试加载默认字体，用于基本文本（缩小字体）
            try:
                text_font = ImageFont.truetype(text_font_path, 32)  # 缩小正文字号
                print(f"成功加载默認字体: {text_font_path}")
            except Exception:
                text_font = ImageFont.load_default()
                print("默认字体加载失败，使用系统默认字体")
            
            # 尝试加载标题字体（增大字号）
            try:
                title_font = ImageFont.truetype(title_font_path, 110)  # 放大标题字号
                print(f"成功加载标题字体: {title_font_path}")
            except Exception:
                title_font = text_font.font_variant(size=110)
                print("标题字体加载失败，使用默认字体代替")
            
            # 尝试加载艺术字体
            try:
                date_font = ImageFont.truetype(artistic_font_path, 35) # 适中的页脚字号
                print(f"成功加载艺术字体: {artistic_font_path}")
            except Exception:
                date_font = text_font.font_variant(size=35)
                print("艺术字体加载失败，使用默认字体代替")
            
            # 尝试加载时间专用字体
            try:
                time_display_font = ImageFont.truetype(DATE_FONT, 47)  # 时间显示专用字体
                print(f"成功加载时间字体: {DATE_FONT}")
            except Exception:
                time_display_font = text_font.font_variant(size=47)
                print("时间字体加载失败，使用默认字体代替")
                
        except Exception as e:
            print(f"加载字体失败: {str(e)}")
            import traceback
            print(traceback.format_exc())
            # 退回到默认字体
            title_font = ImageFont.load_default()
            date_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
            time_display_font = ImageFont.load_default()
            print("使用默认字体")
        
        # 添加半透明遮罩，让文字更易读
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 180))
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)
        
        # 添加标题，放大字号
        title_font_large = ImageFont.truetype(title_font_path, 110) if 'title_font_path' in locals() else title_font
        draw.text((600, 120), "每日天文", fill=(255, 255, 255, 255), font=title_font_large, anchor="mm")
        
        # 在右上角添加正方形的日期框（纵向排列）- 优化版本
        date_box_size = 180  # 进一步放大正方形边长
        date_box_x = img.width - date_box_size - 135  # 进一步向左移动，距右边界100px
        date_box_y = 30  # 距上边界30px
        
        # 绘制半透明白色背景框
        draw.rectangle(
            [(date_box_x, date_box_y), 
             (date_box_x + date_box_size, date_box_y + date_box_size)],
            fill=None,  # 去掉白色背景
            outline=(255, 255, 255, 255),  # 保留白色边框
            width=10
        )
        
        # 在框内纵向排列年月日
        year_str = today.strftime("%Y")
        month_str = today.strftime("%m月")
        day_str = today.strftime("%d日")
        
        # 使用时间专用字体，加粗放大
        date_font_bold = time_display_font if 'time_display_font' in locals() else date_font.font_variant(size=200)
        
        # 计算位置 - 年份竖排在左边，月日在右边中间
        date_center_x = date_box_x + date_box_size // 2
        
        # 年份竖排位置 - 在框的左边
        year_x = date_box_x + 30  # 距离左边框25px
        year_start_y = date_box_y + 30  # 起始位置
        
        # 月日在右边剩余空间的中间
        right_center_x = date_box_x + date_box_size // 2 + 30  # 右边区域中心
        month_y = date_box_y + 60
        day_y = date_box_y + 110
        
        # 绘制年份（竖排）
        color = '#7FBCDE'
        year_chars = list(year_str)  # 将年份拆分为单个字符
        for i, char in enumerate(year_chars):
            char_y = year_start_y + i * 38  # 每个字符间距35px
            # 更多偏移组合实现更粗的加粗效果
            for offset in [(0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1), (-1, -1), (1, -1), (-1, 1)]:
                draw.text((year_x + offset[0], char_y + offset[1]), char, fill='#FFFFFF', font=date_font_bold, anchor="mm")
        
        # 绘制年份与月日之间的分割线（白色竖直线）
        line_x = (date_box_x + date_box_size // 2) - 32  # 在方框中间位置
        line_start_y = date_box_y + 15  # 距离上边框15px
        line_end_y = date_box_y + date_box_size - 15  # 距离下边框15px
        draw.line([(line_x, line_start_y), (line_x, line_end_y)], fill=(255, 255, 255, 255), width=5)
        
        # 绘制月日（右边中间）
        # 更多偏移组合实现更粗的加粗效果
        for offset in [(0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1), (-1, -1), (1, -1), (-1, 1)]:
            draw.text((right_center_x + offset[0], month_y + offset[1]), month_str, fill=color, font=date_font_bold, anchor="mm")
            draw.text((right_center_x + offset[0], day_y + offset[1]), day_str, fill=color, font=date_font_bold, anchor="mm")
        # 处理文本，保留用户的换行符（正文往上移动）
        paragraphs = text.split('\n')
        y_position = 240  # 上移正文位置，缩小与标题间距
        text_width = img.width - 300  # 左右各留150px边距
        max_y_position = 1300  # 为用户图片和页脚留出更多空间
        for paragraph in paragraphs:
            # 检查用户是否已经首行缩进
            if paragraph.startswith("　　"):  # 判断是否以全角空格开头
                indented_paragraph = paragraph
            else:
                # 每个段落首行缩进两个字符，同时预处理负号和加号
                cleaned_paragraph = paragraph.replace('-', '负').replace('+', '')
                indented_paragraph = "　　" + cleaned_paragraph  # 使用全角空格进行缩进
            # 对每个段落进行自动换行
            lines = textwrap.wrap(indented_paragraph, width=28)  # 减小宽度以适应全角空格缩进
            
            # 处理每一行
            for i, line in enumerate(lines):
                # 计算文本宽度来实现居中
                try:
                    text_size = draw.textlength(line, font=text_font)
                    x_position = (img.width - text_size) / 2
                except AttributeError:
                    # 如果textlength方法不可用（旧版PIL），使用固定位置
                    x_position = 150
                
                # 绘制文本及其阴影，提高可读性
                draw.text((x_position+2, y_position+2), line, fill=(0, 0, 0, 180), font=text_font)  # 阴影
                draw.text((x_position, y_position), line, fill=(255, 255, 255, 255), font=text_font)  # 文本
                
                y_position += 55  # 缩小行距
                if y_position > max_y_position:  # 防止文字溢出
                    draw.text((img.width/2, y_position), "...(内容过长)", fill=(255, 255, 255, 255), font=text_font, anchor="mt")
                    y_position += 55  # 为省略号腾出空间
                    break
            
            # 段落间额外添加一行间距
            y_position += 15  # 缩小段落间距
            if y_position > max_y_position:
                break
        
        # 处理用户图片（智能调整大小避免与页脚重合）
        if user_images and len(user_images) > 0:
            # 计算图片区域，确保不与页脚重合
            image_y_position = y_position + 40  # 在文字下方留出一定空间
            footer_y_position = 1630  # 页脚位置
            available_height = footer_y_position - image_y_position - 40  # 留出与页脚的间距
            image_height = min(280, available_height)  # 动态调整图片高度
            
            # 处理用户提供的图片（最多两张）
            valid_images = []
            for img_path in user_images[:self.max_images]:
                try:
                    user_img = Image.open(img_path)
                    valid_images.append(user_img)
                except Exception as e:
                    print(f"无法加载用户图片 {img_path}: {e}")
            
            if len(valid_images) == 1:
                # 单张图片居中放置
                user_img = valid_images[0]
                
                # 保持宽高比，调整大小
                img_width = 600  # 单张图片宽度
                img_height = int(user_img.height * (img_width / user_img.width))
                if img_height > image_height:
                    img_height = image_height
                    img_width = int(user_img.width * (img_height / user_img.height))
                
                user_img = user_img.resize((img_width, img_height))
                
                # 计算居中位置
                paste_x = (img.width - img_width) // 2
                paste_y = image_y_position
                
                # 将用户图片粘贴到主图上
                if user_img.mode == 'RGBA':
                    img.paste(user_img, (paste_x, paste_y), user_img)
                else:
                    img.paste(user_img, (paste_x, paste_y))
                
            elif len(valid_images) == 2:
                # 两张图片左右放置
                img_width = 450  # 双图模式下每张图片宽度
                
                for i, user_img in enumerate(valid_images):
                    # 保持宽高比，调整大小
                    img_height = int(user_img.height * (img_width / user_img.width))
                    if img_height > image_height:
                        img_height = image_height
                        img_width = int(user_img.width * (img_height / user_img.height))
                    
                    user_img = user_img.resize((img_width, img_height))
                    
                    # 计算放置位置
                    if i == 0:  # 左侧图片
                        paste_x = (img.width // 2) - img_width - 50
                    else:  # 右侧图片
                        paste_x = (img.width // 2) + 50
                    
                    paste_y = image_y_position
                    
                    # 将用户图片粘贴到主图上
                    if user_img.mode == 'RGBA':
                        img.paste(user_img, (paste_x, paste_y), user_img)
                    else:
                        img.paste(user_img, (paste_x, paste_y))
        
        # 添加页脚（调用AI生成格言，缩小字号并下移）
        try:
            # 调用AI生成格言
            motto_prompt = "请生成一句关于天文观测或宇宙探索的励志格言，要求简洁有力，15字以内，体现天文的浪漫与科学精神。"
            ai_motto = self.ai_client.get_response(motto_prompt, user_id="system")
            # 清理可能的多余内容，只保留格言本身
            if "：" in ai_motto:
                ai_motto = ai_motto.split("：")[-1].strip()
            if '"' in ai_motto:
                ai_motto = ai_motto.replace('"', "").replace('"', "").strip()
            footer_text = f"小天 · {ai_motto}"
        except Exception as e:
            print(f"AI格言生成失败: {e}")
            footer_text = "小天 · 喵喵喵"
        
        # 使用较小字号的页脚字体
        footer_font = ImageFont.truetype(artistic_font_path, 28) if 'artistic_font_path' in locals() else date_font.font_variant(size=28)
        draw.text((600, 1650), footer_text, fill=(180, 180, 255, 255), font=footer_font, anchor="mm")
        
        # 添加logo图片到左上角，确保在最顶层
        logo_path = os.path.join(self.images_path, "logo.png")
        if os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                # 调整logo大小为固定尺寸，和日期框一样大
                date_box_size = 180  # 和后面日期框的大小保持一致
                logo = logo.resize((date_box_size, date_box_size), Image.Resampling.LANCZOS)
                
                
                # 计算logo位置（左上角，和日期框对称）
                logo_x = 135  # 距左边135px，和日期框的右边距对称
                logo_y = 30  # 距上边30px，和日期框一样
                
                # 粘贴logo到主图上（在最顶层）
                img.paste(logo, (logo_x, logo_y), logo)
                print(f"成功添加顶层logo: {logo_path}")
            except Exception as e:
                print(f"添加logo失败: {e}")
        else:
            print(f"Logo文件不存在: {logo_path}")
        
        # 保存海报
        output_filename = f"astronomy_{today.strftime('%Y%m%d')}.png"
        output_path = os.path.join(self.output_path, output_filename)
        img = img.convert("RGB")
        img.save(output_path)
        
        return output_path
        
    def create_monthly_collection(self) -> Optional[str]:
        """创建上个月所有天文海报的合集"""
        today = datetime.datetime.now()
        first_day = datetime.datetime(today.year, today.month, 1)
        last_month = (first_day - datetime.timedelta(days=1))
        year_month = last_month.strftime("%Y%m")
        
        # 获取上个月的所有海报
        posters = []
        for file in os.listdir(self.output_path):
            if file.startswith(f"astronomy_{year_month}") and file.endswith(".png"):
                posters.append(os.path.join(self.output_path, file))
        
        if not posters:
            return None
        
        # 创建海报网格（最多3x4）
        rows = min(4, (len(posters) + 2) // 3)
        cols = min(3, len(posters))
        
        plt.figure(figsize=(15, rows * 5))
        
        for i, poster_path in enumerate(posters[:12]):  # 最多12张海报
            if i >= rows * cols:
                break
                
            try:
                img = Image.open(poster_path)
                plt.subplot(rows, cols, i + 1)
                plt.imshow(np.array(img))
                plt.axis('off')
                plt.title(os.path.basename(poster_path).replace("astronomy_", "").replace(".png", ""))
            except Exception as e:
                print(f"无法加载海报 {poster_path}: {str(e)}")
        
        plt.tight_layout()
        
        # 保存合集
        collection_path = os.path.join(self.output_path, f"monthly_{last_month.strftime('%Y%m')}.png")
        plt.savefig(collection_path)
        plt.close()
        
        return collection_path
        
    def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """清理旧的海报数据，仅保留最近几天的文件"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        
        # 清理单个海报文件
        for file in os.listdir(self.output_path):
            if file.startswith("astronomy_"):
                try:
                    file_date_str = file.replace("astronomy_", "").replace(".png", "")
                    file_date = datetime.datetime.strptime(file_date_str, "%Y%m%d")
                    
                    if file_date < cutoff_date:
                        os.remove(os.path.join(self.output_path, file))
                except Exception as e:
                    print(f"清理文件 {file} 失败: {str(e)}")
