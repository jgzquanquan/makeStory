from ..llm import ChatLLM, as_messages
from ..prompts import IDEATION_USER_TMPL, SYSTEM_IDEATION
from ..schemas import IdeationResponse
from ..state import PipelineState
from .shared import NodeOutput


def node_multi_ideation(state: PipelineState, llm: ChatLLM) -> NodeOutput:
	user_prompt = IDEATION_USER_TMPL.format(
		topic=state.topic,
		constraints=state.constraints or "无特殊约束",
	)
	messages = as_messages(SYSTEM_IDEATION, user_prompt)
	result = llm.invoke_model(messages, IdeationResponse)
	return {"ideas": result.idea_candidates}
