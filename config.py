# config.py
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    # 是否使用LLM
    #IS_LLM_RUN = True
    IS_LLM_RUN = False

    # DeepSeek API配置
    MY_LLM_API_KEY = os.getenv('MY_DEEPSEEK_API_KEY')
    MY_LLM_API_URL = "https://api.deepseek.com/v1/chat/completions"

    # 模型配置
    MODEL_NAME = "deepseek-coder"
    TEMPERATURE = 0.1  # 低温度保证评分一致性

    # 请求配置
    TIMEOUT = 30

    # 验证配置
    @classmethod
    def validate_config(cls):
        if not cls.MY_LLM_API_KEY:
            raise ValueError("❌ 未找到DEEPSEEK_API_KEY环境变量，请检查.env文件配置")
        print("✅ 配置验证通过")


# 验证配置
Config.validate_config()