"""
Exam engine helpers (Phase 1).

* migrate()          - additive, idempotent schema changes (works on SQLite + MySQL)
* exam lifecycle     - active / stopped (data kept) / deleted (everything erased)
* erase_exam()       - cascade erase of every row + files that belong to an exam
* grade_objective()  - automatic scoring of multiple-choice answers
"""
import os
import shutil
import json
import glob

# (table, column, definition) -- every statement is tried independently so
# re-running on an already migrated database is harmless.
MIGRATIONS = [
    ("exam_info", "status", "TEXT DEFAULT 'active'"),          # active | stopped
    ("exam_info", "exam_mode", "TEXT DEFAULT 'objective'"),    # objective | subjective | both | coding
    ("exam_info", "closed_at", "TIMESTAMP NULL"),
    ("exam_info", "record_enabled", "INTEGER DEFAULT 0"),
    ("exam_info", "negative_marking", "REAL DEFAULT 0"),
    ("exam_questions", "model_answer", "TEXT"),
    ("exam_questions", "rubric", "TEXT"),
    ("exam_questions", "testcases", "TEXT"),
    ("exam_questions", "language", "TEXT"),
    ("student_answers", "marks_awarded", "REAL"),
    ("student_answers", "ai_marks", "REAL"),
    ("student_answers", "ai_feedback", "TEXT"),
    ("student_answers", "graded_by", "TEXT"),
]

# Tables that carry an exam_id column and must be wiped when an exam is deleted.
EXAM_ID_TABLES = [
    "exam_questions", "exam_details", "exam_reference_images",
    "exam_violations", "violations", "verified_faces", "submit_exam",
]

RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "violation_screenshots")


def migrate(connect):
    """Apply additive migrations. `connect` is a zero-arg callable returning a DB connection."""
    conn = connect()
    try:
        for table, column, definition in MIGRATIONS:
            cur = conn.cursor()
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                conn.commit()
            except Exception:
                # Column already exists (or table missing) -> ignore
                try:
                    conn.rollback()
                except Exception:
                    pass
            finally:
                cur.close()
    finally:
        conn.close()


def parse_options(raw):
    """Options are stored newline separated; strip legacy bullet characters."""
    if not raw:
        return []
    return [o.replace("\u2022", "").strip() for o in str(raw).split("\n") if o.replace("\u2022", "").strip()]


def exam_is_open(row):
    """True while students may start / continue an exam."""
    return (row.get("status") or "active") != "stopped"


def grade_objective(cursor, exam_id, answer_id, answers):
    """
    Score MCQ answers. `answers` is [{'question_id':..,'answer':..}, ...].
    Writes marks_awarded per answer, returns (objective_score, has_manual_questions).
    """
    cursor.execute("SELECT negative_marking FROM exam_info WHERE exam_id = %s", (exam_id,))
    row = cursor.fetchone()
    negative = float((row[0] if row else 0) or 0)

    cursor.execute(
        "SELECT question_id, exam_type, options, correct_answer, marks FROM exam_questions WHERE exam_id = %s",
        (exam_id,),
    )
    questions = {r[0]: r for r in cursor.fetchall()}

    total = 0.0
    manual = False
    for a in answers:
        try:
            qid = int(a["question_id"])
        except (TypeError, ValueError, KeyError):
            continue
        q = questions.get(qid)
        if not q:
            continue
        _, qtype, options, correct, marks = q
        if qtype != "objective":
            manual = True
            continue
        opts = parse_options(options)
        given = (a.get("answer") or "").strip()
        awarded = 0.0
        if given and correct is not None and 0 <= int(correct) < len(opts):
            if given == opts[int(correct)]:
                awarded = float(marks or 0)
            else:
                awarded = -negative
        cursor.execute(
            "UPDATE student_answers SET marks_awarded = %s, graded_by = 'auto' "
            "WHERE answer_id = %s AND question_id = %s",
            (awarded, answer_id, qid),
        )
        total += awarded
    return max(total, 0.0), manual


def erase_exam(connection, exam_id, authority_id):
    """
    Permanently erase an exam and ALL related data (rows + recordings + screenshots).
    Returns True if the exam existed and belonged to the teacher.
    """
    cur = connection.cursor()
    try:
        cur.execute("SELECT exam_id FROM exam_info WHERE exam_id = %s AND authority_id = %s", (exam_id, authority_id))
        if not cur.fetchone():
            return False

        # answers hang off student_result / student_answers_summary
        for result_table, answer_table in (
            ("student_result", "student_answers"),
            ("student_answers_summary", "student_answers_details"),
        ):
            cur.execute(f"SELECT answer_id FROM {result_table} WHERE exam_id = %s", (exam_id,))
            ids = [r[0] for r in cur.fetchall()]
            for aid in ids:
                cur.execute(f"DELETE FROM {answer_table} WHERE answer_id = %s", (aid,))
            cur.execute(f"DELETE FROM {result_table} WHERE exam_id = %s", (exam_id,))

        for table in EXAM_ID_TABLES:
            try:
                cur.execute(f"DELETE FROM {table} WHERE exam_id = %s", (exam_id,))
            except Exception:
                pass  # table may not exist in every deployment

        cur.execute("DELETE FROM exam_info WHERE exam_id = %s AND authority_id = %s", (exam_id, authority_id))
        connection.commit()
    finally:
        cur.close()

    # files (recordings, evidence)
    for base in (RECORDINGS_DIR, SCREENSHOT_DIR):
        target = os.path.join(base, str(exam_id))
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        # Also clean any loose chunk files like {exam_id}_*
        for loose_file in glob.glob(os.path.join(base, f"{exam_id}_*")):
            try:
                os.remove(loose_file)
            except OSError:
                pass

    # Purge any cloud storage archives for this exam
    try:
        from cloud_storage import cloud_storage
        cloud_storage.delete_exam_data(exam_id)
    except Exception as e:
        print(f"Cloud storage purge error for exam {exam_id}: {e}")

    return True


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)
