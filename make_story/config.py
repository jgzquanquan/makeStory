import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_NAME = "gpt-4o-mini"
ENV_PATH = ROOT_DIR / ".env"


def _read_env_file() -> dict[str, str]:
	if not ENV_PATH.exists():
		return {}

	entries: dict[str, str] = {}
	for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		entries[key.strip()] = value.strip()
	return entries


def get_runtime_settings() -> dict[str, str]:
	file_values = _read_env_file()
	return {
		"openai_api_key": file_values.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
		"base_url": file_values.get("BASE_URL") or os.getenv("BASE_URL", ""),
		"model_name": file_values.get("MODEL_NAME") or os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME),
	}


def get_openai_api_key() -> str:
	return get_runtime_settings()["openai_api_key"]


def get_base_url() -> str:
	return get_runtime_settings()["base_url"]


def get_model_name() -> str:
	return get_runtime_settings()["model_name"]


# 控制创意轮数与分集数等默认参数
DEFAULT_MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "2"))
DEFAULT_NUM_EPISODES: int = int(os.getenv("NUM_EPISODES", "6"))


def ensure_api_key() -> None:
	if not get_openai_api_key():
		raise RuntimeError("缺少 OPENAI_API_KEY，请在环境变量或 .env 文件中配置。")
