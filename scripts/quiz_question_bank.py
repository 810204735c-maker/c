"""Create shuffled question sets and grade them against the local bank.

Examples:
  python scripts/quiz_question_bank.py start --count 5
  python scripts/quiz_question_bank.py start --section 湖北时政 --count 10
  python scripts/quiz_question_bank.py grade SESSION_ID --answers ABCDA
"""

import argparse
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "hubei_question_bank.sqlite"
LABELS = "ABCD"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS quiz_sessions(
        id TEXT PRIMARY KEY, created_at TEXT NOT NULL, section TEXT, graded_at TEXT
    );
    CREATE TABLE IF NOT EXISTS quiz_items(
        session_id TEXT NOT NULL, position INTEGER NOT NULL,
        question_number INTEGER NOT NULL, option_order TEXT NOT NULL,
        user_answer TEXT, PRIMARY KEY(session_id, position),
        FOREIGN KEY(session_id) REFERENCES quiz_sessions(id),
        FOREIGN KEY(question_number) REFERENCES questions(number)
    );
    """)
    return conn


def start(count, section, numbers):
    if count < 1 or count > 500:
        raise ValueError("count must be between 1 and 500")
    with connect() as conn:
        query = "SELECT * FROM questions WHERE 1=1"
        params = []
        if section:
            query += " AND section=?"
            params.append(section)
        if numbers:
            query += " AND number IN (" + ",".join("?" for _ in numbers) + ")"
            params.extend(numbers)
        rows = list(conn.execute(query, params))
        if count > len(rows):
            raise ValueError(f"Only {len(rows)} questions match the filter")
        rng = secrets.SystemRandom()
        selected = rng.sample(rows, count)
        session_id = uuid.uuid4().hex[:12]
        conn.execute("INSERT INTO quiz_sessions(id,created_at,section) VALUES (?,?,?)",
                     (session_id, datetime.now(timezone.utc).isoformat(), section))
        output = []
        for position, row in enumerate(selected, 1):
            order = list(LABELS)
            while order == list(LABELS):
                rng.shuffle(order)
            conn.execute("INSERT INTO quiz_items VALUES (?,?,?,?,NULL)",
                         (session_id, position, row["number"], "".join(order)))
            output.append({
                "position": position, "original_number": row["number"],
                "section": row["section"], "stem": row["stem"],
                "options": {new: row["option_" + old.lower()]
                            for new, old in zip(LABELS, order)},
            })
        conn.commit()
    print(json.dumps({"session_id": session_id, "questions": output}, ensure_ascii=False, indent=2))


def grade(session_id, answers):
    answers = "".join(ch for ch in answers.upper() if ch in LABELS)
    with connect() as conn:
        rows = list(conn.execute("""
            SELECT i.position, i.option_order, q.*
            FROM quiz_items i JOIN questions q ON q.number=i.question_number
            WHERE i.session_id=? ORDER BY i.position
        """, (session_id,)))
        if not rows:
            raise ValueError("Session not found")
        if len(answers) != len(rows):
            raise ValueError(f"Expected {len(rows)} answers, got {len(answers)}")
        output = []
        for row, submitted in zip(rows, answers):
            correct_display = LABELS[row["option_order"].index(row["answer"])]
            conn.execute("UPDATE quiz_items SET user_answer=? WHERE session_id=? AND position=?",
                         (submitted, session_id, row["position"]))
            output.append({"position": row["position"], "original_number": row["number"],
                           "submitted": submitted, "correct": correct_display,
                           "is_correct": submitted == correct_display,
                           "explanation": row["explanation"],
                           "source_page": row["start_page"]})
        conn.execute("UPDATE quiz_sessions SET graded_at=? WHERE id=?",
                     (datetime.now(timezone.utc).isoformat(), session_id))
        conn.commit()
    print(json.dumps({"session_id": session_id,
                      "score": sum(item["is_correct"] for item in output),
                      "total": len(output), "results": output}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Shuffled local quiz from the 500-question PDF")
    sub = parser.add_subparsers(dest="command", required=True)
    start_parser = sub.add_parser("start")
    start_parser.add_argument("--count", type=int, default=5)
    start_parser.add_argument("--section", choices=["湖北时政", "全国时政", "政治理论", "法律常识", "经济管理", "历史文化科技生活常识"])
    start_parser.add_argument("--numbers", help="Comma-separated original question numbers")
    grade_parser = sub.add_parser("grade")
    grade_parser.add_argument("session_id")
    grade_parser.add_argument("--answers", required=True, help="A letter for each question, e.g. ABCDA")
    args = parser.parse_args()
    if args.command == "start":
        numbers = [int(x) for x in args.numbers.split(",")] if args.numbers else None
        start(args.count, args.section, numbers)
    else:
        grade(args.session_id, args.answers)


if __name__ == "__main__":
    main()
