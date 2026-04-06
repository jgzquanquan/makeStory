import argparse
import json
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .service import (
	GenerateRequest,
	load_runtime_config,
	ModelTestResult,
	presets_as_json,
	ProgressEvent,
	run_pipeline,
	save_runtime_config,
	serialize_state,
	test_model_connection,
)


WEB_DIR = Path(__file__).resolve().parent / "webapp"
INDEX_HTML = WEB_DIR / "index.html"
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def create_job(request: GenerateRequest) -> str:
	job_id = uuid.uuid4().hex
	initial_stages = [
		{"key": "ideation", "label": "创意池", "status": "pending", "message": "等待开始"},
		{"key": "selection", "label": "选题与 Bible", "status": "pending", "message": "等待开始"},
		{"key": "outline", "label": "大纲设计", "status": "pending", "message": "等待开始"},
		{"key": "review", "label": "审稿迭代", "status": "pending", "message": "等待开始"},
		{"key": "planning", "label": "分集规划", "status": "pending", "message": "等待开始"},
		{"key": "writing", "label": "分集写作", "status": "pending", "message": "等待开始"},
	]
	with JOBS_LOCK:
		JOBS[job_id] = {
			"id": job_id,
			"status": "queued",
			"message": "任务已创建，等待执行",
			"stages": initial_stages,
			"result": None,
			"error": "",
			"request": request.model_dump(),
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
		job["status"] = "running"
		job["message"] = event.message


def finish_job(job_id: str, result: dict | None = None, error: str = "") -> None:
	with JOBS_LOCK:
		job = JOBS.get(job_id)
		if not job:
			return
		job["result"] = result
		job["error"] = error
		job["status"] = "failed" if error else "completed"
		job["message"] = error or "生成完成"


def run_job(job_id: str, request: GenerateRequest) -> None:
	try:
		state = run_pipeline(request, progress=lambda event: update_job_stage(job_id, event))
		finish_job(job_id, result=serialize_state(state))
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

		if parsed.path.startswith("/api/jobs/"):
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

		self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)


def main() -> None:
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
