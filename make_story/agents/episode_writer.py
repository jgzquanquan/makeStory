from ..llm import ChatLLM, as_messages
from ..prompts import EPISODE_USER_TMPL, SYSTEM_ARCHITECT
from ..state import PipelineState
from .shared import story_bible_text


def node_write_episode(state: PipelineState, llm: ChatLLM, index: int) -> str:
	plan = next((item for item in state.episode_plans if item.episode_number == index), None)
	context = (
		f"标题:\n{state.selected_idea.title if state.selected_idea else ''}\n\n"
		f"故事 bible:\n{story_bible_text(state)}\n\n"
		f"大纲:\n{state.outline}\n\n人物设定:\n{state.characters}"
	)
	user_prompt = f"{context}\n\n{EPISODE_USER_TMPL.format(index=index, episode_plan=plan.model_dump_json(indent=2) if plan else '{}')}"
	messages = as_messages(SYSTEM_ARCHITECT, user_prompt)
	return llm.invoke(messages)
