from ..llm import ChatLLM
from ..state import PipelineState
from .shared import NodeOutput


def node_generate_characters(state: PipelineState, llm: ChatLLM) -> NodeOutput:
	del llm
	if state.characters:
		return {"characters": state.characters}

	characters = "\n".join(f"- {item}" for item in state.story_bible.main_characters)
	return {"characters": characters}
