# AI QQ机器人

> 一个AI QQ机器人，具备智能对话、定时任务、海报制作、资源管理等完整功能。  

使用set：机器人名称 原始性格 海报名字 竞答名字：命名
查看data/astronomy_questions.json文件，改写适你自己的题库；
自定义海报背景图和标题，并将xiaotian/data/astronomy_images的logo.png替换，以便自动制作海报；

## 现在运行的是v3.5版本
# 新功能：
你可以使用以下命令唤醒：
发送「触发词」（需要有逗号才可以）唤醒
问任何问题，机器人会尽力回答，聊天互动可以提升或降低好感度  
发送「名称 知识问答 题目数量」参与知识问答并按时间逻辑获得巨额好感度；如果参与人数大于3，即使回答错误，好感度也不会下降哦  
发送「名称 案件还原」参与案件推理并获得200好感度  
发送「触发词 与 @用户 对冲 n 好感度」对冲掉对方的好感度  
机器人对每位用户都有不同的性格，你也可以发送「触发词 更改性格」或「触发词 回到最初的性格」改变性格  

## 快速开始

### 1. 环境准备
```bash
# 安装依赖
pip install ncatbot openai requests pillow matplotlib wordcloud jieba

# 设置环境变量
export DEEPSEEK_API_KEY="your-api-key"
export NCATBOT_QQ="你的机器人QQ号"
export NCATBOT_ADMIN="你的管理员QQ号"
```
建议将其直接写入服务器的系统任务，24小时运行
### 2. 基础配置
```python
在文件夹xiaotian/data/fonts/ 中添加你自己的字体文件，并命名为default.ttf , text.TTF , art.TTF , ciyun.TTF；此配置用于生成海报，如果字体本身不支持中文，则海报内中文会乱码
```


### 3. 运行启动
```bash
python3 xiaotian_main.py
```

### 4. 初始设置
使用Root用户权限设置基本配置:
```
小天，设置目标群组：群号1,群号2（设置群组后才会自动发送内容）
小天，设置天气城市：北京
小天，查看设置
```

## 配置说明

### 必需配置
- `MOONSHOT_API_KEY`: API密钥
- `bot_uin`: 机器人QQ号
- `root_id`: 超级管理员QQ号

### 可选配置
- `TARGET_GROUP_IDS`: 目标群组列表
- `ADMIN_USER_IDS`: 管理员用户列表
- `BLACKLIST_USER_IDS`: 黑名单用户列表


### 本项目采用mit开源
