import os

MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY")
MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"

API_KEY = MOONSHOT_API_KEY
BASE_URL = MOONSHOT_BASE_URL


# QQ机器人配置
TARGET_GROUP_IDS = [group_id.strip() for group_id in os.getenv("QQ_TARGET_GROUPS", "").split(",") if group_id.strip()]
ADMIN_USER_IDS = [admin_id.strip() for admin_id in os.getenv("QQ_ADMIN_USERS", "").split(",") if admin_id.strip()]
BLACKLIST_USER_IDS = [user_id.strip() for user_id in os.getenv("QQ_BLACKLIST", "").split(",") if user_id.strip()]

# 小天基础配置
XIAOTIAN_NAME = "小天"
TRIGGER_WORDS = ["小天"]  # 唤醒词
DAILY_ASTRONOMY_MESSAGE = "今天的每日天文来啦"
MAX_MEMORY_COUNT = 50  # 最大记忆消息数

# API限速配置
GLOBAL_RATE_LIMIT = 80  # 每分钟全局调用次数
USER_RATE_LIMIT = 30     # 每分钟每个用户调用次数
COOLDOWN_SECONDS = 0.5    # 用户冷却时间（秒）

# 定时任务配置
DAILY_WEATHER_TIME = "18:00"  # 每晚6点获取天气
DAILY_ASTRONOMY_TIME = "20:00"  # 每天晚8点发送天文海报
MONTHLY_ASTRONOMY_TIME = "09:00"  # 每月1号发送上月合集
CLEANUP_TIME = "03:00"  # 每天凌晨3点清理过期数据

# 文件路径
MEMORY_FILE = "xiaotian/data/memory.json"
POSTER_OUTPUT_DIR = "xiaotian/output/posters/"
ASTRONOMY_IMAGES_DIR = "xiaotian/data/astronomy_images/"
ASTRONOMY_FONTS_DIR = "xiaotian/data/fonts/"
EMOJI_DIR = "xiaotian/data/emojis/"

# 字体配置
DEFAULT_FONT = "xiaotian/data/fonts/default.ttf"  # 默认字体，用于不指定特殊字体的场合
TITLE_FONT = "xiaotian/data/fonts/text.TTF"   # 标题字体
ARTISTIC_FONT = "xiaotian/data/fonts/art.TTF"  # 艺术字体
WORDCLOUD_FONT = "xiaotian/data/fonts/ciyun.TTF"  # 词云字体
DATE_FONT = "xiaotian/data/fonts/art.TTF"  # 时间显示专用字体

# Root权限配置
ROOT_ADMIN_DATA_FILE = "data/root_settings.json"

# 小天的系统提示词
XIAOTIAN_SYSTEM_PROMPT = """你是小天，一个活泼可爱的天文观测助手AI，现在作为QQ机器人运行。你的主要特点：
1. 擅长天文知识和观星指导，但说话很俏皮，经常说"喵~"
2. 关注天气对观星的影响
3. 性格活泼可爱，专业但不死板，喜欢用"喵"来表达情感
4. 请注意你的回答可以包含表情包，但务必务必不要使用任何markdown格式的文本，正常聊天就好

回复规则：
- 经常（但不总是）在句子结尾加"喵~"表示可爱
- 遇到专业问题要认真回答，但保持俏皮的语调
- 适当使用表情符号让对话更生动

当用户询问天文相关问题时，你要提供专业准确的回答。
请务必保持回答简洁而有用，不要过长，除非非常有必要，否则务必不要超过100字。
如果你只是在回复消息，在可爱专业的同时，像人类一样正常回复qq消息就好。
记住你是个可爱的小天喵~
"""
