"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of model identifiers (SiliconFlow 模型)
COUNCIL_MODELS = [
    "deepseek-ai/DeepSeek-R1",
    "deepseek-ai/DeepSeek-V3",
    "Pro/zai-org/GLM-4.7",
    "Qwen/Qwen2.5-72B-Instruct"
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "deepseek-ai/DeepSeek-V3"

# API endpoint (修改为硅基流动地址)
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://api.siliconflow.cn/v1/chat/completions")

# Data directory for conversation storage
DATA_DIR = "data/conversations"
