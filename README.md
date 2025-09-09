# 小天 AI QQ机器人 🤖 | Xiaotian AI QQ Bot

> 一个AI QQ机器人，具备智能对话、定时任务、海报制作、资源管理等完整功能。  
> A professional astronomical observation assistant AI QQ bot with intelligent dialogue, scheduled tasks, poster creation, resource management and complete functionality.


## 现在运行的是小天v3.5 - dnadelion 
# 新功能（这里的“我”指代吉祥物名字）：
🌸 你可以使用以下命令唤醒我喵 🌸
🐣 发送「触发词」（需要有逗号才可以）唤醒我，如果你想要人工为你解答，请@我  
🧸 问我任何问题，我会尽力回答，聊天互动可以提升或降低好感度  
🎀 发送「我 知识问答 题目数量」参与知识问答并按时间逻辑获得巨额好感度；如果参与人数大于3，即使回答错误，好感度也不会下降哦  
🎀 发送「我 案件还原」参与案件推理并获得200好感度  
🍭 发送「触发词 与 @用户 对冲 n 好感度」对冲掉对方的好感度  
🐰 我对每位用户都有不同的性格，你也可以发送「触发词 更改性格」或「触发词 回到最初的性格」改变性格  
💖 每个月我们会根据好感度排名发放礼物，好感度靠前的uu可以获得精美礼品喵  
## 🚀 快速开始 | Quick Start

### 1. 环境准备 | Environment Setup
```bash
# 安装依赖 | Install dependencies
pip install ncatbot openai requests pillow matplotlib wordcloud jieba

# 设置环境变量 | Set environment variables
export DEEPSEEK_API_KEY="your-api-key"
export NCATBOT_QQ="你的机器人QQ号"
export NCATBOT_ADMIN="你的管理员QQ号"
```

### 2. 基础配置 | Basic Configuration
```python
在文件夹xiaotian/data/fonts/ 中添加你自己的字体文件，并命名为default.ttf , text.TTF , art.TTF , ciyun.TTF
```


### 3. 运行启动 | Run and Start
```bash
python3 xiaotian_main.py
```

### 4. 初始设置 | Initial Setup
使用Root权限设置基本配置 | Use Root privileges to set basic configuration:
```
小天，设置目标群组：群号1,群号2 | Xiaotian, set target groups: group1,group2
小天，设置天气城市：北京 | Xiaotian, set weather city: Beijing  
小天，查看设置 | Xiaotian, view settings
```
默认为小天，如果你需要其他名字，使用root管理员账号发送set：吉祥物名称 原始性格 海报名字 竞答名字
## ⚙️ 配置说明 | Configuration

### 必需配置 | Required Configuration
- `MOONSHOT_API_KEY`: Moonshot AI API密钥 | Moonshot AI API key
- `bot_uin`: 机器人QQ号 | Bot QQ number
- `root_id`: 超级管理员QQ号 | Super administrator QQ number

### 可选配置 | Optional Configuration
- `TARGET_GROUP_IDS`: 目标群组列表 | Target group list
- `ADMIN_USER_IDS`: 管理员用户列表 | Administrator user list
- `BLACKLIST_USER_IDS`: 黑名单用户列表 | Blacklist user list
