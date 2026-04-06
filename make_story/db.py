import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import ROOT_DIR


DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "makestory.sqlite3"
SORT_OPTIONS = {
	"created_desc": "ORDER BY datetime(created_at) DESC, id DESC",
	"created_asc": "ORDER BY datetime(created_at) ASC, id ASC",
	"title_asc": "ORDER BY title COLLATE NOCASE ASC, id DESC",
	"title_desc": "ORDER BY title COLLATE NOCASE DESC, id DESC",
}


def get_connection() -> sqlite3.Connection:
	DATA_DIR.mkdir(parents=True, exist_ok=True)
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn


def init_db() -> None:
	with get_connection() as conn:
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS stories (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				title TEXT NOT NULL,
				topic TEXT NOT NULL,
				constraints TEXT NOT NULL DEFAULT '',
				num_episodes INTEGER NOT NULL DEFAULT 0,
				max_iterations INTEGER NOT NULL DEFAULT 2,
				deleted_at TEXT DEFAULT NULL,
				result_json TEXT NOT NULL,
				created_at TEXT NOT NULL
			)
			"""
		)
		columns = {
			row["name"]
			for row in conn.execute("PRAGMA table_info(stories)").fetchall()
		}
		if "max_iterations" not in columns:
			conn.execute(
				"ALTER TABLE stories ADD COLUMN max_iterations INTEGER NOT NULL DEFAULT 2"
			)
		if "deleted_at" not in columns:
			conn.execute(
				"ALTER TABLE stories ADD COLUMN deleted_at TEXT DEFAULT NULL"
			)
		conn.execute(
			"CREATE INDEX IF NOT EXISTS idx_stories_created_at ON stories(created_at DESC)"
		)
		conn.execute(
			"CREATE INDEX IF NOT EXISTS idx_stories_title ON stories(title)"
		)


def save_story(
	title: str,
	topic: str,
	constraints: str,
	num_episodes: int,
	max_iterations: int,
	result: dict[str, Any],
) -> int:
	init_db()
	created_at = datetime.now(timezone.utc).isoformat()
	with get_connection() as conn:
		cursor = conn.execute(
			"""
			INSERT INTO stories (
				title,
				topic,
				constraints,
				num_episodes,
				max_iterations,
				result_json,
				created_at
			)
			VALUES (?, ?, ?, ?, ?, ?, ?)
			""",
			(
				title,
				topic,
				constraints,
				num_episodes,
				max_iterations,
				json.dumps(result, ensure_ascii=False),
				created_at,
			),
		)
		return int(cursor.lastrowid)


def list_stories(
	page: int = 1,
	page_size: int = 10,
	query: str = "",
	sort: str = "created_desc",
) -> dict[str, Any]:
	init_db()
	page = max(1, page)
	page_size = max(1, min(page_size, 50))
	offset = (page - 1) * page_size
	query = query.strip()
	sort = sort if sort in SORT_OPTIONS else "created_desc"
	where_parts = ["deleted_at IS NULL"]
	params: list[Any] = []
	if query:
		where_parts.append("title LIKE ?")
		params.append(f"%{query}%")
	where_clause = "WHERE " + " AND ".join(where_parts)
	order_clause = SORT_OPTIONS[sort]

	with get_connection() as conn:
		total = int(
			conn.execute(
				f"SELECT COUNT(*) FROM stories {where_clause}",
				params,
			).fetchone()[0]
		)
		rows = conn.execute(
			"""
			SELECT id, title, topic, constraints, num_episodes, max_iterations, created_at
			FROM stories
			"""
			+ where_clause
			+ "\n"
			+ order_clause
			+ """
			LIMIT ? OFFSET ?
			""",
			[*params, page_size, offset],
		).fetchall()

	items = [
		{
			"id": int(row["id"]),
			"title": row["title"],
			"topic": row["topic"],
			"constraints": row["constraints"],
			"num_episodes": int(row["num_episodes"]),
			"max_iterations": int(row["max_iterations"]),
			"created_at": row["created_at"],
		}
		for row in rows
	]
	return {
		"items": items,
		"page": page,
		"page_size": page_size,
		"query": query,
		"sort": sort,
		"total": total,
		"total_pages": max(1, (total + page_size - 1) // page_size),
	}


def get_story(story_id: int) -> dict[str, Any] | None:
	init_db()
	with get_connection() as conn:
		row = conn.execute(
			"""
			SELECT id, title, topic, constraints, num_episodes, max_iterations, result_json, created_at
			FROM stories
			WHERE id = ? AND deleted_at IS NULL
			""",
			(story_id,),
		).fetchone()

	if row is None:
		return None

	result = json.loads(row["result_json"])
	return {
		"id": int(row["id"]),
		"title": row["title"],
		"topic": row["topic"],
		"constraints": row["constraints"],
		"num_episodes": int(row["num_episodes"]),
		"max_iterations": int(row["max_iterations"]),
		"created_at": row["created_at"],
		"result": result,
	}


def delete_story(story_id: int) -> bool:
	init_db()
	deleted_at = datetime.now(timezone.utc).isoformat()
	with get_connection() as conn:
		cursor = conn.execute(
			"UPDATE stories SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
			(deleted_at, story_id),
		)
		return cursor.rowcount > 0


def restore_story(story_id: int) -> bool:
	init_db()
	with get_connection() as conn:
		cursor = conn.execute(
			"UPDATE stories SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
			(story_id,),
		)
		return cursor.rowcount > 0
