import os
from dotenv import load_dotenv


load_dotenv()


OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
BASE_URL: str | None = os.getenv("BASE_URL")  # 自定义 API 地址
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")

# 控制创意轮数与分集数等默认参数
DEFAULT_MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "2"))
DEFAULT_NUM_EPISODES: int = int(os.getenv("NUM_EPISODES", "6"))


def ensure_api_key() -> None:
	if not OPENAI_API_KEY:
		raise RuntimeError(
			"缺少 OPENAI_API_KEY，请在环境变量或 .env 文件中配置。"
		)


