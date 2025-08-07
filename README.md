# 小天 AI QQ机器人 🤖 | Xiaotian AI QQ Bot

> 一个专业的天文观测助手AI QQ机器人，具备智能对话、定时任务、海报制作、资源管理等完整功能。  
> A professional astronomical observation assistant AI QQ bot with intelligent dialogue, scheduled tasks, poster creation, resource management and complete functionality.


## 👨‍💻 开发者规范 | Developer Guidelines
**如果你想要协助开发小天，请务必阅读开发者规范；如果你只是看看，可以跳过这一点**

### 代格 | Code Style
- 变量、函数、类命名需语义清晰，采用英文 | Use cle合，关键逻辑需详细说明 | CommentsVersion Control
- 所有更改需通过Pull Request提交 | All changese或功能说明 | Each commit ode review r己的- QQ号测试你的新功能，确认无误后再上传**

### 文档维护 | Docuntation
- 新功能需同步更新README和相关文档 | Update README and usage examples新增功能需编写单元测试 | Write unit tes可s for new features
- 保证主要功能覆盖率 >80% | Ensues should be readable and maintainable

### 安全与合规 | Security & Cpliance
- 不得上传敏感信息（如API密钥、用户数据） | Do not upload sensitive in使用简明英文或中文，格式：`[模块] 简要描述` | Use concise English, format: `[module] brief description`
- 例如：`[astronomy] add logo brightness optimization`

## 🐞 现有问题追踪 | Issue Tracker
**如果你解决了某些问题，请将是否解决的‘否’改为‘是’**
**如果你发现新问题或者提出新功能（请自行实现），也请加在此处**


| 问题编号 | 问题描述                                   | 是否解决 |
|:--------:|--------------------------------------------|:--------:|
| 1        | 天气测试不准确                             | 否       |
| 2        | 统计时错误的将表情包链接统计加入词频       | 否       |
| 3        | 回复过长，时不时使用md格式                 | 否       |


---



## 📋 目录 | Table of Contents
- [功能特色 Features](#功能特色--features)
- [系统架构 | System Architecture](#系统架构--system-architecture)
- [快速开始 | Quick Start](#快速开始--quick-start)
- [配置说明 | Configuration](#配置说明--configuration)
- [使用指南 | User Guide](#使用指南--user-guide)
- [管理员功能 | Admin Features](#管理员功能--admin-features)
- [开发文档 | Development](#开发文档--development)

## 🌟 功能特色 | Features

### 🤖 核心功能 | Core Features
- **智能对话 | Intelligent Dialogue**：基于Moonshot AI的自然语言处理，活泼俏皮的性格 | Based on Moonshot AI with lively and playful personality
- **独立记忆 | Independent Memory**：每个用户私聊和每个群聊都有独立的对话记忆 | Each private chat and group chat has independent conversation memory
- **智能触发 | Smart Triggering**：支持关键词触发和自动气氛调节 | Supports keyword triggering and automatic atmosphere adjustment
- **定时任务 | Scheduled Tasks**：天气播报、统计报告、天文海报等自动化任务 | Weather reports, statistical reports, astronomical posters and other automated tasks

### 🎨 专业功能 | Professional Features
- **天文海报制作 | Astronomical Poster Creation**：
  - 根据文本内容自动生成精美的天文科普海报 | Automatically generate beautiful astronomical science posters based on text content
  - 智能排版和字体渲染 | Intelligent layout and font rendering  
  - 支持用户自定义图片插入 | Support user-defined image insertion
  - **新增LOGO功能**：左上角智能LOGO展示，自动亮度优化 | **NEW LOGO Feature**: Smart logo display in upper left corner with automatic brightness optimization
  
- **词频统计分析 | Word Frequency Analysis**：
  - 实时统计消息词频，生成图表和词云 | Real-time message word frequency statistics, generate charts and word clouds
  - 智能过滤停用词 | Intelligent filtering of stop words
  - 支持时间段分析 | Support time period analysis

- **天气查询 | Weather Query**：
  - 获取观星条件建议和天气预报 | Get stargazing condition suggestions and weather forecasts
  - 支持多城市配置 | Support multiple city configurations

- **数据统计 | Data Statistics**：
  - 消息分析、用户活跃度、关键词统计 | Message analysis, user activity, keyword statistics
  - 生成可视化图表 | Generate visualization charts

### 🛡️ 管理功能 | Management Features
- **Root超级管理员 | Root Super Administrator**：
  - 拥有完全控制权限 | Full control permissions
  - 实时配置修改 | Real-time configuration modification
  - 系统状态监控 | System status monitoring

- **资源管理 | Resource Management**：
  - **直接上传功能**：通过QQ直接上传图片和字体资源 | **Direct Upload**: Upload images and font resources directly through QQ
  - **文件类型支持**：支持.png, .jpg, .ttf, .otf等格式 | **File Type Support**: Support .png, .jpg, .ttf, .otf and other formats
  - **自动分类存储**：图片和字体自动分类存储到对应目录 | **Auto Categorized Storage**: Images and fonts automatically categorized and stored in corresponding directories

- **安全防护 | Security Protection**：
  - 速率限制、黑名单、权限控制 | Rate limiting, blacklist, permission control
  - API调用监控 | API call monitoring

## 🏗️ 系统架构 | System Architecture

```
小天 QQ机器人 | Xiaotian QQ Bot
├── 核心模块 | Core Modules
│   ├── xiaotian_main.py     # 主程序入口 | Main program entry
│   ├── config.py            # 配置管理 | Configuration management
│   └── scheduler.py         # 消息调度器 | Message scheduler
├── AI模块 | AI Modules
│   ├── ai_core.py          # AI核心接口 | AI core interface
│   └── utils/ai_utils.py   # AI工具函数 | AI utility functions
├── 功能模块 | Function Modules
│   ├── tools.py            # 基础工具 | Basic tools
│   ├── astronomy.py        # 天文海报 | Astronomical posters
│   ├── wordstats.py        # 词频统计 | Word statistics
│   └── message_stats.py    # 消息统计 | Message statistics
├── 管理模块 | Management Modules
│   ├── admin.py            # 基础管理 | Basic management
│   └── root_manager.py     # 超级管理员 | Super administrator
└── 数据存储 | Data Storage
    ├── data/               # 数据文件 | Data files
    ├── output/             # 输出文件 | Output files
    ├── astronomy_images/   # 天文图片资源 | Astronomical image resources
    │   ├── 1.jpg ~ 12.jpg  # 月份背景图 | Monthly background images
    │   ├── default.jpg     # 默认背景图 | Default background image
    │   └── logo.png        # LOGO图片 | Logo image
    ├── fonts/              # 字体资源 | Font resources
    └── logs/               # 日志文件 | Log files
```

### 🔄 消息处理流程 | Message Processing Flow
```
QQ消息 | QQ Message → 接收处理 | Receive → 权限检查 | Permission Check → 功能路由 | Function Routing → AI处理 | AI Processing → 响应生成 | Response Generation → 发送回复 | Send Reply
```

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
在文件夹xiaotian/data/fonts/ 中添加你自己的字体文件，并命名为default.ttf , text.TTF , art.TTF , ciyun.TTF
```

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

### 定时任务配置 | Scheduled Task Configuration
```python
DAILY_WEATHER_TIME = "19:00"      # 天气播报时间 | Weather report time
DAILY_STATS_TIME = "20:00"        # 统计报告时间 | Statistics report time
DAILY_ASTRONOMY_TIME = "08:00"    # 天文海报时间 | Astronomy poster time
MONTHLY_ASTRONOMY_TIME = "09:00"  # 月度合集时间 | Monthly collection time
CLEANUP_TIME = "03:00"            # 数据清理时间 | Data cleanup time
```

## 📖 使用指南 | User Guide

### 👤 普通用户 | Regular Users

#### 触发对话 | Trigger Conversation
```
小天，今天的天气怎么样？| Xiaotian, what's the weather like today?
小天 你知道今晚能看到什么星座吗？| Xiaotian, do you know what constellations can be seen tonight?
./帮我制作一张天文海报 | ./Help me make an astronomical poster
```

#### 🎨 天文海报制作 | Astronomical Poster Creation
**格式 | Format:**
```
小天，每日天文做好啦：
今天是2024年8月4日，正值夏季观星的黄金时期。
夜空中最显著的是银河系的中心部分...
（400-600字的天文内容）

Xiaotian, daily astronomy is ready:
Today is August 4, 2024, the golden period for summer stargazing.
The most prominent in the night sky is the central part of the Milky Way...
(400-600 words of astronomical content)
```

**新功能特点 | New Features:**
- ✨ **智能LOGO展示**：左上角自动添加Logo，支持亮度优化 | Smart logo display in upper left corner with brightness optimization
- 🖼️ **用户图片支持**：可插入自定义图片 | Support for custom image insertion
- 🎨 **智能排版**：自动调整文字和图片布局 | Intelligent layout with automatic text and image adjustment
- 📅 **日期框美化**：右上角精美的日期显示框 | Beautiful date display box in upper right corner

### 👑 Root管理员 | Root Administrator

#### 📁 资源管理 | Resource Management
**上传图片资源 | Upload Image Resources:**
```
# 发送图片文件并配合指令 | Send image file with command
小天，上传背景图片：[文件名].jpg | Xiaotian, upload background image: [filename].jpg
小天，上传LOGO：logo.png | Xiaotian, upload logo: logo.png
```

**上传字体资源 | Upload Font Resources:**
```
# 发送字体文件并配合指令 | Send font file with command  
小天，上传字体：[字体名].ttf | Xiaotian, upload font: [fontname].ttf
小天，上传字体：[字体名].otf | Xiaotian, upload font: [fontname].otf
```

**支持的文件类型 | Supported File Types:**
- **图片 | Images**: .png, .jpg, .jpeg
- **字体 | Fonts**: .ttf, .otf

#### ⚙️ 系统配置 | System Configuration
```
小天，设置目标群组：群号1,群号2 | Set target groups: group1,group2
小天，设置天气城市：城市名 | Set weather city: cityname
小天，添加管理员：QQ号 | Add admin: QQ number
小天，添加黑名单：QQ号 | Add blacklist: QQ number
小天，查看设置 | View settings
小天，查看统计 | View statistics
``` | System Configuration

#### 🔄 实时控制 | Real-time Control
```
小天，发送消息到群：群号：消息内容 | Send message to group: groupID: message
小天，重启系统 | Restart system
小天，清理数据 | Clean data
小天，查看日志 | View logs

详细的Root管理员功能请参考： Root功能说明文档

## 🛠️ 开发文档 | Development Documentation

### 📁 模块说明 | Module Description

#### 🤖 AI核心 (ai_core.py) | AI Core
- `XiaotianAI`: AI接口核心类 | AI interface core class
- `get_response()`: 获取AI回复 | Get AI response
- `detect_emotion()`: 情绪检测 | Emotion detection
- 独立记忆管理 | Independent memory management

#### 📋 调度器 (scheduler.py) | Scheduler
- `XiaotianScheduler`: 消息调度核心 | Message scheduling core
- `process_message()`: 消息处理入口 | Message processing entry
- 定时任务管理 | Scheduled task management
- Root权限集成 | Root permission integration

#### 🎨 天文海报 (astronomy.py) | Astronomy Poster
- `AstronomyPoster`: 海报生成类 | Poster generation class
- **新增LOGO功能 | New Logo Feature**: 
  - 自动LOGO加载和位置调整 | Automatic logo loading and position adjustment
  - 亮度优化算法 | Brightness optimization algorithm
  - 智能尺寸适配 | Intelligent size adaptation

#### 👑 Root管理 (root_manager.py) | Root Management
- `RootManager`: 超级管理员功能 | Super administrator functionality
- **资源文件管理 | Resource File Management**:
  - 图片上传和分类存储 | Image upload and categorized storage
  - 字体上传和管理 | Font upload and management
  - 文件类型验证 | File type validation
- 配置动态修改 | Dynamic configuration modification
- 实时消息发送 | Real-time message sending

#### 📊 工具模块 | Tool Modules
- `tools.py`: 基础工具（天气、图表等）| Basic tools (weather, charts, etc.)
- `wordstats.py`: 词频统计分析 | Word frequency statistical analysis  
- `message_stats.py`: 消息数据统计 | Message data statistics

### 🔧 扩展开发 | Extension Development
1. 在对应模块中添加新功能 | Add new features in corresponding modules
2. 在调度器中注册新的消息处理逻辑 | Register new message processing logic in scheduler
3. 在Root管理中添加配置项（如需要）| Add configuration items in Root management (if needed)
4. 更新配置文件和文档 | Update configuration files and documentation

### 💾 数据存储 | Data Storage
- `data/`: JSON格式的配置和数据文件 | JSON format configuration and data files
- `output/`: 生成的图片和图表文件 | Generated images and chart files
- `astronomy_images/`: 天文图片资源目录 | Astronomical image resource directory
- `fonts/`: 字体资源目录 | Font resource directory
- `logs/`: 运行日志文件 | Runtime log files

## 📝 更新日志 | Update Log

### v2.1 (当前版本 | Current Version)
- ✅ **新增LOGO功能**：天文海报左上角智能LOGO展示 | **New Logo Feature**: Smart logo display in upper left corner of astronomy posters
- ✅ **亮度优化**：LOGO自动亮度和对比度增强 | **Brightness Optimization**: Automatic brightness and contrast enhancement for logo
- ✅ **资源管理增强**：支持直接上传图片和字体资源 | **Enhanced Resource Management**: Support direct upload of images and font resources
- ✅ **文件分类存储**：自动分类存储上传的资源文件 | **Categorized File Storage**: Automatically categorize and store uploaded resource files

### v2.0
- ✅ 新增Root超级管理员系统 | Added Root super administrator system
- ✅ 实现智能气氛调节功能 | Implemented intelligent atmosphere adjustment
- ✅ 添加独立记忆系统 | Added independent memory system
- ✅ 性格升级，更加活泼可爱 | Personality upgrade, more lively and cute
- ✅ 定时任务真实化发送 | Realistic sending of scheduled tasks

### v1.0 (基础版本 | Basic Version)
- ✅ 基础QQ机器人功能 | Basic QQ bot functionality
- ✅ AI对话系统 | AI dialogue system
- ✅ 天文海报制作 | Astronomical poster creation
- ✅ 词频统计分析 | Word frequency statistical analysis
- ✅ 定时任务框架 | Scheduled task framework

## 🤝 支持与反馈 | Support and Feedback

如果您在使用过程中遇到问题或有建议，请 | If you encounter problems or have suggestions during use, please:

1. 查看本文档和Root功能说明 | Check this documentation and Root function instructions
2. 检查日志文件获取错误信息 | Check log files for error information
3. 使用Root命令 `小天，查看设置` 检查配置 | Use Root command `Xiaotian, view settings` to check configuration
4. 确认资源文件是否正确上传到对应目录 | Confirm that resource files are correctly uploaded to corresponding directories

## 📄 许可证 | License

MIT License（仅限于项目本身，依赖请自行遵守第三方协议，本项目未包含任何依赖源码或可执行文件）

## 第三方依赖说明

本项目依赖 NapCat 作为通信代理工具。  
NapCat 采用其自定义的“有限再分发许可证”，本项目未包含其任何源码或可执行文件。 
请前往 NapCat 官方仓库获取并遵守其许可证：
🔗 https://github.com/NapNeko/NapCatQQ


---

**小天 - 让AI更懂你，让天文更有趣！⭐**  
**Xiaotian - Making AI understand you better, making astronomy more interesting! ⭐**