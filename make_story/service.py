import json
import os
import time
from typing import Any, Callable, Dict, List

from pydantic import BaseModel, Field

from .agents import (
	node_generate_characters,
	node_generate_outline,
	node_multi_ideation,
	node_plan_episodes,
	node_review_outline,
	node_rewrite_outline,
	node_select_best,
	node_write_episode,
)
from .config import DEFAULT_MODEL_NAME, ENV_PATH, get_runtime_settings
from .db import save_story
from .llm import ChatLLM, MockLLM, as_messages
from .state import PipelineState


class TopicPreset(BaseModel):
	id: str
	label: str
	topic: str
	constraints: str


class GenerateRequest(BaseModel):
	topic: str
	constraints: str = ""
	num_episodes: int = Field(default=6, ge=1, le=20)
	max_iterations: int = Field(default=2, ge=1, le=10)
	mock: bool = False
	api_key: str = ""
	model_name: str = DEFAULT_MODEL_NAME
	base_url: str = ""


class ProgressEvent(BaseModel):
	key: str
	label: str
	status: str
	message: str
	data: Dict[str, Any] = Field(default_factory=dict)


class ModelTestResult(BaseModel):
	ok: bool
	model_name: str
	base_url: str
	latency_ms: int
	response_preview: str
	message: str


ProgressCallback = Callable[[ProgressEvent], None]

PIPELINE_STAGES: List[tuple[str, str]] = [
	("ideation", "创意池"),
	("selection", "选题与 Bible"),
	("outline", "大纲设计"),
	("review", "审稿迭代"),
	("planning", "分集规划"),
	("writing", "分集写作"),
]


TOPIC_PRESETS: List[TopicPreset] = [
	TopicPreset(
		id="urban-romance",
		label="都市情感",
		topic="都市情感悬疑",
		constraints="女性向短剧，6集，每集3分钟，要求强钩子和情绪拉扯",
	),
	TopicPreset(
		id="revenge",
		label="复仇反转",
		topic="豪门复仇反转",
		constraints="竖屏短剧，8集，每集2-3分钟，强调身份反转和爽点密度",
	),
	TopicPreset(
		id="workplace",
		label="职场逆袭",
		topic="女性职场逆袭",
		constraints="面向短视频平台，6集，每集3分钟，节奏快，适合爆点剪辑",
	),
	TopicPreset(
		id="fantasy",
		label="古风奇幻",
		topic="古风权谋奇幻",
		constraints="女性向，8集，每集4分钟，强调世界观轻量、人物关系浓",
	),
	TopicPreset(
		id="family",
		label="家庭伦理",
		topic="家庭伦理反击",
		constraints="下沉市场短剧，6集，每集3分钟，矛盾强烈，价值观清晰",
	),
	TopicPreset(
		id="youth",
		label="青春校园",
		topic="青春校园成长",
		constraints="年轻用户向，6集，每集3分钟，人物鲜明，台词有记忆点",
	),
]


def create_llm(request: GenerateRequest) -> ChatLLM | MockLLM:
	settings = get_runtime_settings()
	if request.mock:
		return MockLLM()
	return ChatLLM(
		model=request.model_name or settings["model_name"],
		api_key=request.api_key or settings["openai_api_key"],
		base_url=request.base_url or settings["base_url"],
	)


def apply_state_update(state: PipelineState, update: Dict[str, Any]) -> PipelineState:
	data = state.model_dump()
	for key, value in update.items():
		if hasattr(value, "model_dump"):
			data[key] = value.model_dump()
		elif isinstance(value, list):
			data[key] = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
		else:
			data[key] = value
	return PipelineState.model_validate(data)


def run_ideation_step(state: PipelineState, llm: ChatLLM | MockLLM) -> Dict[str, Any]:
	return node_multi_ideation(state, llm)


def run_selection_step(state: PipelineState, llm: ChatLLM | MockLLM) -> Dict[str, Any]:
	return node_select_best(state, llm)


def run_outline_step(state: PipelineState, llm: ChatLLM | MockLLM) -> Dict[str, Any]:
	state = apply_state_update(state, node_generate_outline(state, llm))
	return node_generate_characters(state, llm)


def run_review_step(state: PipelineState, llm: ChatLLM | MockLLM) -> Dict[str, Any]:
	return node_review_outline(state, llm)


def run_rewrite_step(state: PipelineState, llm: ChatLLM | MockLLM) -> Dict[str, Any]:
	return node_rewrite_outline(state, llm)


def run_episode_planning_step(state: PipelineState, llm: ChatLLM | MockLLM) -> Dict[str, Any]:
	return node_plan_episodes(state, llm)


def run_episode_writing_step(state: PipelineState, llm: ChatLLM | MockLLM, index: int) -> str:
	return node_write_episode(state, llm, index)


def build_stage_preview(state: PipelineState, key: str) -> Dict[str, Any]:
	if key == "ideation":
		return {
			"ideas": [idea.model_dump() for idea in state.ideas],
		}
	if key == "selection":
		return {
			"selected_idea": state.selected_idea.model_dump() if state.selected_idea else None,
			"selection_reason": state.selection_reason,
			"story_bible": state.story_bible.model_dump(),
		}
	if key == "outline":
		return {
			"outline": state.outline or "",
			"characters": state.characters or "",
		}
	if key == "review":
		return {
			"review": state.review.model_dump(),
			"iteration": state.iteration,
		}
	if key == "planning":
		return {
			"episode_plans": [item.model_dump() for item in state.episode_plans],
		}
	if key == "writing":
		return {
			"episodes": state.episodes,
			"episodes_completed": len(state.episodes),
			"num_episodes": state.num_episodes,
		}
	return {}


def emit_progress(
	progress: ProgressCallback | None,
	key: str,
	label: str,
	status: str,
	message: str,
	data: Dict[str, Any] | None = None,
) -> None:
	if progress is None:
		return
	progress(ProgressEvent(key=key, label=label, status=status, message=message, data=data or {}))


def run_pipeline(request: GenerateRequest, progress: ProgressCallback | None = None) -> PipelineState:
	llm = create_llm(request)

	state = PipelineState(
		topic=request.topic,
		constraints=request.constraints,
		num_episodes=request.num_episodes,
		max_iterations=request.max_iterations,
	)

	emit_progress(progress, "ideation", "创意池", "running", "多 Agent 正在产出候选题材")
	state = apply_state_update(state, run_ideation_step(state, llm))
	emit_progress(
		progress,
		"ideation",
		"创意池",
		"done",
		f"已生成 {len(state.ideas)} 个候选创意",
		build_stage_preview(state, "ideation"),
	)

	emit_progress(progress, "selection", "选题与 Bible", "running", "正在选择最佳创意并生成故事 Bible")
	state = apply_state_update(state, run_selection_step(state, llm))
	selected_title = state.selected_idea.title if state.selected_idea else "未命名"
	emit_progress(
		progress,
		"selection",
		"选题与 Bible",
		"done",
		f"已选定《{selected_title}》",
		build_stage_preview(state, "selection"),
	)

	emit_progress(progress, "outline", "大纲设计", "running", "正在生成总大纲和人物骨架")
	state = apply_state_update(state, run_outline_step(state, llm))
	emit_progress(
		progress,
		"outline",
		"大纲设计",
		"done",
		"大纲和人物设定已生成",
		build_stage_preview(state, "outline"),
	)

	approved = False
	while not approved:
		emit_progress(progress, "review", "审稿迭代", "running", f"第 {state.iteration + 1} 轮审稿中")
		state = apply_state_update(state, run_review_step(state, llm))
		if state.review.approved:
			approved = True
			emit_progress(
				progress,
				"review",
				"审稿迭代",
				"done",
				"审稿通过，进入分集规划",
				build_stage_preview(state, "review"),
			)
			break
		if state.iteration >= state.max_iterations:
			approved = True
			state = apply_state_update(
				state,
				{
					"review": state.review.model_copy(update={"approved": True}),
				},
				)
			emit_progress(
				progress,
				"review",
				"审稿迭代",
				"done",
				"达到最大迭代次数，按当前版本继续产出",
				build_stage_preview(state, "review"),
			)
			break
		emit_progress(
			progress,
			"review",
			"审稿迭代",
			"running",
			"根据审稿意见重写大纲",
			build_stage_preview(state, "review"),
		)
		state = apply_state_update(state, run_rewrite_step(state, llm))

	emit_progress(progress, "planning", "分集规划", "running", "正在拆分每集目标、钩子和节拍")
	state = apply_state_update(state, run_episode_planning_step(state, llm))
	emit_progress(
		progress,
		"planning",
		"分集规划",
		"done",
		f"已完成 {len(state.episode_plans)} 集规划",
		build_stage_preview(state, "planning"),
	)

	emit_progress(progress, "writing", "分集写作", "running", "正在逐集生成剧本文本")
	episodes: List[str] = []
	for index in range(1, state.num_episodes + 1):
		emit_progress(progress, "writing", "分集写作", "running", f"正在编写第 {index}/{state.num_episodes} 集")
		episodes.append(run_episode_writing_step(state, llm, index))
		state = apply_state_update(state, {"episodes": episodes})
		emit_progress(
			progress,
			"writing",
			"分集写作",
			"running",
			f"正在编写第 {index}/{state.num_episodes} 集",
			build_stage_preview(state, "writing"),
		)
	emit_progress(progress, "writing", "分集写作", "done", "全部分集剧本已生成", build_stage_preview(state, "writing"))

	return state


def test_model_connection(request: GenerateRequest) -> ModelTestResult:
	start = time.perf_counter()
	llm = create_llm(request)
	settings = get_runtime_settings()

	if request.mock:
		reply = "MOCK 通路正常"
	else:
		reply = llm.invoke(
			as_messages(
				"你是模型连通性探针。只回答一行简短文本。",
				"请回复：模型连接成功",
			),
			temperature=0,
		)

	latency_ms = int((time.perf_counter() - start) * 1000)
	return ModelTestResult(
		ok=True,
		model_name=request.model_name or settings["model_name"],
		base_url=request.base_url or settings["base_url"],
		latency_ms=latency_ms,
		response_preview=reply[:200],
		message="模型连接成功",
	)


def serialize_state(state: PipelineState) -> Dict[str, Any]:
	return {
		"selected_idea": state.selected_idea.model_dump() if state.selected_idea else None,
		"selection_reason": state.selection_reason,
		"story_bible": state.story_bible.model_dump(),
		"outline": state.outline or "",
		"characters": state.characters or "",
		"review": state.review.model_dump(),
		"episode_plans": [item.model_dump() for item in state.episode_plans],
		"episodes": state.episodes,
	}


def persist_story(request: GenerateRequest, state: PipelineState) -> int:
	title = (
		state.selected_idea.title
		if state.selected_idea and state.selected_idea.title.strip()
		else request.topic.strip() or "未命名剧本"
	)
	return save_story(
		title=title,
		topic=request.topic,
		constraints=request.constraints,
		notes="",
		num_episodes=state.num_episodes,
		max_iterations=state.max_iterations,
		result=serialize_state(state),
	)


def load_runtime_config() -> Dict[str, str]:
	settings = get_runtime_settings()
	api_key = settings["openai_api_key"]
	return {
		"api_key": "",
		"api_key_hint": mask_secret(api_key),
		"has_api_key": "true" if bool(api_key) else "false",
		"model_name": settings["model_name"],
		"base_url": settings["base_url"],
	}


def save_runtime_config(api_key: str, model_name: str, base_url: str) -> None:
	env_path = ENV_PATH
	settings = get_runtime_settings()
	entries: Dict[str, str] = {}
	if env_path.exists():
		for raw_line in env_path.read_text(encoding="utf-8").splitlines():
			line = raw_line.strip()
			if not line or line.startswith("#") or "=" not in line:
				continue
			key, value = line.split("=", 1)
			entries[key] = value

	entries["OPENAI_API_KEY"] = api_key.strip() or settings["openai_api_key"]
	entries["MODEL_NAME"] = model_name.strip() or settings["model_name"]
	entries["BASE_URL"] = base_url.strip()

	content = "\n".join(f"{key}={value}" for key, value in entries.items()) + "\n"
	env_path.write_text(content, encoding="utf-8")
	os.environ["OPENAI_API_KEY"] = entries["OPENAI_API_KEY"]
	os.environ["MODEL_NAME"] = entries["MODEL_NAME"]
	os.environ["BASE_URL"] = entries["BASE_URL"]


def presets_as_json() -> str:
	return json.dumps([item.model_dump() for item in TOPIC_PRESETS], ensure_ascii=False)


def mask_secret(secret: str) -> str:
	if not secret:
		return ""
	if len(secret) <= 8:
		return "*" * len(secret)
	return f"{secret[:4]}...{secret[-4:]}"


def initial_progress_stages() -> List[Dict[str, str]]:
	return [
		{"key": key, "label": label, "status": "pending", "message": "等待开始"}
		for key, label in PIPELINE_STAGES
	]
