# makeStory

`makeStory` 是一个面向短剧创作的多 Agent 剧本生成器。

它不是单次“出一段文本”的玩具，而是一个能看到过程的创作控制台。你可以先选热门题材，再配置模型，先测试 API 是否通，再实时观察创意池、故事 Bible、大纲审稿、分集规划和分集写作一步步推进。

## What It Does

- 多 Agent 生成候选创意，不是一上来就押一个题材
- 自动挑选最优方向，并生成 `story_bible`
- 产出总大纲、人物小传、分集卡和分集剧本
- 审稿不通过时自动回到改写环节
- Web 控制台可以实时看进展，不再盲等
- 支持在生成前测试模型连接是否正常

## Pipeline

1. `Ideation Agents`
并行模拟多个创意角色，生成候选题材池。

2. `Showrunner / Selector`
从候选题材中选出最优方向，并产出 `story_bible`。

3. `Outline Agent`
把故事 bible 扩展成总大纲和人物小传。

4. `Review Agent`
从钩子、节奏、角色驱动、平台适配和合规角度审稿。

5. `Rewrite Agent`
根据审稿意见迭代大纲。

6. `Episode Planner`
先生成每集功能卡，再进入正片写作。

7. `Episode Writer`
按分集卡产出每集剧本。

## Why This Version Is Better

- Agent 已经按模块拆开，后面加 `Platform Adapter`、`Dialogue Doctor` 这种角色不会把代码堆成一团。
- JSON 类输出已经走 Pydantic 校验，真实模型返回脏数据时更容易发现问题。
- Web 页不是纯表单了，能看到每个阶段的实时状态。
- 模型配置支持单独测试连通性，少走一次完整长链路失败。

## Project Structure

`make_story/agents/`
各 Agent 独立模块，按职责拆分为创意、选择、大纲、审稿、改写、分集规划、分集写作。

`make_story/schemas.py`
结构化产物定义，包含创意候选、故事 bible、审稿结果、分集卡等 schema。

`make_story/state.py`
LangGraph 风格的全局状态定义。

`make_story/service.py`
流程调度、进度回调、模型测试、结果序列化。

`make_story/web.py`
本地 Web 服务和任务状态接口。

`make_story/webapp/index.html`
前端控制台页面。

`make_story/run.py`
CLI 入口。

## Quick Start

### 1. Mock 模式先跑通

```bash
./.conda/bin/python -m make_story.run --topic "都市情感悬疑" --constraints "女性向短剧，6集，每集3分钟" --mock
```

### 2. 启动 Web 控制台

```bash
./.conda/bin/python -m make_story.web --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

### 3. 使用真实模型

在 `.env` 里配置：

```bash
OPENAI_API_KEY=your_key
MODEL_NAME=gpt-4o-mini
BASE_URL=
```

如果你接的是兼容 OpenAI 的中转服务，也可以直接在 Web 控制台里填写 `Base URL` 和模型名。

## Web Console

当前页面支持：

- 热门题材预设
- `OPENAI_API_KEY` / `MODEL_NAME` / `BASE_URL` 配置
- 模型连接测试
- 实时阶段进展
- 生成后查看最佳创意、故事 Bible、分集规划和剧本文本

## Roadmap

- 增加 `Platform Adapter Agent`，分别优化抖音、快手、微信小程序短剧节奏
- 增加 `Dialogue Doctor Agent`，单独强化对白 punchline
- 增加 `Consistency Agent`，检查人物动机、线索回收和设定一致性
- 增加导出功能，支持一键导出 `json` / `txt`
- 把文本大纲和剧本也升级成更稳定的结构化中间层
