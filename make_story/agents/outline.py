from ..llm import ChatLLM, as_messages
from ..prompts import OUTLINE_USER_TMPL, SYSTEM_ARCHITECT
from ..state import PipelineState
from .shared import NodeOutput, story_bible_text


def node_generate_outline(state: PipelineState, llm: ChatLLM) -> NodeOutput:
	user_prompt = OUTLINE_USER_TMPL.format(
		title=state.selected_idea.title if state.selected_idea else "",
		story_bible=story_bible_text(state),
	)
	messages = as_messages(SYSTEM_ARCHITECT, user_prompt)
	response = llm.invoke(messages)

	outline = response
	characters = ""
	if "[人物]" in response:
		parts = response.split("[人物]")
		outline = parts[0].replace("[大纲]", "").strip()
		if len(parts) > 1:
			characters = parts[1].strip()

	return {"outline": outline, "characters": characters}
