"""
小天的词频统计模块
负责分析和统计消息中的词频
"""

import os
import re
import json
import datetime
from openai import OpenAI
import random
import jieba
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
import matplotlib.pyplot as plt
import matplotlib
from wordcloud import WordCloud
import numpy as np
from pathlib import Path

from .config import WORDSTATS_OUTPUT_DIR, WORDSTATS_DATA_DIR, DEFAULT_FONT, WORDCLOUD_FONT
from .ai_core import XiaotianAI


class WordFrequencyAnalyzer:
    def __init__(self, base_path="xiaotian"):
        # 使用绝对路径
        self.base_path = os.path.abspath(base_path)
        print(f"WordFrequencyAnalyzer 初始化，基础路径: {self.base_path}")
        
        self.data_path = os.path.abspath(WORDSTATS_DATA_DIR)
        self.output_path = os.path.abspath(WORDSTATS_OUTPUT_DIR)
        self.stopwords_path = os.path.join(self.base_path, "data/stopwords.txt")
        
        print(f"数据路径: {self.data_path}")
        print(f"输出路径: {self.output_path}")
        print(f"停用词文件: {self.stopwords_path}")
        
        # 确保目录存在
        os.makedirs(self.data_path, exist_ok=True)
        os.makedirs(self.output_path, exist_ok=True)
        
        # 使用配置中的字体
        self.default_font = DEFAULT_FONT
        self.wordcloud_font = WORDCLOUD_FONT
        print(f"将使用默认字体: {self.default_font}")
        print(f"将使用词云字体: {self.wordcloud_font}")
            
        # 加载停用词
        self.stopwords = self._load_stopwords()
        
        # 今日消息存储
        self.daily_messages = []
        self.today_date = datetime.datetime.now().strftime("%Y%m%d")
        
        # 确保jieba词典已加载
        try:
            jieba.initialize()
            print("jieba 初始化成功")
        except Exception as e:
            print(f"jieba 初始化失败: {e}")
        
        # 初始化 AI 客户端
        self.ai_client = XiaotianAI()
        print("AI 客户端已初始化")
    
    def _load_stopwords(self) -> set:
        """加载停用词列表"""
        stopwords = {'的', '了', '和', '是', '在', '我', '有', '你', '他', '她', '它', '们', '个',
                   '这', '那', '就', '要', '啊', '吧', '呢', '吗', '啦', '呀', '哦', '嗯',
                   '哈', '一', '是不是', '什么', '怎么', '为什么', '如何', '可以', '能', '不能',
                   '会', '不会', '应该', '可能', '应当', '需要', '一下', '一种', '一个', '没有',
                   '没', '不', '很', '太', '还', '又', '也', '但是', '但', '而', '而且', 
                   '所以', '因此', '因为', '如果', '的话', '只是', '只有', '只', '就是', '这个',
                   '那个', '小天', '请问'}
        
        # 如果存在停用词文件，加载它
        if os.path.exists(self.stopwords_path):
            try:
                with open(self.stopwords_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        stopwords.add(line.strip())
            except Exception as e:
                print(f"加载停用词失败: {e}")
        else:
            # 创建默认的停用词文件
            try:
                with open(self.stopwords_path, 'w', encoding='utf-8') as f:
                    for word in stopwords:
                        f.write(word + '\n')
            except Exception as e:
                print(f"创建停用词文件失败: {e}")
        
        return stopwords
    
    def add_message(self, message: str) -> None:
        """添加消息到今日集合"""
        # 检查是否需要重置（新的一天）
        current_date = datetime.datetime.now().strftime("%Y%m%d")
        if current_date != self.today_date:
            # 新的一天，先保存昨天的数据
            self._save_daily_messages(self.today_date)
            # 重置
            self.daily_messages = []
            self.today_date = current_date
        
        # 添加新消息
        self.daily_messages.append(message)
        
    def _save_daily_messages(self, date_str: str) -> None:
        """保存某天的消息集合"""
        if not self.daily_messages:
            return
            
        # 分析并保存词频数据
        word_counts = self.analyze_word_frequency(self.daily_messages)
        
        # 将结果保存到文件
        data_file = os.path.join(self.data_path, f"wordstats_{date_str}.json")
        
        try:
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "date": date_str,
                    "total_messages": len(self.daily_messages),
                    "word_counts": word_counts
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存词频数据失败: {e}")
    
    def analyze_word_frequency(self, messages: List[str], top_n: int = 30) -> Dict[str, int]:
        """分析消息中的词频"""
        # 合并所有消息
        all_text = " ".join(messages)
        
        # 使用jieba分词
        word_list = jieba.lcut(all_text)
        
        # 过滤停用词和单字符词
        pattern = r'^[^\w\u4e00-\u9fff]+$'
        filtered_words = [word for word in word_list 
                         if word not in self.stopwords 
                         and len(word.strip()) > 1 
                         and not word.isdigit()
                         and not re.match(pattern, word)]  # 排除纯符号
        
        # 计算词频
        word_counts = Counter(filtered_words)
        
        # 返回前N个高频词
        return dict(word_counts.most_common(top_n))
    
    def generate_daily_wordcloud(self, date_str: Optional[str] = None) -> Optional[str]:
        """生成每日词云图"""
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        print(f"尝试为日期 {date_str} 生成词云图")
        
        # 加载当日词频数据
        data_file = os.path.join(self.data_path, f"wordstats_{date_str}.json")
        word_counts = None
        
        if not os.path.exists(data_file):
            print(f"数据文件不存在: {data_file}")
            if date_str == self.today_date and self.daily_messages:
                print(f"使用内存中的今日数据，消息数量: {len(self.daily_messages)}")
                # 使用内存中的今日数据
                word_counts = self.analyze_word_frequency(self.daily_messages)
                print(f"分析得到的词数: {len(word_counts) if word_counts else 0}")
            else:
                # 尝试使用昨天的数据
                # 使用随机生成的词频数据填充词云图
                print("使用随机生成的词频数据填充词云图")
                try:
                    random_words = self.ai_client.get_response("请返回20个随机词汇,请注意，词汇必须严格是20个")
                    word_counts = self.analyze_word_frequency([random_words])
                except Exception as e:
                    print(f"AI生成随机词汇失败: {e}")
                    # 使用硬编码的备用词汇
                    fallback_words = ["天空", "星星", "月亮", "太阳", "云朵", "风", "雨", "雪", "花", "树", 
                                    "山", "海", "河", "湖", "鸟", "鱼", "猫", "狗", "书", "音乐"]
                    word_counts = {word: random.randint(5, 20) for word in fallback_words}
                print(f"生成的随机词频数据: {word_counts}")
        else:
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    word_counts = data["word_counts"]
            except Exception as e:
                print(f"加载词频数据失败: {e}")
                return None
        
        if not word_counts:
            return None
            
        # 配置中文字体 - 从配置文件获取
        print(f"使用配置中的词云字体: {self.wordcloud_font}")
        
        # 设置matplotlib字体
        try:
            from matplotlib.font_manager import FontProperties
            custom_font = FontProperties(fname=self.default_font)
            plt.rcParams['font.family'] = custom_font.get_name()
            print(f"成功设置matplotlib字体: {self.default_font}")
        except Exception as e:
            print(f"设置自定义字体失败: {e}")
            # 使用系统字体作为后备
            matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Noto Sans CJK']
            print("使用系统字体作为后备选项")

        matplotlib.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
        
        # 创建词云图，使用配置中的词云字体
        font_path = self.wordcloud_font  # 使用配置中设置的词云字体
        print(f"用于词云的字体路径: {font_path}")
                
        try:
            print(f"开始创建WordCloud对象，使用字体: {font_path}")
            print(f"词频数据样例: {list(word_counts.items())[:5]}")
            
            # 确保word_counts中的所有键都是字符串
            word_counts = {str(k): v for k, v in word_counts.items()}
            
            # 创建WordCloud对象，使用配置中指定的字体
            wordcloud = WordCloud(
                font_path=font_path,  # 使用配置中的词云字体
                width=1000,  # 增加宽度
                height=800,  # 增加高度
                background_color='#F9F8F3',
                scale = 2,
                margin = 2,
                max_words=100,
                max_font_size=200,  # 增加最大字体大小
                min_font_size = 4,
                colormap='viridis',  # 使用更现代的配色方案
                random_state=42
            )
            
            print("WordCloud对象创建成功，开始生成词频")
            wordcloud = wordcloud.generate_from_frequencies(word_counts)
            print("词频生成成功")
        except Exception as e:
            print(f"创建或生成WordCloud失败: {e}")
            import traceback
            print(traceback.format_exc())
            return None
        
        plt.figure(figsize=(12, 10))  # 调整图表大小
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.title(f"小天 - {date_str[:4]}/{date_str[4:6]}/{date_str[6:]}", fontsize=18, pad=20)  # 增加标题字体大小和间距
        plt.tight_layout()
        
        # 保存图片
        output_path = os.path.join(self.output_path, f"wordcloud_{date_str}.png")
        
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 使用绝对路径
            abs_output_path = os.path.abspath(output_path)
            print(f"保存词云图到: {abs_output_path}")
            
            plt.savefig(abs_output_path)
            plt.close()
            
            if os.path.exists(abs_output_path):
                print(f"词云图保存成功: {abs_output_path}")
                return abs_output_path
            else:
                print(f"警告: 词云图保存失败，文件不存在: {abs_output_path}")
                return None
        except Exception as e:
            print(f"保存词云图失败: {e}")
            import traceback
            print(traceback.format_exc())
            plt.close()
            return None
    
    def generate_daily_barchart(self, date_str: Optional[str] = None) -> Optional[str]:
        """生成每日词频条形图"""
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        # 加载当日词频数据
        data_file = os.path.join(self.data_path, f"wordstats_{date_str}.json")
        if not os.path.exists(data_file):
            if date_str == self.today_date and self.daily_messages:
                # 使用内存中的今日数据
                word_counts = self.analyze_word_frequency(self.daily_messages)
            else:
                return None
        else:
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    word_counts = data["word_counts"]
            except Exception as e:
                print(f"加载词频数据失败: {e}")
                return None
        
        if not word_counts:
            return None
            
        # 只保留前30个词
        top_n = min(30, len(word_counts))
        words = list(word_counts.keys())[:top_n]
        counts = list(word_counts.values())[:top_n]
        
        # 配置中文字体 - 从配置文件获取
        print(f"使用配置中的默认字体: {self.default_font}")
        
        try:
            from matplotlib.font_manager import FontProperties
            custom_font = FontProperties(fname=self.default_font)
            plt.rcParams['font.family'] = custom_font.get_name()
            print(f"成功设置条形图字体: {self.default_font}")
        except Exception as e:
            print(f"设置自定义字体失败: {e}")
            matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # 回退到SimHei
            print("使用系统字体SimHei作为后备选项")
            
        matplotlib.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
        
        # 创建条形图
        plt.figure(figsize=(14, 10))  # 调整图表大小
        plt.barh(words[::-1], counts[::-1], color='dodgerblue', edgecolor='black')  # 使用更鲜艳的颜色和边框
        plt.xlabel('词频', fontsize=14, labelpad=10)  # 增加字体大小和间距
        plt.ylabel('词语', fontsize=14, labelpad=10)
        plt.title(f"小天 - {date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日热门词汇 Top {top_n}", fontsize=16, pad=20)  # 增加标题字体大小和间距
        plt.xticks(fontsize=12)
        plt.yticks(fontsize=12)
        plt.grid(axis='x', linestyle='--', alpha=0.7)  # 添加网格线
        plt.tight_layout()
        
        # 保存图片
        output_path = os.path.join(self.output_path, f"wordstats_{date_str}.png")
        
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 使用绝对路径
            abs_output_path = os.path.abspath(output_path)
            print(f"保存条形图到: {abs_output_path}")
            
            plt.savefig(abs_output_path)
            plt.close()
            
            if os.path.exists(abs_output_path):
                print(f"条形图保存成功: {abs_output_path}")
                return abs_output_path
            else:
                print(f"警告: 条形图保存失败，文件不存在: {abs_output_path}")
                return None
        except Exception as e:
            print(f"保存条形图失败: {e}")
            import traceback
            print(traceback.format_exc())
            plt.close()
            return None
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """清理旧数据，只保留最近几天的数据"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime("%Y%m%d")
        
        # 清理旧的数据文件
        for file in os.listdir(self.data_path):
            if file.startswith("wordstats_") and file.endswith(".json"):
                date_str = file.replace("wordstats_", "").replace(".json", "")
                if date_str < cutoff_str:
                    try:
                        os.remove(os.path.join(self.data_path, file))
                    except Exception as e:
                        print(f"清理文件 {file} 失败: {e}")
        
        # 清理旧的图表文件
        for file in os.listdir(self.output_path):
            if (file.startswith("wordcloud_") or file.startswith("wordstats_")) and file.endswith(".png"):
                date_str = file.split("_")[1].replace(".png", "")
                if date_str < cutoff_str:
                    try:
                        os.remove(os.path.join(self.output_path, file))
                    except Exception as e:
                        print(f"清理文件 {file} 失败: {e}")
                        
    def force_save_current_data(self) -> None:
        """强制保存当前数据（用于关闭程序前）"""
        self._save_daily_messages(self.today_date)
