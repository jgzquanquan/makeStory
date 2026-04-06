from langgraph.graph import StateGraph, END

from .llm import ChatLLM
from .service import (
	run_episode_planning_step,
	run_episode_writing_step,
	run_ideation_step,
	run_outline_step,
	run_review_step,
	run_rewrite_step,
	run_selection_step,
)
from .state import PipelineState


def build_graph(llm: ChatLLM):
	graph = StateGraph(PipelineState)

	graph.add_node("multi_ideation", lambda s: run_ideation_step(s, llm))
	graph.add_node("select_best", lambda s: run_selection_step(s, llm))
	graph.add_node("outline", lambda s: run_outline_step(s, llm))
	graph.add_node("review", lambda s: run_review_step(s, llm))
	graph.add_node("rewrite", lambda s: run_rewrite_step(s, llm))
	graph.add_node("plan_episodes", lambda s: run_episode_planning_step(s, llm))

	def is_approved(state: PipelineState) -> str:
		return "approved" if state.review.approved else "revise"

	graph.set_entry_point("multi_ideation")
	graph.add_edge("multi_ideation", "select_best")
	graph.add_edge("select_best", "outline")
	graph.add_edge("outline", "review")
	graph.add_conditional_edges("review", is_approved, {"approved": "plan_episodes", "revise": "rewrite"})
	graph.add_edge("rewrite", "review")
	graph.add_edge("plan_episodes", "episodes")

	def episodes_node(state: PipelineState) -> dict[str, list[str]]:
		episodes = []
		for i in range(1, state.num_episodes + 1):
			episodes.append(run_episode_writing_step(state, llm, i))
		return {"episodes": episodes}

	graph.add_node("episodes", episodes_node)
	graph.add_edge("episodes", END)

	return graph.compile()
