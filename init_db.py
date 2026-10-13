import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'proctor.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS admin (
    admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    contact TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    session_id TEXT DEFAULT NULL,
    last_activity TIMESTAMP DEFAULT NULL,
    is_hashed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS exam_authority (
    authority_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    contact TEXT DEFAULT NULL,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_profiles (
    id INTEGER PRIMARY KEY,
    profile_image BLOB,
    face_encoding BLOB,
    FOREIGN KEY (id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    skill TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teacher_profiles (
    id INTEGER PRIMARY KEY,
    profile_image BLOB,
    class TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS complaints (
    complaint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT NULL,
    authority_id INTEGER DEFAULT NULL,
    complaint_text TEXT NOT NULL,
    reply_text TEXT,
    status TEXT DEFAULT 'Pending',
    submission_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (authority_id) REFERENCES exam_authority(authority_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_info (
    exam_id INTEGER PRIMARY KEY,
    authority_id INTEGER NOT NULL,
    exam_title TEXT NOT NULL,
    exam_duration INTEGER DEFAULT NULL,
    exam_rules TEXT,
    exam_date TEXT DEFAULT NULL,
    exam_time TEXT DEFAULT NULL,
    exam_link TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (authority_id) REFERENCES exam_authority(authority_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_details (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    authority_id INTEGER NOT NULL,
    exam_title TEXT NOT NULL,
    exam_type TEXT NOT NULL,
    question_text TEXT,
    question_image BLOB,
    marks INTEGER DEFAULT 0,
    options TEXT,
    exam_duration INTEGER DEFAULT NULL,
    exam_rules TEXT,
    exam_date TEXT DEFAULT NULL,
    exam_time TEXT DEFAULT NULL,
    exam_link TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (authority_id) REFERENCES exam_authority(authority_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    authority_id INTEGER NOT NULL,
    exam_title TEXT NOT NULL,
    exam_type TEXT NOT NULL,
    question_text TEXT,
    question_image BLOB,
    marks INTEGER DEFAULT 0,
    options TEXT,
    correct_answer INTEGER DEFAULT NULL,
    FOREIGN KEY (exam_id) REFERENCES exam_info(exam_id) ON DELETE CASCADE,
    FOREIGN KEY (authority_id) REFERENCES exam_authority(authority_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exam_reference_images (
    ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    image1 BLOB NOT NULL,
    image2 BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, exam_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (exam_id) REFERENCES exam_info(exam_id)
);

CREATE TABLE IF NOT EXISTS exam_violations (
    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    fullname TEXT NOT NULL,
    email TEXT NOT NULL,
    violation_type TEXT NOT NULL,
    face_count INTEGER NOT NULL,
    violation_image BLOB,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (exam_id) REFERENCES exam_info(exam_id)
);

CREATE TABLE IF NOT EXISTS student_academic_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    course TEXT NOT NULL,
    year TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_personal_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    fullname TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_answers_summary (
    answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fullname TEXT NOT NULL,
    exam_title TEXT NOT NULL,
    score INTEGER DEFAULT NULL,
    status TEXT DEFAULT NULL,
    UNIQUE (user_id, exam_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (exam_id) REFERENCES exam_info(exam_id)
);

CREATE TABLE IF NOT EXISTS student_result (
    answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fullname TEXT NOT NULL,
    exam_title TEXT NOT NULL,
    score INTEGER DEFAULT NULL,
    status TEXT DEFAULT NULL,
    UNIQUE (user_id, exam_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (exam_id) REFERENCES exam_info(exam_id)
);

CREATE TABLE IF NOT EXISTS student_answers (
    answer_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    answer TEXT NOT NULL,
    PRIMARY KEY (answer_id, question_id),
    FOREIGN KEY (answer_id) REFERENCES student_result(answer_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES exam_questions(question_id)
);

CREATE TABLE IF NOT EXISTS student_answers_details (
    answer_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    answer TEXT NOT NULL,
    PRIMARY KEY (answer_id, question_id),
    FOREIGN KEY (answer_id) REFERENCES student_answers_summary(answer_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES exam_questions(question_id)
);

CREATE TABLE IF NOT EXISTS submit_exam (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    answer TEXT,
    submission_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS verified_faces (
    user_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    face_image TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, exam_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES exam_info(exam_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS violations (
    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    violation_type TEXT NOT NULL,
    num_faces INTEGER DEFAULT NULL,
    image BLOB,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (exam_id) REFERENCES exam_info(exam_id)
);
"""

def init_sqlite_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Database initialized successfully at {DB_PATH}")

if __name__ == '__main__':
    init_sqlite_db()
