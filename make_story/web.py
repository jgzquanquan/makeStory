import argparse
import json
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .service import (
	GenerateRequest,
	initial_progress_stages,
	load_runtime_config,
	persist_story,
	ModelTestResult,
	presets_as_json,
	ProgressEvent,
	run_pipeline,
	save_runtime_config,
	serialize_state,
	test_model_connection,
)
from .db import delete_story, get_story, init_db, list_stories, restore_story


WEB_DIR = Path(__file__).resolve().parent / "webapp"
INDEX_HTML = WEB_DIR / "index.html"
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
JOB_TTL_SECONDS = 60 * 30
MAX_JOBS = 40


def prune_jobs() -> None:
	now = time.time()
	with JOBS_LOCK:
		expired = [
			job_id
			for job_id, job in JOBS.items()
			if now - float(job.get("updated_at", now)) > JOB_TTL_SECONDS
		]
		for job_id in expired:
			JOBS.pop(job_id, None)

		if len(JOBS) <= MAX_JOBS:
			return

		ordered_jobs = sorted(
			JOBS.items(),
			key=lambda item: float(item[1].get("updated_at", 0)),
			reverse=True,
		)
		for job_id, _ in ordered_jobs[MAX_JOBS:]:
			JOBS.pop(job_id, None)


def create_job(request: GenerateRequest) -> str:
	prune_jobs()
	job_id = uuid.uuid4().hex
	now = time.time()
	with JOBS_LOCK:
		JOBS[job_id] = {
			"id": job_id,
			"status": "queued",
			"message": "任务已创建，等待执行",
			"stages": initial_progress_stages(),
			"preview": {},
			"result": None,
			"error": "",
			"request": request.model_dump(),
			"created_at": now,
			"updated_at": now,
		}
	return job_id


def update_job_stage(job_id: str, event: ProgressEvent) -> None:
	with JOBS_LOCK:
		job = JOBS.get(job_id)
		if not job:
			return
		for stage in job["stages"]:
			if stage["key"] == event.key:
				stage["status"] = event.status
				stage["message"] = event.message
		if event.data:
			job["preview"][event.key] = event.data
		job["status"] = "running"
		job["message"] = event.message
		job["updated_at"] = time.time()


def finish_job(job_id: str, result: dict | None = None, error: str = "") -> None:
	with JOBS_LOCK:
		job = JOBS.get(job_id)
		if not job:
			return
		job["result"] = result
		job["error"] = error
		job["status"] = "failed" if error else "completed"
		job["message"] = error or "生成完成"
		job["updated_at"] = time.time()


def run_job(job_id: str, request: GenerateRequest) -> None:
	try:
		state = run_pipeline(request, progress=lambda event: update_job_stage(job_id, event))
		result = serialize_state(state)
		story_id = persist_story(request, state)
		result["story_id"] = story_id
		finish_job(job_id, result=result)
	except Exception as exc:
		finish_job(job_id, error=str(exc))


class StoryWebHandler(BaseHTTPRequestHandler):
	def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
		body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json; charset=utf-8")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def _send_html(self, html: str, status: int = HTTPStatus.OK) -> None:
		body = html.encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "text/html; charset=utf-8")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def _read_json_body(self) -> dict:
		length = int(self.headers.get("Content-Length", "0"))
		raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
		return json.loads(raw or "{}")

	def do_GET(self) -> None:
		parsed = urlparse(self.path)
		if parsed.path == "/":
			config = load_runtime_config()
			html = INDEX_HTML.read_text(encoding="utf-8")
			html = html.replace("__TOPIC_PRESETS__", presets_as_json())
			html = html.replace("__RUNTIME_CONFIG__", json.dumps(config, ensure_ascii=False))
			self._send_html(html)
			return

		if parsed.path == "/api/config":
			self._send_json(load_runtime_config())
			return

		if parsed.path == "/api/stories":
			query = parse_qs(parsed.query)
			page = int(query.get("page", ["1"])[0])
			page_size = int(query.get("page_size", ["6"])[0])
			search = str(query.get("q", [""])[0])
			sort = str(query.get("sort", ["created_desc"])[0])
			self._send_json(
				{
					"ok": True,
					**list_stories(page=page, page_size=page_size, query=search, sort=sort),
				}
			)
			return

		if parsed.path.startswith("/api/stories/"):
			story_id = parsed.path.rsplit("/", 1)[-1]
			if not story_id.isdigit():
				self._send_json({"error": "Invalid story id"}, status=HTTPStatus.BAD_REQUEST)
				return
			story = get_story(int(story_id))
			if story is None:
				self._send_json({"error": "Story not found"}, status=HTTPStatus.NOT_FOUND)
				return
			self._send_json({"ok": True, "story": story})
			return

		if parsed.path.startswith("/api/jobs/"):
			prune_jobs()
			job_id = parsed.path.rsplit("/", 1)[-1]
			with JOBS_LOCK:
				job = JOBS.get(job_id)
			if not job:
				self._send_json({"error": "Job not found"}, status=HTTPStatus.NOT_FOUND)
				return
			self._send_json(job)
			return

		self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

	def do_POST(self) -> None:
		parsed = urlparse(self.path)
		try:
			payload = self._read_json_body()
		except json.JSONDecodeError:
			self._send_json({"error": "请求体不是合法 JSON"}, status=HTTPStatus.BAD_REQUEST)
			return

		if parsed.path == "/api/generate":
			try:
				request = GenerateRequest.model_validate(payload)
			except Exception as exc:
				self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
				return

			job_id = create_job(request)
			thread = threading.Thread(target=run_job, args=(job_id, request), daemon=True)
			thread.start()
			self._send_json({"ok": True, "job_id": job_id})
			return

		if parsed.path == "/api/save-config":
			try:
				save_runtime_config(
					api_key=str(payload.get("api_key", "")),
					model_name=str(payload.get("model_name", "")),
					base_url=str(payload.get("base_url", "")),
				)
			except Exception as exc:
				self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
				return

			self._send_json({"ok": True})
			return

		if parsed.path == "/api/test-model":
			try:
				request = GenerateRequest.model_validate(payload)
				result: ModelTestResult = test_model_connection(request)
			except Exception as exc:
				self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
				return

			self._send_json({"ok": True, "result": result.model_dump()})
			return

		if parsed.path.startswith("/api/stories/") and parsed.path.endswith("/restore"):
			story_id = parsed.path.removesuffix("/restore").rsplit("/", 1)[-1]
			if not story_id.isdigit():
				self._send_json({"error": "Invalid story id"}, status=HTTPStatus.BAD_REQUEST)
				return
			restored = restore_story(int(story_id))
			if not restored:
				self._send_json({"error": "Story not found"}, status=HTTPStatus.NOT_FOUND)
				return
			self._send_json({"ok": True})
			return

		self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

	def do_DELETE(self) -> None:
		parsed = urlparse(self.path)
		if parsed.path.startswith("/api/stories/"):
			story_id = parsed.path.rsplit("/", 1)[-1]
			if not story_id.isdigit():
				self._send_json({"error": "Invalid story id"}, status=HTTPStatus.BAD_REQUEST)
				return
			story = get_story(int(story_id))
			if story is None:
				self._send_json({"error": "Story not found"}, status=HTTPStatus.NOT_FOUND)
				return
			deleted = delete_story(int(story_id))
			if not deleted:
				self._send_json({"error": "Story not found"}, status=HTTPStatus.NOT_FOUND)
				return
			self._send_json({"ok": True, "story": story})
			return

		self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)


def main() -> None:
	init_db()
	parser = argparse.ArgumentParser(description="makeStory Web 控制台")
	parser.add_argument("--host", default="127.0.0.1")
	parser.add_argument("--port", type=int, default=8000)
	args = parser.parse_args()

	server = ThreadingHTTPServer((args.host, args.port), StoryWebHandler)
	print(f"makeStory Web 已启动: http://{args.host}:{args.port}")
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		pass
	finally:
		server.server_close()


if __name__ == "__main__":
	main()
