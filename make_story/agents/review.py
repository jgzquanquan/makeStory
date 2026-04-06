from ..llm import ChatLLM, as_messages
from ..prompts import REVIEW_USER_TMPL, SYSTEM_CRITIC
from ..schemas import OutlineReview
from ..state import PipelineState
from .shared import NodeOutput, story_bible_text


def node_review_outline(state: PipelineState, llm: ChatLLM) -> NodeOutput:
	context = (
		f"标题:\n{state.selected_idea.title if state.selected_idea else ''}\n\n"
		f"故事 bible:\n{story_bible_text(state)}\n\n"
		f"大纲:\n{state.outline}\n\n人物设定:\n{state.characters}"
	)
	user_prompt = f"{context}\n\n{REVIEW_USER_TMPL}"
	messages = as_messages(SYSTEM_CRITIC, user_prompt)
	review = llm.invoke_model(messages, OutlineReview)
	return {"review": review, "iteration": state.iteration + 1}
