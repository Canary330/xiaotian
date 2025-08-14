"""
小天的工具模块
包含海报制作、天气获取、图表生成等功能
"""

import json
import re
from datetime import datetime
import random
from typing import Dict, Any
from ..manage.root_manager import RootManager
from .message import MessageSender


class WeatherTools:
    def __init__(self, root_manager=None):
        if root_manager is None:
            raise ValueError("WeatherTools requires a RootManager instance")
        self.root_manager = root_manager
        self.message_sender = MessageSender(self.root_manager, None)  # AI核心暂时不需要传入
    
    def daily_weather_task(self):
        """每日天气任务"""
        if not self.root_manager.is_feature_enabled('daily_weather'):
            return
            
        print(f"🌤️ {datetime.now().strftime('%H:%M')} - 执行每日天气任务")
        
        # 获取天气信息
        city = self.root_manager.get_weather_city()
        weather_info = self.get_weather_info(city)

        if "error" not in weather_info:
            # 生成天气报告
            weather_report = self._format_weather_report(weather_info)
            print(f"📢 天气播报：\n{weather_report}")
            
            # 发送到目标群组
            target_groups = self.root_manager.get_target_groups()
            if target_groups:
                self.message_sender.send_message_to_groups(weather_report)
            else:
                print("⚠️ 没有设置目标群组，天气报告未发送。请使用命令'小天，设置目标群组：群号1,群号2'来设置目标群组。")
        else:
            print(f"❌ 天气获取失败：{weather_info['error']}")

    def _format_weather_report(self, weather_info: dict) -> str:
        """格式化天气报告"""
        # 检查是否有错误信息
        if 'error' in weather_info:
            return f"🌤️ 天气预报服务暂时不可用\n\n{weather_info.get('error', '无法获取天气数据')}\n\n稍后再试喵~"
            
        return f"""🌤️ 今晚观星天气预报

📍 地点：{weather_info['location']}
🌡️ 温度：{weather_info['temperature']}°C
☁️ 天气：{weather_info['weather']}
💧 湿度：{weather_info['humidity']}%
💨 风速：{weather_info['wind_speed']}km/h
👁️ 能见度：{weather_info['visibility']}

{weather_info['stargazing_advice']}"""
    

    def get_weather_info(self, location: str = None) -> Dict[str, Any]:
        """获取天气信息 - 使用Moonshot API搜索天气数据"""
        try:
            # 如果没有提供地点，使用默认地点
            if not location:
                location = "双流"  # 默认位置
                
            print(f"开始获取天气信息，地点: {location}")
                
            # 构建搜索查询
            current_date = datetime.now().strftime("%Y年%m月%d日")
            time_of_day = "今晚" if datetime.now().hour >= 12 else "今天"
            query = f"{current_date} {location}地区{time_of_day}天气详细预报，包括温度、湿度、风力、能见度、云量和空气质量。分析这些数据对于天文观测的影响，判断是否适合观星，返回JSON格式。"
            
            print(f"天气查询参数: 日期={current_date}, 时段={time_of_day}")
            
            # 导入AI核心，利用已有的Moonshot API连接
            from ..ai.ai_core import XiaotianAI
            ai = XiaotianAI()
            
            # 构造天气查询系统提示词和用户提示词
            system_prompt = """你是专业的气象与天文观测助手。
请根据提供的地点和日期，返回详细的天气预报和对天文观测的影响分析。
必须以有效的JSON格式返回以下信息:
{
  "location": "地点名称",
  "weather": "天气状况(如晴、多云、小雨等)",
  "temperature": 温度数字(不含单位),
  "humidity": 湿度百分比数字(不含百分号),
  "wind_speed": 风速数字(km/h),
  "visibility": "能见度描述(极佳/良好/一般/较差/很差)",
  "cloud_cover": "云量描述(晴朗/少云/多云/阴天)",
  "observation_quality": "观星条件(极佳/良好/一般/较差/不适合)",
  "advice": "针对天文观测的简短建议"
}
严格遵循此格式，确保返回的是有效JSON，不要添加额外文本。数据应尽可能准确反映当前天气状况。"""
            
            print("发送天气查询请求到AI...")
            weather_response = ai.query_with_prompt(system_prompt, query)
            print(f"AI返回原始响应: {weather_response[:200]}...")
            
            # 解析JSON响应
            try:
                # 首先清理响应文本，确保只包含有效JSON
                json_str = weather_response
                # 查找JSON开始的位置
                json_start = weather_response.find('{')
                json_end = weather_response.rfind('}')
                if json_start >= 0 and json_end > json_start:
                    json_str = weather_response[json_start:json_end+1]
                    print(f"提取的JSON字符串: {json_str[:100]}...")
                
                # 尝试解析JSON
                weather_data = json.loads(json_str)
                print(f"成功解析JSON数据: {list(weather_data.keys())}")
                
                # 提取信息，确保有默认值
                weather = weather_data.get("weather", "未知")
                temperature = weather_data.get("temperature", 20)
                humidity = weather_data.get("humidity", 50)
                wind_speed = weather_data.get("wind_speed", 5)
                visibility = weather_data.get("visibility", "一般")
                cloud_cover = weather_data.get("cloud_cover", "未知")
                observation_quality = weather_data.get("observation_quality", "一般")
                advice = weather_data.get("advice", "")
                
                # 转换为数字类型
                if isinstance(temperature, str):
                    temperature = int(re.search(r'-?\d+', temperature).group()) if re.search(r'-?\d+', temperature) else 20
                if isinstance(humidity, str):
                    humidity = int(re.search(r'\d+', humidity).group()) if re.search(r'\d+', humidity) else 50
                if isinstance(wind_speed, str):
                    wind_speed = int(re.search(r'\d+', wind_speed).group()) if re.search(r'\d+', wind_speed) else 5
                
                print(f"处理后的天气数据: 天气={weather}, 温度={temperature}, 湿度={humidity}, 风速={wind_speed}, 能见度={visibility}")
                
                # 观星建议逻辑
                is_good_for_stargazing = (
                    weather in ["晴", "晴朗", "少云"] and 
                    wind_speed < 15 and 
                    visibility in ["极佳", "良好", "高"]
                )
                
                # 如果API返回了观星条件，使用它来确定是否适合观星
                if observation_quality:
                    is_good_for_stargazing = observation_quality in ["极佳", "良好"]
                
                # 优先使用API提供的建议，否则生成
                stargazing_advice = advice if advice else self._get_stargazing_advice(weather, visibility, wind_speed)
                
                weather_info = {
                    "location": location,
                    "date": current_date,
                    "weather": weather,
                    "temperature": temperature,
                    "humidity": humidity,
                    "wind_speed": wind_speed,
                    "visibility": visibility,
                    "cloud_cover": cloud_cover,
                    "observation_quality": observation_quality,
                    "good_for_stargazing": is_good_for_stargazing,
                    "stargazing_advice": stargazing_advice
                }
                
                print(f"生成的天气信息: {weather_info}")
                
                return weather_info
                
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"❌ 解析天气数据失败: {e}")
                print(f"问题的响应内容: {weather_response}")
                
                # 生成备用天气数据
                fallback_weather = self._generate_fallback_weather(location)
                print(f"使用备用天气数据: {fallback_weather}")
                return fallback_weather
                
        except Exception as e:
            print(f"❌ 天气获取总体失败: {e}")
            import traceback
            print(traceback.format_exc())
            
            # 生成备用天气数据
            fallback_weather = self._generate_fallback_weather(location)
            print(f"使用备用天气数据: {fallback_weather}")
            return fallback_weather
            
    def _generate_fallback_weather(self, location: str):
        """生成备用天气数据"""
        current_date = datetime.now().strftime("%Y年%m月%d日")
        current_hour = datetime.now().hour
        
        # 根据时段生成合理的备用数据
        if 6 <= current_hour < 18:  # 白天
            weathers = ["晴", "多云", "晴间多云"]
            temp_range = (20, 30)
            visibility_options = ["良好", "极佳"]
        else:  # 夜晚
            weathers = ["晴", "多云", "少云"]
            temp_range = (15, 25)
            visibility_options = ["良好", "一般"]
        
        weather = random.choice(weathers)
        temperature = random.randint(temp_range[0], temp_range[1])
        humidity = random.randint(40, 70)
        wind_speed = random.randint(2, 10)
        visibility = random.choice(visibility_options)
        
        # 观星建议逻辑
        is_good_for_stargazing = (
            weather in ["晴", "晴朗", "少云"] and 
            wind_speed < 15 and 
            visibility in ["极佳", "良好", "高"]
        )
        
        cloud_cover = "晴朗" if weather == "晴" else ("少云" if weather == "少云" else "多云")
        observation_quality = "良好" if is_good_for_stargazing else "一般"
        
        print(f"生成备用天气数据: 地点={location}, 天气={weather}, 温度={temperature}, 适合观星={is_good_for_stargazing}")
        
        return {
            "location": location,
            "date": current_date,
            "weather": weather,
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "visibility": visibility,
            "cloud_cover": cloud_cover,
            "observation_quality": observation_quality,
            "good_for_stargazing": is_good_for_stargazing,
            "stargazing_advice": self._get_stargazing_advice(weather, visibility, wind_speed)
        }
        
    def _get_stargazing_advice(self, weather: str, visibility: str, wind_speed: int) -> str:
        """生成观星建议"""
        current_hour = datetime.now().hour
        
        # 优质观星条件
        if weather in ["晴", "晴朗"] and visibility in ["极佳", "良好"] and wind_speed < 10:
            advice_options = [
                "🌟 今晚是观星的绝佳时机！天空晴朗，能见度高，适合深空观测。",
                "✨ 观测条件极佳！适合拍摄深空天体，银河核心区域应清晰可见。",
                "🔭 绝佳观星夜！低风速和高透明度使望远镜观测达到最佳效果。",
                "🌌 今晚天气完美！如果远离城市光污染，可能看到数千颗恒星。"
            ]
            return random.choice(advice_options)
            
        # 良好观星条件
        elif weather in ["晴", "晴朗", "少云"] and visibility in ["良好", "一般"] and wind_speed < 15:
            advice_options = [
                "🌙 今晚观星条件良好，适合观测明亮的天体如月球、行星和一等星。",
                "💫 不错的观测夜，虽然能见度不是最佳，但主要星座和亮星清晰可见。",
                "🪐 适合行星观测的夜晚！即使透明度不完美，也能看清行星细节。",
                "👁️ 观测条件不错，肉眼可见主要星座，双筒镜或小型望远镜效果较好。"
            ]
            return random.choice(advice_options)
            
        # 一般观星条件
        elif weather in ["多云", "晴间多云", "部分多云"] and visibility in ["一般", "良好"]:
            advice_options = [
                "☁️ 云量较多，可能只能在云缝间偶尔看到星星，建议关注天气变化。",
                "👀 观测条件一般，可能会有部分时段云层散开，届时可观测亮星和行星。",
                "🔍 断续观测之夜，准备好快速抓住云层散开的时机观测明亮天体。",
                "📱 建议使用天文APP追踪云层变化，抓住临时观测窗口。"
            ]
            return random.choice(advice_options)
            
        # 不适合观星
        else:
            # 更具体的建议
            if "雨" in weather or "雪" in weather:
                advice_options = [
                    "🌧️ 今晚有降水，不适合观星。建议在室内学习天文知识或处理设备。",
                    "💻 天气不佳，推荐使用虚拟天文台软件或观看天文纪录片。",
                    "🛠️ 适合进行望远镜维护或整理过去的观测记录和照片的雨夜。",
                    "📚 不适合观测，是阅读天文书籍或规划未来观测计划的好时机。"
                ]
            elif "雾" in weather or visibility in ["较差", "很差"]:
                advice_options = [
                    "🌫️ 能见度太低，星光会严重散射。建议改期观测。",
                    "⚠️ 高湿度和低能见度会影响光学设备，不建议今晚使用望远镜。",
                    "📅 因雾气影响观测质量，建议等待更清澈的夜空。",
                    "🧹 不适合观测的雾天，可以利用时间清洁和校准设备。"
                ]
            elif wind_speed >= 15:
                advice_options = [
                    "💨 风速过高，会导致望远镜震动影响观测质量，不建议户外活动。",
                    "🌬️ 强风会使望远镜跟踪困难，建议另选风速较低的夜晚观测。",
                    "⛔ 风力太强，可能危及设备安全，今晚不适合架设望远镜。",
                    "📋 因风力较大，建议改为室内天文活动或规划未来的观测。"
                ]
            else:
                advice_options = [
                    "❌ 今晚天气条件不适合观星，建议调整计划等待更好的观测机会。",
                    "🏠 夜空状况不佳，推荐室内天文活动或天文摄影后期处理。",
                    "⏱️ 观测条件不理想，可以利用这段时间学习新的天文知识或调试设备。",
                    "🔄 建议暂缓观测计划，关注未来几天天气预报选择更佳观测时机。"
                ]
            return random.choice(advice_options)