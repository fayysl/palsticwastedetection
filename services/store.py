"""Scan history storage: Supabase in production, SQLite for local dev.

Supabase is used when SUPABASE_URL and SUPABASE_KEY are set. We talk to its
REST API (PostgREST) directly, so no extra SDK is needed.
"""

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

import requests

COLUMNS = ("id", "client_id", "created_at", "thumbnail", "model", "demo", "total_items",
           "recyclable_items", "co2_saved_kg", "points", "level", "analysis")


def _row(client_id, analysis, thumbnail, model, demo):
    return {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "thumbnail": thumbnail,
        "model": model,
        "demo": demo,
        "total_items": analysis["total_items"],
        "recyclable_items": analysis["recyclable_items"],
        "co2_saved_kg": analysis["co2_saved_kg"],
        "points": analysis["points"],
        "level": analysis["level"]["key"],
        "analysis": analysis,
    }


def summarize(rows):
    """Aggregate stats for the Track dashboard."""
    by_category, by_bin, daily = {}, {}, {}
    for r in rows:
        day = r["created_at"][:10]
        daily[day] = daily.get(day, 0) + r["total_items"]
        for item in r["analysis"].get("items", []):
            by_category[item["category"]] = by_category.get(item["category"], 0) + item["count"]
            b = item["bin"]["label"]
            by_bin[b] = by_bin.get(b, 0) + item["count"]
    points = sum(r["points"] for r in rows)
    return {
        "scans": len(rows),
        "items": sum(r["total_items"] for r in rows),
        "recyclable_items": sum(r["recyclable_items"] for r in rows),
        "co2_saved_kg": round(sum(r["co2_saved_kg"] for r in rows), 2),
        "points": points,
        "eco_level": eco_level(points),
        "by_category": by_category,
        "by_bin": by_bin,
        "daily": dict(sorted(daily.items())[-14:]),
    }


def eco_level(points):
    tiers = [(0, "Seedling 🌱"), (50, "Sprout 🌿"), (150, "Tree 🌳"), (400, "Forest 🌲"), (1000, "Earth Guardian 🌍")]
    name, nxt = tiers[0][1], None
    for i, (need, label) in enumerate(tiers):
        if points >= need:
            name = label
            nxt = tiers[i + 1][0] if i + 1 < len(tiers) else None
    return {"name": name, "next_at": nxt}


class SQLiteStore:
    kind = "sqlite"

    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self.lock = threading.Lock()
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY, client_id TEXT, created_at TEXT, thumbnail TEXT,
                model TEXT, demo INTEGER, total_items INTEGER, recyclable_items INTEGER,
                co2_saved_kg REAL, points INTEGER, level TEXT, analysis TEXT)""")
            c.execute("CREATE INDEX IF NOT EXISTS scans_client ON scans(client_id, created_at)")

    def _conn(self):
        return sqlite3.connect(self.path)

    @staticmethod
    def _decode(r):
        d = dict(zip(COLUMNS, r))
        d["demo"] = bool(d["demo"])
        d["analysis"] = json.loads(d["analysis"])
        return d

    def save(self, client_id, analysis, thumbnail, model, demo=False):
        row = _row(client_id, analysis, thumbnail, model, demo)
        values = [row[c] for c in COLUMNS]
        values[COLUMNS.index("analysis")] = json.dumps(analysis)
        values[COLUMNS.index("demo")] = int(demo)
        with self.lock, self._conn() as c:
            c.execute(f"INSERT INTO scans VALUES ({','.join('?' * len(COLUMNS))})", values)
        return row

    def list(self, client_id=None, limit=50):
        q = f"SELECT {','.join(COLUMNS)} FROM scans"
        args = []
        if client_id:
            q += " WHERE client_id = ?"
            args.append(client_id)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            return [self._decode(r) for r in c.execute(q, args)]

    def get(self, scan_id):
        with self._conn() as c:
            r = c.execute(f"SELECT {','.join(COLUMNS)} FROM scans WHERE id = ?", (scan_id,)).fetchone()
        return self._decode(r) if r else None


class SupabaseStore:
    kind = "supabase"

    def __init__(self, url, key, table="scans"):
        self.base = f"{url.rstrip('/')}/rest/v1/{table}"
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"}

    def _req(self, method, params=None, body=None, prefer=None):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        resp = requests.request(method, self.base, headers=headers, params=params,
                                json=body, timeout=15)
        resp.raise_for_status()
        return resp.json() if resp.content else []

    def save(self, client_id, analysis, thumbnail, model, demo=False):
        row = _row(client_id, analysis, thumbnail, model, demo)
        self._req("POST", body=row, prefer="return=minimal")
        return row

    def list(self, client_id=None, limit=50):
        params = {"select": ",".join(COLUMNS), "order": "created_at.desc", "limit": str(limit)}
        if client_id:
            params["client_id"] = f"eq.{client_id}"
        return self._req("GET", params=params)

    def get(self, scan_id):
        rows = self._req("GET", params={"select": ",".join(COLUMNS), "id": f"eq.{scan_id}"})
        return rows[0] if rows else None


def make_store(instance_path):
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if url and key:
        return SupabaseStore(url, key)
    return SQLiteStore(os.getenv("SQLITE_PATH") or os.path.join(instance_path, "ecoscan.db"))
