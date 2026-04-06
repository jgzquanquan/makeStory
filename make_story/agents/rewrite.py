from ..llm import ChatLLM, as_messages
from ..prompts import REWRITE_OUTLINE_USER_TMPL, SYSTEM_ARCHITECT
from ..state import PipelineState
from .shared import NodeOutput


def node_rewrite_outline(state: PipelineState, llm: ChatLLM) -> NodeOutput:
	user_prompt = REWRITE_OUTLINE_USER_TMPL.format(
		issues=state.review.issues,
		rewrite_focus="；".join(state.review.rewrite_focus) or "增强冲突与节奏",
	)
	user_prompt += f"\n\n当前大纲:\n{state.outline}\n\n当前人物:\n{state.characters}"
	messages = as_messages(SYSTEM_ARCHITECT, user_prompt)
	response = llm.invoke(messages)

	outline = response
	characters = state.characters
	if "[人物]" in response:
		parts = response.split("[人物]")
		outline = parts[0].replace("[大纲]", "").strip()
		if len(parts) > 1:
			characters = parts[1].strip()

	return {"outline": outline, "characters": characters}
