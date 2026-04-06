import json
import re
from typing import Any, Dict, List, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from .config import get_base_url, get_model_name, get_openai_api_key


T = TypeVar("T", bound=BaseModel)


class ChatLLM:
	def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None):
		self.model = model or get_model_name()
		api_key = api_key if api_key is not None else get_openai_api_key()
		base_url = base_url if base_url is not None else get_base_url()
		self.client = OpenAI(api_key=api_key, base_url=base_url) if api_key else None

	def invoke(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
		if not self.client:
			raise RuntimeError("OpenAI 客户端未初始化，请配置 OPENAI_API_KEY")
		resp = self.client.chat.completions.create(
			model=self.model,
			messages=messages,  # type: ignore
			temperature=temperature,
		)
		return resp.choices[0].message.content or ""

	def invoke_json(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
		content = self.invoke(messages, temperature=temperature)
		return extract_json_object(content)

	def invoke_model(self, messages: List[Dict[str, str]], schema: type[T], temperature: float = 0.7) -> T:
		payload = self.invoke_json(messages, temperature=temperature)
		return schema.model_validate(payload)


def as_messages(system: str, user: str) -> List[Dict[str, str]]:
	return [
		{"role": "system", "content": system},
		{"role": "user", "content": user},
	]


def extract_json_object(text: str) -> Dict[str, Any]:
	cleaned = text.strip()
	if cleaned.startswith("```"):
		lines = cleaned.splitlines()
		if len(lines) >= 3:
			cleaned = "\n".join(lines[1:-1]).strip()

	try:
		parsed = json.loads(cleaned)
		if isinstance(parsed, dict):
			return parsed
	except json.JSONDecodeError:
		pass

	match = re.search(r"\{.*\}", cleaned, re.DOTALL)
	if not match:
		raise ValueError("LLM 未返回可解析的 JSON 对象")

	parsed = json.loads(match.group(0))
	if not isinstance(parsed, dict):
		raise ValueError("LLM 返回的 JSON 不是对象")
	return parsed


class MockLLM:
	"""无需API Key的占位LLM，用于本地无密钥试跑。

	会基于提示大致返回可解析且能贯穿流程的占位文本。
	"""

	def invoke(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
		joined = "\n".join(m.get("content", "") for m in messages)
		lowered = joined.lower()
		if "idea_candidates" in lowered:
			return json.dumps(
				{
					"idea_candidates": [
						{
							"agent_name": "市场热点 Agent",
							"title": "豪门替身她不装了",
							"logline": "假替身在豪门局中反向操盘，三集一个身份反转。",
							"target_audience": "女性向短剧用户",
							"selling_points": ["高钩子", "身份反转", "强情绪"],
							"risks": ["设定容易同质化"],
						},
						{
							"agent_name": "情绪关系 Agent",
							"title": "离婚冷静期第七天",
							"logline": "即将离婚的夫妻被迫同居破案，旧伤与真相同步翻出。",
							"target_audience": "都市情感用户",
							"selling_points": ["婚恋冲突", "悬疑副线", "人物弧光"],
							"risks": ["节奏需要更狠"],
						},
						{
							"agent_name": "爽点结构 Agent",
							"title": "我在古代做黑红顶流",
							"logline": "现代经纪人穿进古代戏班，把过气花旦捧成第一顶流。",
							"target_audience": "泛娱乐女性用户",
							"selling_points": ["跨时空", "事业爽感", "轻喜剧"],
							"risks": ["世界观要收束"],
						},
					]
				},
				ensure_ascii=False,
			)
		if "selected_title" in lowered and "story_bible" in lowered:
			return json.dumps(
				{
					"selected_title": "离婚冷静期第七天",
					"selection_reason": "情感与悬疑结合，适合做强钩子短剧，角色关系也更利于多集展开。",
					"story_bible": {
						"world": "现代都市，高压律所与老城区命案旧址双线交织。",
						"core_conflict": "夫妻两人因一桩旧案被迫重新合作，在互相试探中揭开婚姻破裂真相。",
						"theme": "亲密关系里最难的是重新相信。",
						"tone": "情绪拉扯强、悬疑推进快、每集结尾有反转。",
						"main_characters": [
							"沈念：女律师，理性克制，想摆脱过去。",
							"周叙：刑辩律师，嘴硬心软，仍在调查当年事故。",
							"林澈：记者，掌握关键录像，也是两人旧友。",
						],
						"episode_arcs": [
							"第1集：离婚前夜收到匿名证据，二人被迫同查。",
							"第2集：旧友出现，发现婚变与旧案可能有关。",
							"第3集：核心录像曝光一半，双方互相怀疑。",
							"第4集：真凶引导舆论，事业与关系双重坍塌。",
							"第5集：主角联手反击，揭开事故背后利益链。",
							"第6集：案件反转，婚姻关系得到新的答案。",
						],
					},
				},
				ensure_ascii=False,
			)
		if "[大纲]" in joined and "[人物]" in joined and "故事 bible" in joined:
			return (
				"[大纲]\n"
				"1. 沈念与周叙在离婚签字前夜收到匿名证据，被迫重返三年前旧案现场。\n"
				"2. 两人在追查中发现婚姻破裂并非单纯情感问题，而是有人刻意利用旧案制造裂痕。\n"
				"3. 随着记者林澈带来残缺录像，二人关系持续恶化，却也逐渐拼出真相轮廓。\n"
				"4. 幕后势力引爆舆论，让沈念事业崩塌、周叙被迫站队，主角陷入最低谷。\n"
				"5. 最终两人决定联手反击，在法庭与情感抉择中同时完成案件收束和关系重建。\n\n"
				"[人物]\n"
				"- 沈念：女律师，理性克制，害怕再次信错人；目标是摆脱过去并守住职业尊严。\n"
				"- 周叙：刑辩律师，表面冷硬，实际始终在查旧案；目标是还原事故真相。\n"
				"- 林澈：记者，掌握关键录像，在友情与职业立场之间摇摆。\n"
			)
		if '"approved"' in lowered and '"issues"' in lowered:
			return '{"approved": true, "issues": "", "strengths": ["钩子明确", "人物关系可持续"], "rewrite_focus": []}'
		if "episode_plans" in lowered:
			num_episodes = 6
			match = re.search(r"为\s*(\d+)\s*集短剧生成分集卡", joined)
			if match:
				num_episodes = int(match.group(1))
			base_plans = [
				{"episode_number": 1, "title": "匿名证据", "goal": "强开场并建立合作关系", "hook": "离婚协议旁边出现命案照片", "beats": ["签字前夜", "匿名短信", "旧案重现", "被迫联手"]},
				{"episode_number": 2, "title": "旧友回场", "goal": "扩大谜团并加压关系", "hook": "关键记者带来被删改的视频", "beats": ["找记者", "发现剪辑痕迹", "互相猜疑", "新线索出现"]},
				{"episode_number": 3, "title": "半段录像", "goal": "制造重大误会", "hook": "录像里出现周叙不该出现的身影", "beats": ["查看录像", "指控升级", "记者失联", "反咬一口"]},
				{"episode_number": 4, "title": "公开处刑", "goal": "把主角推入低谷", "hook": "女主被全网指为伪造证据", "beats": ["舆论爆发", "律所停职", "男主追查", "发现幕后推手"]},
				{"episode_number": 5, "title": "反击夜", "goal": "主角重新结盟", "hook": "真凶以为赢定时被反钓鱼", "beats": ["坦白旧伤", "布局引蛇出洞", "拿到原始硬盘", "真相逼近"]},
				{"episode_number": 6, "title": "第七天", "goal": "收束案件与关系", "hook": "法庭上出现决定婚姻走向的新证词", "beats": ["最终对峙", "事故真相", "情感选择", "留下余味"]},
			]
			return json.dumps(
				{
					"episode_plans": base_plans[:num_episodes]
				},
				ensure_ascii=False,
			)
		if "第" in joined and "集" in joined and "剧本" in joined:
			episode_label = "本集"
			title = "未命名分集"
			hook = "新的秘密浮出水面"
			plan_match = re.search(r'"title"\s*:\s*"([^"]+)"', joined)
			hook_match = re.search(r'"hook"\s*:\s*"([^"]+)"', joined)
			index_match = re.search(r"编写第\s*(\d+)\s*集", joined)
			if plan_match:
				title = plan_match.group(1)
			if hook_match:
				hook = hook_match.group(1)
			if index_match:
				episode_label = f"第{index_match.group(1)}集"
			return (
				f"【{episode_label}·{title}】\n"
				f"【场景一】情绪对峙现场。\n"
				f"沈念：这一次，我不想再被人牵着走。\n"
				f"周叙：可对方已经把钩子甩到我们面前了。\n\n"
				f"【场景二】线索出现。\n"
				f"屏幕上跳出新的证据提示。\n"
				f"沈念：{hook}\n"
				f"周叙：这不是巧合，是有人在逼我们往前走。\n\n"
				f"【场景三】反转收尾。\n"
				f"两人刚准备追查，真正的幕后人先一步抹掉了关键痕迹。"
			)
		# 默认占位
		return "MOCK占位回复"

	def invoke_json(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
		content = self.invoke(messages, temperature=temperature)
		return extract_json_object(content)

	def invoke_model(self, messages: List[Dict[str, str]], schema: type[T], temperature: float = 0.7) -> T:
		payload = self.invoke_json(messages, temperature=temperature)
		return schema.model_validate(payload)
