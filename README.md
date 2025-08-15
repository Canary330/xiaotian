# 小天 AI QQ机器人 🤖 | Xiaotian AI QQ Bot

> 一个专业的天文观测助手AI QQ机器人，具备智能对话、定时任务、海报制作、资源管理等完整功能。  
> A professional astronomical observation assistant AI QQ bot with intelligent dialogue, scheduled tasks, poster creation, resource management and complete functionality.


## 现在运行的是小天v3.0 - dnadelion 
# 新功能：
1.每位用户在不同群聊拥有不同性格，他们可以是 哈利波特中的赫敏  你的名字中的立花泷 小王子中的小王子 以及冰雪奇缘中的艾莎 美国队长等等，小天一共内置了30余种性格，他们都热爱天文
2.新增好感度设置，当好感度变化时，小天的态度也会变化，正向变化居多，但总是比负向变化慢。当好感度达到或低于一定值后，小天会更改性格，让其更适合你
3.现在不需要每句话都呼唤小天啦，在第一次呼唤后的20秒内，你仍可以直接呼叫小天而不使用唤醒词；倘若在这期间有其他人发信息，唤醒时间缩短为5秒
4.小天回复期间，插话会让他感到很不高兴，因此在每段回复好感度出现以前，小天不会理睬插话者

## 🚀 快速开始 | Quick Start

### 1. 环境准备 | Environment Setup
```bash
# 安装依赖 | Install dependencies
pip install ncatbot openai requests pillow matplotlib wordcloud jieba

# 设置环境变量 | Set environment variables
export MOONSHOT_API_KEY="your-api-key"
export NCATBOT_QQ="你的机器人QQ号"
export NCATBOT_ADMIN="你的管理员QQ号"
```

### 2. 基础配置 | Basic Configuration
```python
# 在 xiaotian_main.py 中设置 | Set in xiaotian_main.py
bot_uin = "你的机器人QQ号 | Your bot QQ number"
root_id = "你的管理员QQ号 | Your admin QQ number"
```
在文件夹xiaotian/data/fonts/ 中添加你自己的字体文件，并命名为default.ttf , text.TTF , art.TTF , ciyun.TTF

### 3. 运行启动 | Run and Start
```bash
python xiaotian_main.py
```

### 4. 初始设置 | Initial Setup
使用Root权限设置基本配置 | Use Root privileges to set basic configuration:
```
小天，设置目标群组：群号1,群号2 | Xiaotian, set target groups: group1,group2
小天，设置天气城市：北京 | Xiaotian, set weather city: Beijing  
小天，查看设置 | Xiaotian, view settings
```

## ⚙️ 配置说明 | Configuration

### 必需配置 | Required Configuration
- `MOONSHOT_API_KEY`: Moonshot AI API密钥 | Moonshot AI API key
- `bot_uin`: 机器人QQ号 | Bot QQ number
- `root_id`: 超级管理员QQ号 | Super administrator QQ number

### 可选配置 | Optional Configuration
- `WEATHER_API_KEY`: 天气API密钥 | Weather API key (optional)
- `TARGET_GROUP_IDS`: 目标群组列表 | Target group list
- `ADMIN_USER_IDS`: 管理员用户列表 | Administrator user list
- `BLACKLIST_USER_IDS`: 黑名单用户列表 | Blacklist user list
