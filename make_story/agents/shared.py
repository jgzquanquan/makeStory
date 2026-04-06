from .types import NodeOutput
from ..state import PipelineState


def story_bible_text(state: PipelineState) -> str:
	sb = state.story_bible
	main_characters = "\n- ".join(sb.main_characters) if sb.main_characters else "待补充"
	episode_arcs = "\n- ".join(sb.episode_arcs) if sb.episode_arcs else "待补充"
	return (
		f"世界观: {sb.world}\n"
		f"核心冲突: {sb.core_conflict}\n"
		f"主题: {sb.theme}\n"
		f"基调: {sb.tone}\n"
		f"主要人物:\n- {main_characters}\n"
		f"分集弧线:\n- {episode_arcs}"
	)


__all__ = ["NodeOutput", "story_bible_text"]
