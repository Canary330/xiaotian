# -*- coding: utf-8 -*-
"""
小天的新成员欢迎模块
负责检测新成员入群并发送欢迎消息
"""

import os
import json
import time
from typing import Dict, Optional, Set
from datetime import datetime
import random

class WelcomeManager:
    """管理新成员欢迎功能"""
    
    def __init__(self, root_manager=None, ai=None):
        """初始化欢迎管理器"""
        self.root_manager = root_manager
        self.ai = ai
        
        # 存储已处理过的加群通知ID（避免重复欢迎）
        self.processed_notices = set()
        
        # 欢迎消息模板
        self.welcome_templates = [
            "🌟 欢迎 {nickname} 加入我们的大家庭！希望你在这里玩得开心~",
            "🎉 新朋友 {nickname} 来啦！欢迎你的加入！",
            "👋 Hey {nickname}，欢迎加入！期待与你的交流~",
            "💫 欢迎 {nickname} 加入群聊！有什么问题可以随时问我哦~"
        ]
    
    def process_group_increase_notice(self, notice_data) -> Optional[str]:
        """
        处理群成员增加通知
        
        Args:
            notice_data: 通知数据，格式如下：
            {
                "time": 1609478707,
                "self_id": 123456789, 
                "post_type": "notice",
                "notice_type": "group_increase", 
                "sub_type": "approve", 
                "group_id": 123456789,
                "operator_id": 987654321,
                "user_id": 987654321 # 加入者QQ号
            }
            
        Returns:
            Optional[str]: 如是新成员且不是机器人自己，返回欢迎消息；否则返回None
        """
        # 检查通知类型
        if notice_data.get("notice_type") != "group_increase":
            return None
            
        # 获取相关信息
        group_id = str(notice_data.get("group_id"))
        user_id = str(notice_data.get("user_id"))
        self_id = str(notice_data.get("self_id"))  # 机器人自己的QQ号
        notice_time = notice_data.get("time", 0)
        
        # 生成唯一的通知ID（避免重复处理）
        notice_id = f"{group_id}_{user_id}_{notice_time}"
        
        # 如果已经处理过或者是机器人自己入群，则跳过
        if notice_id in self.processed_notices or user_id == self_id:
            return None
            
        # 标记为已处理
        self.processed_notices.add(notice_id)
        
        # 限制已处理通知的数量，避免内存增长过快
        if len(self.processed_notices) > 1000:
            # 只保留最新的500条记录
            self.processed_notices = set(list(self.processed_notices)[-500:])
        
        # 生成欢迎消息，只传递用户ID
        welcome_msg = self._generate_welcome_message(user_id)
        return welcome_msg
    
    def _generate_welcome_message(self, member_id: str) -> str:
        """
        生成欢迎消息
        
        Args:
            member_id: 成员ID
            
        Returns:
            str: 欢迎消息
        """
        # 随机选择一条欢迎模板
        template = random.choice(self.welcome_templates)
        
        # 替换昵称（使用@成员的形式，实际发送时会被转换为At组件）
        nickname = f"[CQ:at,qq={member_id}]"
        
        # 生成欢迎消息
        welcome_msg = template.format(nickname=nickname)
        
        # 添加小天的使用说明
        usage_guide = (
            "欢迎加入天文协会会员群，这里有超多的资源和志同道合的伙伴。无论你是初学者还是资深爱好者，都能在这里找到属于自己的天地"
            "\n\n🌸 你可以使用以下命令唤醒小天喵 🌸\n"
            "🐣 发送「小天」唤醒机器人，如果你想要人工为你解答，请@我\n"
            "🧸 问我任何问题，我会尽力回答，聊天互动可以提升或降低好感度\n"
            "🎀 发送「小天 天文竞答 题目数量」参与知识问答并按时间逻辑获得巨额好感度；如果参与人数大于3，即使回答错误，好感度也不会下降哦\n"
            "🎀 发送「小天 案件还原」参与案件推理并获得200好感度\n"
            "🍭 发送「小天，与 @用户 对冲 n 好感度」对冲掉对方的好感度\n"
            "🐰 小天对每位用户都有不同的性格，你也可以发送「小天，更改性格」或「小天，回到最初的性格」改变性格\n"
            "💖 每个月我们会根据好感度排名发放礼物，好感度靠前的uu可以获得精美礼品喵\n"
        )
        
        welcome_msg += usage_guide
        
        # 赠送好感度（如果AI实例可用）
        if self.ai:
            try:
                # 按照AI系统中的格式构建memory_key
                # 从ai_core.py中可以看出，好感度系统使用的是 user_{user_id} 格式
                user_id = member_id
                memory_key = f"user_{user_id}"
                
                # 获取或创建用户状态，get_user_like_status 会自动创建新用户记录
                user_status = self.ai.get_user_like_status(user_id)
                
                # 直接修改用户状态，绕过倍率系统赠送20点好感度
                if user_status is not None:
                    # 生成随机好感度
                    prob = random.random()
                    bonus_msg = ""
                    if prob < 0.001:
                        user_status['total_like'] = 2000.0
                        bonus_msg =( "🎁 哇哦！超级幸运！0.1%的概率，已赠送您 2000 点好感度~~小天开心到爆炸！\n"
                                    "~~如果可以的话，能不能给小天一颗⭐，求求了")
                        print(f"✓ 已为新成员 {user_id} 赠送2000点好感度（超级小概率事件）")
                    elif prob < 0.01:
                        user_status['total_like'] = 200.0
                        bonus_msg = ("🎁 哇哦！超级幸运！1%的概率，已赠送您 200 点好感度~~小天太开心了！\n"
                                    "~~如果可以的话，能不能给小天一颗⭐，求求了")
                        print(f"✓ 已为新成员 {user_id} 赠送200点好感度（超级小概率事件）")
                    elif prob < 0.05:
                        user_status['total_like'] = 100.0
                        bonus_msg = ("🎁 恭喜！5%的概率，已赠送您 100 点好感度~~小天很高兴！\n"
                                    "~~如果可以的话，能不能给小天一颗⭐，求求了")
                        print(f"✓ 已为新成员 {user_id} 赠送100点好感度（小概率事件）")
                    elif prob < 0.1:
                        user_status['total_like'] = 50.0
                        bonus_msg = ("🎁 不错哦！10%的概率，已赠送您 50 点好感度~~小天觉得你很棒！\n"
                                    "~~如果可以的话，能不能给小天一颗⭐，求求了")
                        print(f"✓ 已为新成员 {user_id} 赠送50点好感度（普通小概率事件）")
                    else:
                        bonus = random.randint(0, 5)
                        user_status['total_like'] = 20.0 + bonus
                        bonus_msg = f"🎁 初次见面，已赠送您 {20 + bonus} 点好感度"
                        print(f"✓ 已为新成员 {user_id} 赠送{20 + bonus}点好感度")
                    
                    welcome_msg += bonus_msg
                else:
                    print(f"⚠️ 无法为新成员 {user_id} 创建好感度记录，可能是AI实例未完全初始化")
            except Exception as e:
                print(f"❌ 赠送好感度失败: {str(e)}")
                # 尝试确保用户记录被创建
                try:
                    # 重新尝试创建用户记录
                    self.ai.user_like_status[f"user_{user_id}"] = {
                        'total_like': 20.0,
                        'last_change_direction': None,
                        'reset_count': 0,
                        'original_personality': None,
                        'notified_thresholds': [],
                        'speed_multiplier': 1.0,
                        'personality_change_count': 0
                    }
                    print(f"✓ 已通过备用方式为新成员 {user_id} 赠送20点好感度")
                    welcome_msg += "🎁 初次见面，已赠送您 20 点好感度~~如果可以的话，能不能给小天一颗⭐，求求了"
                except Exception as backup_error:
                    print(f"❌ 备用方式也失败了: {str(backup_error)}")
        
        return welcome_msg
