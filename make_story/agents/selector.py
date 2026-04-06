from ..llm import ChatLLM, as_messages
from ..prompts import SELECT_USER_TMPL, SYSTEM_CRITIC
from ..schemas import SelectionResponse
from ..state import PipelineState
from .shared import NodeOutput


def node_select_best(state: PipelineState, llm: ChatLLM) -> NodeOutput:
	ideas_text = "\n\n".join(
		[
			f"Agent: {idea.agent_name}\n标题: {idea.title}\n一句话梗概: {idea.logline}\n受众: {idea.target_audience}\n卖点: {', '.join(idea.selling_points)}\n风险: {', '.join(idea.risks)}"
			for idea in state.ideas
		]
	)
	user_prompt = SELECT_USER_TMPL.format(ideas=ideas_text)
	messages = as_messages(SYSTEM_CRITIC, user_prompt)
	result = llm.invoke_model(messages, SelectionResponse)

	selected_idea = next((idea for idea in state.ideas if idea.title == result.selected_title), None)
	if selected_idea is None:
		raise ValueError(f"选择器返回了不存在的标题: {result.selected_title}")

	return {
		"selected_idea": selected_idea,
		"selection_reason": result.selection_reason,
		"story_bible": result.story_bible,
	}
