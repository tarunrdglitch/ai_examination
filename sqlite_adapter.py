import sqlite3
import re
import os
from datetime import datetime
import mysql.connector

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'proctor.db')

class Error(mysql.connector.Error):
    """Base exception for MySQL/SQLite adapter errors."""
    def __init__(self, msg=None, errno=None, sqlstate=None):
        super().__init__(msg=msg or "Database error", errno=errno or 1000, sqlstate=sqlstate)

class DatabaseError(Error):
    pass

class IntegrityError(DatabaseError, mysql.connector.IntegrityError):
    """Constraint violation; matches `except mysql.connector.IntegrityError` in app.py."""
    pass

class SafeDateTimeStr(str):
    """A string subclass that supports .strftime() for Jinja2 template compatibility."""
    def strftime(self, fmt='%Y-%m-%d %H:%M:%S'):
        clean = self.strip().replace('T', ' ')
        try:
            if len(clean) == 10:
                dt = datetime.strptime(clean, '%Y-%m-%d')
            elif len(clean) == 16:
                dt = datetime.strptime(clean, '%Y-%m-%d %H:%M')
            elif len(clean) == 19:
                dt = datetime.strptime(clean, '%Y-%m-%d %H:%M:%S')
            else:
                dt = datetime.fromisoformat(clean)
            return dt.strftime(fmt)
        except Exception:
            return str(self)

def convert_val(val):
    if isinstance(val, str) and re.match(r'^\d{4}-\d{2}-\d{2}', val):
        return SafeDateTimeStr(val)
    return val

def translate_query(query):
    # Replace MySQL NOW() with datetime('now', 'localtime')
    query = re.sub(r'\bNOW\(\)', "datetime('now', 'localtime')", query, flags=re.IGNORECASE)
    # MySQL upsert -> SQLite upsert (conflict target may be omitted on the last clause)
    if re.search(r'ON\s+DUPLICATE\s+KEY\s+UPDATE', query, flags=re.IGNORECASE):
        query = re.sub(r'ON\s+DUPLICATE\s+KEY\s+UPDATE', 'ON CONFLICT DO UPDATE SET', query, flags=re.IGNORECASE)
        query = re.sub(r'\bVALUES\(\s*`?(\w+)`?\s*\)', r'excluded.\1', query, flags=re.IGNORECASE)
    # Replace %s with ?
    parts = query.split('%s')
    query = '?'.join(parts)
    return query

class SQLiteCursor:
    def __init__(self, conn, dictionary=False):
        self._conn = conn
        self._dictionary = dictionary
        self._cursor = conn.cursor()
        self.lastrowid = None
        self.rowcount = -1
        self.description = None

    def execute(self, operation, params=None):
        try:
            sql = translate_query(operation)
            if params is None:
                self._cursor.execute(sql)
            else:
                if isinstance(params, (list, tuple)):
                    converted_params = []
                    for p in params:
                        if hasattr(p, 'isoformat'): # datetime
                            converted_params.append(p.strftime('%Y-%m-%d %H:%M:%S'))
                        else:
                            converted_params.append(p)
                    self._cursor.execute(sql, converted_params)
                else:
                    self._cursor.execute(sql, params)
            self.lastrowid = self._cursor.lastrowid
            self.rowcount = self._cursor.rowcount
            self.description = self._cursor.description
            return self
        except sqlite3.IntegrityError as e:
            raise IntegrityError(str(e), errno=1062) from e
        except sqlite3.Error as e:
            raise DatabaseError(str(e)) from e

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        converted = [convert_val(v) for v in row]
        if self._dictionary and self._cursor.description:
            cols = [col[0] for col in self._cursor.description]
            return dict(zip(cols, converted))
        return tuple(converted)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        if self._dictionary and self._cursor.description:
            cols = [col[0] for col in self._cursor.description]
            return [dict(zip(cols, [convert_val(v) for v in r])) for r in rows]
        return [tuple(convert_val(v) for v in r) for r in rows]

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass

class SQLiteConnection:
    def __init__(self, db_path=DB_PATH):
        self._db_path = db_path
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        try:
            self._conn.execute('PRAGMA journal_mode=WAL')
            self._conn.execute('PRAGMA synchronous=NORMAL')
        except sqlite3.Error:
            pass
        self._closed = False

    def cursor(self, dictionary=False, buffered=False):
        return SQLiteCursor(self._conn, dictionary=dictionary)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def is_connected(self):
        return not self._closed

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self._conn.close()
            except Exception:
                pass

_schema_ready = False

def connect(**kwargs):
    global _schema_ready
    if not _schema_ready:
        from init_db import init_sqlite_db
        init_sqlite_db()
        _schema_ready = True
    return SQLiteConnection()
