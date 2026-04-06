from typing import Dict, Any
from langgraph.graph import StateGraph, END
from .state import PipelineState
from .llm import ChatLLM
from .agents import (
	node_multi_ideation,
	node_select_best,
	node_generate_outline,
	node_generate_characters,
	node_review_outline,
	node_rewrite_outline,
	node_plan_episodes,
	node_write_episode,
)


def build_graph(llm: ChatLLM):
	graph = StateGraph(PipelineState)

	# 包装为无参节点签名，符合LangGraph调用
	graph.add_node("multi_ideation", lambda s: node_multi_ideation(s, llm))
	graph.add_node("select_best", lambda s: node_select_best(s, llm))
	graph.add_node("gen_outline", lambda s: node_generate_outline(s, llm))
	graph.add_node("gen_chars", lambda s: node_generate_characters(s, llm))
	graph.add_node("review", lambda s: node_review_outline(s, llm))
	graph.add_node("rewrite", lambda s: node_rewrite_outline(s, llm))
	graph.add_node("plan_episodes", lambda s: node_plan_episodes(s, llm))

	def is_approved(state: PipelineState) -> str:
		return "approved" if state.review.approved else "revise"

	graph.set_entry_point("multi_ideation")
	graph.add_edge("multi_ideation", "select_best")
	graph.add_edge("select_best", "gen_outline")
	graph.add_edge("gen_outline", "gen_chars")
	graph.add_edge("gen_chars", "review")
	graph.add_conditional_edges("review", is_approved, {"approved": "plan_episodes", "revise": "rewrite"})
	graph.add_edge("rewrite", "review")
	graph.add_edge("plan_episodes", "episodes")

	def episodes_node(state: PipelineState) -> Dict[str, Any]:
		episodes = []
		for i in range(1, state.num_episodes + 1):
			episodes.append(node_write_episode(state, llm, i))
		return {"episodes": episodes}

	graph.add_node("episodes", episodes_node)
	graph.add_edge("episodes", END)

	return graph.compile()
