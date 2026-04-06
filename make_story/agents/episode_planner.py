from ..llm import ChatLLM, as_messages
from ..prompts import EPISODE_PLAN_USER_TMPL, SYSTEM_ARCHITECT
from ..schemas import EpisodePlanResponse
from ..state import PipelineState
from .shared import NodeOutput, story_bible_text


def node_plan_episodes(state: PipelineState, llm: ChatLLM) -> NodeOutput:
	user_prompt = EPISODE_PLAN_USER_TMPL.format(
		num_episodes=state.num_episodes,
		title=state.selected_idea.title if state.selected_idea else "",
		story_bible=story_bible_text(state),
		outline=state.outline or "",
		characters=state.characters or "",
	)
	messages = as_messages(SYSTEM_ARCHITECT, user_prompt)
	result = llm.invoke_model(messages, EpisodePlanResponse)
	if len(result.episode_plans) != state.num_episodes:
		raise ValueError(
			f"分集规划数量不匹配，期望 {state.num_episodes} 集，实际 {len(result.episode_plans)} 集"
		)
	return {"episode_plans": result.episode_plans}
