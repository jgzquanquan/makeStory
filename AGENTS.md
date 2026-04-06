# Repository Guidelines

## Project Structure & Module Organization

Core code lives in `make_story/`.

- `make_story/agents/`: individual agent modules such as ideation, selector, outline, review, planning, and episode writing
- `make_story/service.py`: orchestration, progress events, model connection test, and result serialization
- `make_story/web.py`: local HTTP server and API endpoints
- `make_story/webapp/index.html`: frontend control panel
- `make_story/run.py`: CLI entrypoint
- `make_story/schemas.py`, `state.py`, `llm.py`: shared models, pipeline state, and LLM wrapper

There is currently no `tests/` directory. If you add tests, place them under `tests/` and mirror module names, for example `tests/test_service.py`.

## Build, Test, and Development Commands

- `./.conda/bin/pip install -r requirements.txt`: install project dependencies
- `./.conda/bin/python -m make_story.run --topic "都市情感悬疑" --constraints "女性向短剧" --mock`: run the CLI pipeline in mock mode
- `./.conda/bin/python -m make_story.web --host 127.0.0.1 --port 8000`: start the local web console
- `python -m compileall make_story`: quick syntax validation for the Python package

Use the project `.conda` environment when possible. It is the most predictable path in this repo.

## Coding Style & Naming Conventions

Use 4-space indentation in Python. Keep modules small and role-focused.

- functions and variables: `snake_case`
- Pydantic models and classes: `PascalCase`
- agent node functions: `node_<stage_name>`

Prefer explicit schema validation over loose dictionaries. Keep frontend changes inside `make_story/webapp/index.html` unless the UI grows enough to justify splitting files.

## Testing Guidelines

There is no formal test suite yet. Minimum expectation for changes:

- run `python -m compileall make_story`
- run the CLI in `--mock` mode for pipeline changes
- test the web flow locally for UI or API changes

When adding tests, use `pytest` style naming: `test_<feature>.py`.

## Commit & Pull Request Guidelines

Follow the commit style already used in history:

- `feat: ...`
- `docs: ...`

Keep commits scoped to one logical change. PRs should include:

- a short summary of what changed
- setup or config changes, if any
- screenshots for frontend updates
- manual verification steps, for example `--mock` run or web flow tested

## Security & Configuration Tips

Never commit `.env` or real API keys. Store runtime configuration in `.env` locally and use the UI only to test or save local settings. For GitHub pushes on this machine, SSH is already the expected path.
