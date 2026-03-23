#!/usr/bin/env python3
"""
aichatlog.py — Claude Code → Obsidian sync engine (via Fast Note Sync)

Part of the aichatlog plugin. Zero external dependencies.
Only syncs conversation files — no Obsidian-specific processing.

Subcommands:
  setup   Interactive FNS configuration wizard
  hook    Called by CC Stop hook (stdin = hook JSON)
  run     Manual one-shot sync of latest conversation
  test    Test FNS API connectivity
  status  Show current configuration and sync state
  log     Show recent sync log entries
  export  Bulk export all unsynchronized conversations
  ingest  Manually ingest all JSONL files into the database
  web     Launch the session management dashboard
"""

import base64, hashlib, json, os, re, sqlite3, sys
import urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────
HOME         = Path.home()
CONFIG_DIR   = HOME / ".config" / "aichatlog"
CONFIG_FILE  = CONFIG_DIR / "config.json"
DB_FILE      = CONFIG_DIR / "aichatlog.db"
LOG_FILE     = CONFIG_DIR / "sync.log"
CC_LOGS      = HOME / ".claude" / "conversation-logs"

# ── i18n ─────────────────────────────────────────────────────
STRINGS = {
    "en": {
        "setup_title":       "AIChatLog — Setup Wizard",
        "detected_json":     "Detected FNS configuration JSON",
        "tip_paste":         "Tip: paste FNS JSON config for quick setup, or press Enter for manual config",
        "tip_paste_hint":    "(from FNS management panel → repo → copy config)",
        "prompt_paste":      "Paste FNS JSON (or Enter to skip)",
        "json_loaded":       "FNS config loaded",
        "fns_api_config":    "FNS API Configuration",
        "fns_api_hint":      "(Get these from your FNS management panel → repository → viewConfig)",
        "prompt_url":        "FNS server URL",
        "prompt_token":      "API Token",
        "prompt_vault":       "Vault",
        "prompt_device":     "Device name",
        "prompt_sync_dir":   "Sync directory in vault",
        "prompt_lang":       "Language / 语言",
        "config_saved":      "Config saved to",
        "next_steps":        "Next: restart Claude Code to activate the Stop hook,\n  then run /aichatlog:test to verify the FNS connection.",
        "not_configured":    "Not configured. Run /aichatlog:setup",
        "synced":            "Synced",
        "files":             "file(s)",
        "nothing_new":       "Nothing new",
        "upload_ok":         "Upload: OK",
        "upload_failed":     "Upload: Failed",
        "check_config":      "Check config",
        "or_reconfigure":    "Or try /aichatlog:setup to reconfigure",
        "processed":         "Processed",
        "conversations":     "conversation(s)",
        "recent_activity":   "Recent activity:",
        "no_log":            "No log yet.",
        "select_lang":       "Select language",
        "export_scanning":   "Scanning conversations...",
        "export_found":      "Found",
        "export_new":        "new",
        "export_skipped":    "already synced",
        "export_progress":   "Exporting",
        "export_done":       "Export complete",
        "export_failed_n":   "failed",
        "export_no_new":     "All conversations already synced.",
        "force_clearing":    "Force mode: clearing mtime cache...",
        "force_resync":      "Force mode: re-parsing all and re-syncing...",
        "database":          "Database",
        "total_conv":        "Total conversations",
        "ingesting":         "Ingesting conversations...",
        "conv_in_db":        "conversations in database.",
        "dashboard_url":     "Dashboard",
        "press_ctrl_c":      "Press Ctrl+C to stop.",
        "adapter_changed":   "Adapter changed",
        "marked_resync":     "conversations marked for re-sync.",
    },
    "zh-CN": {
        "setup_title":       "AIChatLog — 配置向导",
        "detected_json":     "检测到 FNS 配置 JSON",
        "tip_paste":         "提示：粘贴 FNS JSON 配置快速设置，或按 Enter 手动配置",
        "tip_paste_hint":    "（从 FNS 管理面板 → 笔记库 → 复制配置）",
        "prompt_paste":      "粘贴 FNS JSON（或按 Enter 跳过）",
        "json_loaded":       "FNS 配置已加载",
        "fns_api_config":    "FNS API 配置",
        "fns_api_hint":      "（从 FNS 管理面板 → 笔记库 → 查看配置获取）",
        "prompt_url":        "FNS 服务器地址",
        "prompt_token":      "API Token",
        "prompt_vault":       "笔记库名称",
        "prompt_device":     "设备名称",
        "prompt_sync_dir":   "笔记库中的同步目录",
        "prompt_lang":       "Language / 语言",
        "config_saved":      "配置已保存到",
        "next_steps":        "下一步：重启 Claude Code 以激活 Stop hook，\n  然后运行 /aichatlog:test 验证 FNS 连接。",
        "not_configured":    "未配置，请运行 /aichatlog:setup",
        "synced":            "已同步",
        "files":             "个文件",
        "nothing_new":       "没有新内容",
        "upload_ok":         "上传：成功",
        "upload_failed":     "上传：失败",
        "check_config":      "检查配置",
        "or_reconfigure":    "或尝试 /aichatlog:setup 重新配置",
        "processed":         "已处理",
        "conversations":     "个对话",
        "recent_activity":   "最近活动：",
        "no_log":            "暂无日志。",
        "select_lang":       "选择语言",
        "export_scanning":   "正在扫描对话...",
        "export_found":      "发现",
        "export_new":        "条新对话",
        "export_skipped":    "条已同步",
        "export_progress":   "导出中",
        "export_done":       "导出完成",
        "export_failed_n":   "条失败",
        "export_no_new":     "所有对话均已同步。",
        "force_clearing":    "强制模式：正在清除缓存...",
        "force_resync":      "强制模式：重新解析并重新同步...",
        "database":          "数据库",
        "total_conv":        "对话总数",
        "ingesting":         "正在导入对话...",
        "conv_in_db":        "条对话已入库。",
        "dashboard_url":     "管理面板",
        "press_ctrl_c":      "按 Ctrl+C 停止。",
        "adapter_changed":   "适配器已切换",
        "marked_resync":     "条对话已标记为待重新同步。",
    },
    "zh-TW": {
        "setup_title":       "AIChatLog — 設定精靈",
        "detected_json":     "偵測到 FNS 設定 JSON",
        "tip_paste":         "提示：貼上 FNS JSON 設定快速完成配置，或按 Enter 手動設定",
        "tip_paste_hint":    "（從 FNS 管理面板 → 筆記庫 → 複製設定）",
        "prompt_paste":      "貼上 FNS JSON（或按 Enter 跳過）",
        "json_loaded":       "FNS 設定已載入",
        "fns_api_config":    "FNS API 設定",
        "fns_api_hint":      "（從 FNS 管理面板 → 筆記庫 → 檢視設定取得）",
        "prompt_url":        "FNS 伺服器位址",
        "prompt_token":      "API Token",
        "prompt_vault":       "筆記庫名稱",
        "prompt_device":     "裝置名稱",
        "prompt_sync_dir":   "筆記庫中的同步目錄",
        "prompt_lang":       "Language / 語言",
        "config_saved":      "設定已儲存到",
        "next_steps":        "下一步：重新啟動 Claude Code 以啟用 Stop hook，\n  然後執行 /aichatlog:test 驗證 FNS 連線。",
        "not_configured":    "未設定，請執行 /aichatlog:setup",
        "synced":            "已同步",
        "files":             "個檔案",
        "nothing_new":       "沒有新內容",
        "upload_ok":         "上傳：成功",
        "upload_failed":     "上傳：失敗",
        "check_config":      "檢查設定",
        "or_reconfigure":    "或嘗試 /aichatlog:setup 重新設定",
        "processed":         "已處理",
        "conversations":     "個對話",
        "recent_activity":   "最近活動：",
        "no_log":            "暫無日誌。",
        "select_lang":       "選擇語言",
        "export_scanning":   "正在掃描對話...",
        "export_found":      "發現",
        "export_new":        "筆新對話",
        "export_skipped":    "筆已同步",
        "export_progress":   "匯出中",
        "export_done":       "匯出完成",
        "export_failed_n":   "筆失敗",
        "export_no_new":     "所有對話均已同步。",
        "force_clearing":    "強制模式：正在清除快取...",
        "force_resync":      "強制模式：重新解析並重新同步...",
        "database":          "資料庫",
        "total_conv":        "對話總數",
        "ingesting":         "正在匯入對話...",
        "conv_in_db":        "筆對話已入庫。",
        "dashboard_url":     "管理面板",
        "press_ctrl_c":      "按 Ctrl+C 停止。",
        "adapter_changed":   "適配器已切換",
        "marked_resync":     "筆對話已標記為待重新同步。",
    },
}

LANG_NAMES = {"en": "English", "zh-CN": "简体中文", "zh-TW": "繁體中文"}

def get_lang():
    cfg = cfg_load()
    return (cfg or {}).get("lang", "en")

def t(key):
    lang = get_lang()
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))

# ── Logging ──────────────────────────────────────────────────
def log(msg, echo=False):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    if echo:
        print(f"  {msg}")

# ── Config ───────────────────────────────────────────────────
def cfg_load():
    if not CONFIG_FILE.exists():
        return None
    cfg = json.loads(CONFIG_FILE.read_text())
    # Migration: v0.4 config (fns_api at root) → v0.5 config (output.adapter)
    if "fns_api" in cfg and "output" not in cfg:
        cfg["output"] = {"adapter": "fns", "fns": cfg["fns_api"]}
        cfg_save(cfg)
    return cfg

def cfg_save(c):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(c, indent=2, ensure_ascii=False))

def cfg_is_configured(cfg):
    """Check if an output adapter is properly configured."""
    if not cfg:
        return False
    output = cfg.get("output", {})
    adapter_name = output.get("adapter", "fns")
    adapter_cfg = output.get(adapter_name, {})
    if adapter_name == "fns":
        return bool(adapter_cfg.get("token"))
    elif adapter_name == "local":
        return bool(adapter_cfg.get("path"))
    elif adapter_name == "git":
        return bool(adapter_cfg.get("repo_path"))
    elif adapter_name == "server":
        return bool(adapter_cfg.get("url"))
    # Legacy check
    return bool(cfg.get("fns_api", {}).get("token"))

# ── Database ─────────────────────────────────────────────────
def db_connect():
    """Open (or create) the SQLite database. Returns a connection."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_FILE), timeout=5)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.row_factory = sqlite3.Row
    db_init_schema(db)
    return db

def db_init_schema(db):
    """Create tables if they don't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            session_id    TEXT PRIMARY KEY,
            title         TEXT NOT NULL,
            date          TEXT NOT NULL,
            project       TEXT DEFAULT '',
            project_path  TEXT DEFAULT '',
            message_count INTEGER DEFAULT 0,
            word_count    INTEGER DEFAULT 0,
            status        TEXT DEFAULT 'unsynced'
                          CHECK(status IN ('unsynced','synced','ignored')),
            content_hash  TEXT,
            synced_path   TEXT,
            synced_at     TEXT,
            source_file   TEXT,
            source_mtime  REAL,
            created_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
            updated_at    TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_conv_status ON conversations(status);
        CREATE INDEX IF NOT EXISTS idx_conv_date   ON conversations(date DESC);

        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES conversations(session_id) ON DELETE CASCADE,
            seq        INTEGER NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            time_str   TEXT DEFAULT '',
            is_context INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, seq);

        CREATE TABLE IF NOT EXISTS extractions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL REFERENCES conversations(session_id) ON DELETE CASCADE,
            summary      TEXT,
            result_json  TEXT,
            llm_model    TEXT,
            cost_usd     REAL DEFAULT 0,
            created_at   TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_extractions_session ON extractions(session_id);

        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
        );
        INSERT OR IGNORE INTO schema_version (version) VALUES (1);
    """)
    # Schema v2: add source column
    v = db.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 1
    if v < 2:
        try:
            db.execute("ALTER TABLE conversations ADD COLUMN source TEXT DEFAULT 'claude-code'")
        except Exception:
            pass  # column may already exist
        db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")
        db.commit()
    # FTS5 for dashboard search (title + project)
    try:
        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                session_id UNINDEXED, title, project,
                content='conversations', content_rowid='rowid'
            )
        """)
        db.executescript("""
            CREATE TRIGGER IF NOT EXISTS conv_fts_ai AFTER INSERT ON conversations BEGIN
                INSERT INTO conversations_fts(rowid, session_id, title, project)
                VALUES (new.rowid, new.session_id, new.title, new.project);
            END;
            CREATE TRIGGER IF NOT EXISTS conv_fts_ad AFTER DELETE ON conversations BEGIN
                INSERT INTO conversations_fts(conversations_fts, rowid, session_id, title, project)
                VALUES ('delete', old.rowid, old.session_id, old.title, old.project);
            END;
            CREATE TRIGGER IF NOT EXISTS conv_fts_au AFTER UPDATE ON conversations BEGIN
                INSERT INTO conversations_fts(conversations_fts, rowid, session_id, title, project)
                VALUES ('delete', old.rowid, old.session_id, old.title, old.project);
                INSERT INTO conversations_fts(rowid, session_id, title, project)
                VALUES (new.rowid, new.session_id, new.title, new.project);
            END;
        """)
    except Exception:
        pass  # FTS5 not available on this build; search falls back to LIKE
    db.commit()
    # Schema v3: add synced_hash and synced_message_count for conditional sync
    v = db.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 1
    if v < 3:
        for col in [
            "ALTER TABLE conversations ADD COLUMN synced_hash TEXT",
            "ALTER TABLE conversations ADD COLUMN synced_message_count INTEGER DEFAULT 0",
        ]:
            try:
                db.execute(col)
            except Exception:
                pass
        db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (3)")
        db.commit()

# ── Helpers ──────────────────────────────────────────────────
def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(8192), b""): h.update(c)
    return h.hexdigest()

def md5_str(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def san(name):
    """Sanitize a string for use as a filename. Keeps CJK chars, replaces illegal chars with -."""
    s = re.sub(r'[<>:"/\\|?*]', '-', name)       # illegal filename chars
    s = re.sub(r'[\n\r\t]', ' ', s)                # newlines to space
    s = re.sub(r'\s+', ' ', s).strip()             # collapse whitespace
    s = s.strip('-. ')
    return s[:50] or "untitled"

# ── Output Adapter Interface ──────────────────────────────────
class OutputAdapter:
    """Base class for all output adapters."""
    name = "base"

    def write_note(self, path, content):
        """Write a note. path is relative (e.g. 'aichatlog/My Note.md').
        Returns (ok: bool, message: str)."""
        raise NotImplementedError

    def test_connection(self):
        """Verify adapter is configured and reachable.
        Returns (ok: bool, message: str)."""
        raise NotImplementedError


class FNSAdapter(OutputAdapter):
    """Output adapter for Fast Note Sync REST API."""
    name = "fns"

    def __init__(self, adapter_cfg):
        self.url = adapter_cfg.get("url", "").rstrip("/")
        self.token = adapter_cfg.get("token", "")
        self.vault = adapter_cfg.get("vault", "")

    def _call(self, endpoint, data):
        url = self.url + endpoint
        body = json.dumps(data).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "token": self.token,
        }
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode())
                if isinstance(resp, dict) and resp.get("status") is False:
                    return False, f"FNS error {resp.get('code')}: {resp.get('message', '')}"
                return True, resp
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}: {e.read().decode()[:300]}"
        except Exception as e:
            return False, str(e)

    def write_note(self, path, content):
        return self._call("/api/note", {"vault": self.vault, "path": path, "content": content})

    def test_connection(self):
        test = f"AIChatLog connectivity test.\nDate: {datetime.now().isoformat()}\nSafe to delete.\n"
        return self._call("/api/note", {"vault": self.vault, "path": ".aichatlog-test.md", "content": test})


class LocalAdapter(OutputAdapter):
    """Output adapter that writes .md files to a local directory."""
    name = "local"

    def __init__(self, adapter_cfg):
        self.base_path = Path(adapter_cfg.get("path", "")).expanduser()

    def write_note(self, path, content):
        target = self.base_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return True, str(target)

    def test_connection(self):
        if not self.base_path.exists():
            return False, f"Directory does not exist: {self.base_path}"
        test_file = self.base_path / ".aichatlog-test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            return True, f"Writable: {self.base_path}"
        except OSError as e:
            return False, str(e)


class GitAdapter(OutputAdapter):
    """Output adapter that writes .md files and commits to a git repo."""
    name = "git"

    def __init__(self, adapter_cfg):
        import subprocess as _sp
        self._sp = _sp
        self.repo_path = Path(adapter_cfg.get("repo_path", "")).expanduser()
        self.auto_commit = adapter_cfg.get("auto_commit", True)
        self.auto_push = adapter_cfg.get("auto_push", False)

    def write_note(self, path, content):
        target = self.repo_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if self.auto_commit:
            self._sp.run(["git", "add", str(target)], cwd=str(self.repo_path), capture_output=True)
            self._sp.run(["git", "commit", "-m", f"aichatlog: {Path(path).stem}"],
                         cwd=str(self.repo_path), capture_output=True)
        if self.auto_push:
            self._sp.run(["git", "push"], cwd=str(self.repo_path), capture_output=True)
        return True, str(target)

    def test_connection(self):
        try:
            r = self._sp.run(["git", "status", "--porcelain"],
                             cwd=str(self.repo_path), capture_output=True, text=True)
            if r.returncode == 0:
                return True, f"Git repo OK: {self.repo_path}"
            return False, f"Not a git repo: {self.repo_path}"
        except FileNotFoundError:
            return False, "git not found in PATH"


class ServerAdapter(OutputAdapter):
    """Output adapter that POSTs ConversationObject to aichatlog-server."""
    name = "server"

    def __init__(self, adapter_cfg):
        self.url = adapter_cfg.get("url", "").rstrip("/")
        self.token = adapter_cfg.get("token", "")

    def write_note(self, path, content):
        """Fallback: POST markdown content as a minimal v1 ConversationObject."""
        obj = {"version": 1, "source": "claude-code", "device": "unknown",
               "session_id": path, "title": path, "date": "",
               "message_count": 0, "word_count": len(content.split()),
               "content_hash": md5_str(content), "messages": []}
        return self.send_conversation(obj)

    def send_conversation(self, conversation_object):
        """POST ConversationObject to aichatlog-server (v1 compat)."""
        url = f"{self.url}/api/conversations"
        body = json.dumps(conversation_object, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode())
                return True, resp
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}: {e.read().decode()[:300]}"
        except Exception as e:
            return False, str(e)

    def send_sync(self, sync_object):
        """POST v2 sync request to /api/conversations/sync. Returns (ok, resp_dict)."""
        url = f"{self.url}/api/conversations/sync"
        body = json.dumps(sync_object, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode())
                return True, resp
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Old server without sync endpoint; caller should fallback to v1
                return False, {"fallback": True}
            return False, f"HTTP {e.code}: {e.read().decode()[:300]}"
        except Exception as e:
            return False, str(e)

    def test_connection(self):
        # Step 1: health check (always public)
        try:
            req = urllib.request.Request(f"{self.url}/api/health", method="GET")
            with urllib.request.urlopen(req, timeout=10) as r:
                pass
        except Exception as e:
            return False, f"Server unreachable: {e}"

        # Step 2: auth check — hit a protected endpoint to verify token
        try:
            req = urllib.request.Request(f"{self.url}/api/stats", method="GET")
            if self.token:
                req.add_header("Authorization", f"Bearer {self.token}")
            with urllib.request.urlopen(req, timeout=10) as r:
                return True, "Connected & authenticated"
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "Server reachable but token is invalid or missing"
            return False, f"HTTP {e.code}"
        except Exception as e:
            return False, f"Auth check failed: {e}"


ADAPTERS = {"fns": FNSAdapter, "local": LocalAdapter, "git": GitAdapter, "server": ServerAdapter}

def get_adapter(cfg):
    """Instantiate the configured output adapter."""
    output = cfg.get("output", {})
    adapter_name = output.get("adapter", "fns")
    adapter_cls = ADAPTERS.get(adapter_name)
    if not adapter_cls:
        raise ValueError(f"Unknown adapter: {adapter_name}")
    adapter_cfg = output.get(adapter_name, {})
    return adapter_cls(adapter_cfg)


# ── Legacy FNS helpers (kept for backward compat) ────────────
def fns_upload(cfg, path, content):
    """Create or update a note via FNS REST API (POST /api/note). Legacy wrapper."""
    adapter = get_adapter(cfg)
    return adapter.write_note(path, content)

# ── JSONL Parsing ───────────────────────────────────────────
def parse_jsonl(jsonl_path):
    """Parse a conversation JSONL file into structured data.

    Returns dict with keys:
        session_id, date, project, messages, title,
        started_at, ended_at (full ISO8601 local time),
        model (primary AI model), git_branch, entrypoint, cc_version,
        total_input_tokens, total_output_tokens, total_cache_read_tokens,
        total_cache_creation_tokens,
        has_code (bool),
        metadata (dict of source-specific extras)
    Returns None if file is empty or has no real messages.
    """
    messages = []
    session_id = None
    project = None
    first_ts = None
    last_ts = None
    git_branch = None
    entrypoint = None
    cc_version = None
    slug = None
    ai_title = None
    models_seen = []
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_create = 0
    has_code = False

    for line in jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = obj.get("type")
        if msg_type not in ("user", "assistant"):
            continue

        if session_id is None:
            session_id = obj.get("sessionId", "")
        if project is None:
            project = obj.get("cwd", "")
        if git_branch is None:
            git_branch = obj.get("gitBranch")
        if entrypoint is None:
            entrypoint = obj.get("entrypoint")
        if cc_version is None:
            cc_version = obj.get("version")
        if slug is None:
            slug = obj.get("slug")
        if ai_title is None and obj.get("aiTitle"):
            ai_title = obj.get("aiTitle")

        if obj.get("isMeta"):
            continue

        msg = obj.get("message", {})
        content_parts = msg.get("content", "")
        role = msg.get("role", msg_type)

        if isinstance(content_parts, list):
            parts = []
            for p in content_parts:
                if not isinstance(p, dict):
                    continue
                ptype = p.get("type", "")
                if ptype == "text":
                    t = p.get("text", "")
                    if t:
                        parts.append(t)
                elif ptype == "tool_use":
                    name = p.get("name", "unknown")
                    inp = p.get("input", {})
                    lines = [f"**Tool: {name}**"]
                    if isinstance(inp, dict):
                        for k, v in inp.items():
                            sv = str(v)
                            if len(sv) > 300:
                                sv = sv[:300] + "…"
                            lines.append(f"  {k}: {sv}")
                    parts.append("\n".join(lines))
                elif ptype == "tool_result":
                    rc = p.get("content", "")
                    if isinstance(rc, list):
                        rc = "\n".join(
                            sub.get("text", "") for sub in rc
                            if isinstance(sub, dict) and sub.get("type") == "text"
                        )
                    if isinstance(rc, str) and rc.strip():
                        truncated = rc.strip()
                        if len(truncated) > 2000:
                            truncated = truncated[:2000] + "\n…(truncated)"
                        parts.append(f"```\n{truncated}\n```")
                elif ptype == "thinking":
                    t = p.get("thinking", "") or p.get("text", "")
                    if t:
                        parts.append(f"<thinking>\n{t}\n</thinking>")
            text = "\n\n".join(parts)
        elif isinstance(content_parts, str):
            text = content_parts
        else:
            continue

        if not text.strip():
            continue
        stripped_text = text.strip()
        if re.match(r'^<(local-command-|command-name>|command-message>)', stripped_text):
            continue

        is_context = bool(re.match(
            r'^<(ide_selection|ide_opened_file|ide_closed_file|system-reminder|task-notification|available-deferred-tools|gitStatus)',
            stripped_text))
        if is_context:
            # If real text remains after stripping XML, it's not pure context
            cleaned = re.sub(r'<([a-zA-Z][a-zA-Z0-9_:-]*)[\s>][\s\S]*?</\1>', '', stripped_text)
            cleaned = re.sub(r'<[a-zA-Z][a-zA-Z0-9_:-]*(?:\s[^>]*)?\s*/>', '', cleaned)
            cleaned = re.sub(r'</?[a-zA-Z][a-zA-Z0-9_:-]*(?:\s[^>]*)?>', '', cleaned).strip()
            if len(cleaned) > 3:
                is_context = False

        # Parse timestamp — store UTC for server, derive local display time
        ts_raw = obj.get("timestamp", "")
        timestamp = ""
        time_str = ""
        if ts_raw:
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                # Store as UTC ISO8601 for server (preserves precision + timezone)
                timestamp = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
                    f"{dt.microsecond // 1000:03d}Z"
                # Local display time for markdown rendering
                local_dt = dt.astimezone()
                time_str = local_dt.strftime("%H:%M")
                if first_ts is None:
                    first_ts = timestamp
                last_ts = timestamp
            except (ValueError, OSError):
                pass

        # Extract per-message model and token usage (assistant messages)
        msg_model = ""
        msg_input_tokens = 0
        msg_output_tokens = 0
        if msg_type == "assistant":
            msg_model = msg.get("model", "")
            if msg_model and msg_model not in models_seen:
                models_seen.append(msg_model)
            usage = msg.get("usage", {})
            if usage:
                msg_input_tokens = usage.get("input_tokens", 0)
                msg_output_tokens = usage.get("output_tokens", 0)
                total_input += msg_input_tokens
                total_output += msg_output_tokens
                total_cache_read += usage.get("cache_read_input_tokens", 0)
                total_cache_create += usage.get("cache_creation_input_tokens", 0)

        if not has_code and "```" in text:
            has_code = True

        messages.append({
            "role": role, "content": text,
            "time_str": time_str, "timestamp": timestamp,
            "is_context": is_context,
            "model": msg_model,
            "input_tokens": msg_input_tokens,
            "output_tokens": msg_output_tokens,
        })

    if not messages or not session_id:
        return None

    # Title: prefer aiTitle from CC, then extract from first real user message
    title = "untitled"
    if ai_title:
        title = san(ai_title)
    else:
        for m in messages:
            if m["role"] == "user" and not m.get("is_context"):
                raw = m["content"].strip()
                # Strip all XML tag blocks (multi-line aware)
                raw = re.sub(r'<([a-zA-Z][a-zA-Z0-9_:-]*)[\s>][\s\S]*?</\1>', '', raw)
                raw = re.sub(r'<[a-zA-Z][a-zA-Z0-9_:-]*(?:\s[^>]*)?\s*/>', '', raw)
                raw = re.sub(r'</?[a-zA-Z][a-zA-Z0-9_:-]*(?:\s[^>]*)?>', '', raw)
                raw = re.sub(r'[#*`\[\]]', '', raw).strip()
                raw = raw.split("\n")[0].strip()
                if raw and len(raw) > 3:
                    title = san(raw)
                break

    first_date = first_ts[:10] if first_ts else datetime.now().strftime("%Y-%m-%d")

    # Primary model = most used assistant model
    model = models_seen[0] if models_seen else ""

    # Source-specific metadata (extensible dict)
    metadata = {}
    if git_branch:
        metadata["git_branch"] = git_branch
    if entrypoint:
        metadata["entrypoint"] = entrypoint
    if cc_version:
        metadata["cc_version"] = cc_version
    if slug:
        metadata["slug"] = slug
    if total_cache_read or total_cache_create:
        metadata["cache_read_tokens"] = total_cache_read
        metadata["cache_creation_tokens"] = total_cache_create

    return {
        "session_id": session_id,
        "date": first_date,
        "project": project or "",
        "messages": messages,
        "title": title,
        "started_at": first_ts or "",
        "ended_at": last_ts or "",
        "model": model,
        "has_code": has_code,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "metadata": metadata,
    }


def format_conversation(parsed):
    """Generate markdown with per-message timestamps from parsed JSONL data."""
    lines = []
    lines.append(f"# {parsed['title']}")
    lines.append("")
    lines.append(f"> Session: {parsed['session_id']}")
    lines.append(f"> Date: {parsed['date']}")
    if parsed["project"]:
        lines.append(f"> Project: {parsed['project']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in parsed["messages"]:
        if msg.get("is_context"):
            continue
        role_label = "User" if msg["role"] == "user" else "Assistant"
        ts = f" [{msg['time_str']}]" if msg["time_str"] else ""
        lines.append(f"### {role_label}{ts}")
        lines.append("")
        lines.append(msg["content"])
        lines.append("")

    return "\n".join(lines)


def _build_conversation_base(parsed, cfg, source="claude-code"):
    """Build common ConversationObject fields shared by v1 and v2."""
    msgs = parsed["messages"]
    project_path = parsed.get("project", "")
    return {
        "source": source,
        "device": cfg.get("device_name", "unknown"),
        "session_id": parsed["session_id"],
        "title": parsed["title"],
        "date": parsed["date"],
        "started_at": parsed.get("started_at", ""),
        "ended_at": parsed.get("ended_at", ""),
        "project": project_path.split("/")[-1] if project_path else "",
        "project_path": project_path,
        "model": parsed.get("model", ""),
        "message_count": len(msgs),
        "word_count": sum(len(m["content"].split()) for m in msgs),
        "content_hash": md5_str(json.dumps(msgs, ensure_ascii=False)),
        "has_code": parsed.get("has_code", False),
        "total_input_tokens": parsed.get("total_input_tokens", 0),
        "total_output_tokens": parsed.get("total_output_tokens", 0),
        "metadata": parsed.get("metadata", {}),
    }


def to_conversation_object(parsed, cfg, source="claude-code"):
    """Convert parsed JSONL dict to ConversationObject v1 for protocol transport."""
    obj = _build_conversation_base(parsed, cfg, source)
    obj["version"] = 1
    obj["messages"] = [{**m, "seq": i} for i, m in enumerate(parsed["messages"])]
    return obj


def to_conversation_object_v2(parsed, cfg, mode, db_row, source="claude-code"):
    """Build v2 ConversationObject with conditional sync support.

    mode: "full" | "delta" | "check"
    db_row: conversations row dict with synced_hash / synced_message_count
    """
    obj = _build_conversation_base(parsed, cfg, source)
    obj["version"] = 2
    obj["sync_mode"] = mode

    msgs = parsed["messages"]
    if mode == "full":
        obj["messages"] = [{**m, "seq": i} for i, m in enumerate(msgs)]
    elif mode == "delta":
        old_count = (db_row["synced_message_count"] or 0) if db_row else 0
        obj["delta_from_seq"] = old_count
        obj["messages"] = [{**m, "seq": i} for i, m in enumerate(msgs) if i >= old_count]
    # check mode: no messages field
    return obj


def make_title_from_md(md_path):
    """Fallback: extract title from .md file when JSONL is unavailable."""
    content = md_path.read_text(encoding="utf-8", errors="replace")
    in_user = False
    for ln in content.strip().split("\n"):
        stripped = ln.strip()
        if re.match(r'^##\s+USER\s*$', stripped, re.IGNORECASE) or "**User:**" in stripped:
            in_user = True
            continue
        if in_user:
            if stripped and not stripped.startswith(("---", "##", "**")):
                return san(re.sub(r'[#*`\[\]]', '', stripped).strip())
    return "untitled"


# ── Pipeline ─────────────────────────────────────────────────
def find_all_jsonl():
    """Return all conversation .jsonl files sorted by mtime (oldest first)."""
    if not CC_LOGS.exists():
        return []
    files = [f for f in CC_LOGS.glob("conversation_*.jsonl") if not f.is_symlink()]
    return sorted(files, key=lambda f: f.stat().st_mtime)


def find_latest_jsonl():
    """Return the most recently modified conversation .jsonl file."""
    if not CC_LOGS.exists():
        return None
    files = [f for f in CC_LOGS.glob("conversation_*.jsonl") if not f.is_symlink()]
    return max(files, key=lambda f: f.stat().st_mtime) if files else None


# ── Ingest (JSONL → DB) ─────────────────────────────────────
def ingest_jsonl(db, jsonl_path):
    """Parse a JSONL file and upsert into the database. Returns session_id or None."""
    fname = jsonl_path.name
    mtime = jsonl_path.stat().st_mtime

    # Fast path: already ingested this exact file version
    row = db.execute(
        "SELECT session_id FROM conversations WHERE source_file = ? AND source_mtime = ?",
        (fname, mtime)
    ).fetchone()
    if row:
        return row["session_id"]

    parsed = parse_jsonl(jsonl_path)
    if not parsed or len(parsed["messages"]) < 2:
        return None

    sid = parsed["session_id"]
    msgs = parsed["messages"]
    content_hash = md5_str(json.dumps(msgs, ensure_ascii=False))
    word_count = sum(len(m["content"].split()) for m in msgs)
    project_name = parsed["project"].split("/")[-1] if parsed["project"] else ""
    now_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    existing = db.execute(
        "SELECT content_hash, status, source_mtime FROM conversations WHERE session_id = ?",
        (sid,)
    ).fetchone()

    if existing:
        # Only update if this file is newer
        if existing["source_mtime"] and mtime <= existing["source_mtime"]:
            return sid
        new_status = existing["status"]
        if existing["status"] != "ignored" and existing["content_hash"] != content_hash:
            new_status = "unsynced"
        db.execute("""
            UPDATE conversations SET
                title=?, date=?, project=?, project_path=?,
                message_count=?, word_count=?, content_hash=?,
                source_file=?, source_mtime=?, updated_at=?, status=?
            WHERE session_id=?
        """, (parsed["title"], parsed["date"], project_name,
              parsed["project"], len(msgs), word_count, content_hash,
              fname, mtime, now_ts, new_status, sid))
    else:
        db.execute("""
            INSERT INTO conversations
            (session_id, title, date, project, project_path, message_count, word_count,
             content_hash, source_file, source_mtime, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid, parsed["title"], parsed["date"], project_name,
              parsed["project"], len(msgs), word_count, content_hash,
              fname, mtime, now_ts, now_ts))

    # Replace messages for this session
    db.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    db.executemany(
        "INSERT INTO messages (session_id, seq, role, content, time_str, is_context) VALUES (?,?,?,?,?,?)",
        [(sid, i, m["role"], m["content"], m["time_str"], int(m.get("is_context", False)))
         for i, m in enumerate(msgs)]
    )
    db.commit()
    return sid


def ingest_all(db):
    """Ingest all JSONL files into the database. Returns count of processed sessions."""
    count = 0
    for jf in find_all_jsonl():
        if ingest_jsonl(db, jf):
            count += 1
    return count


def ingest_latest(db):
    """Ingest only the most recent JSONL file. Returns session_id or None."""
    jf = find_latest_jsonl()
    return ingest_jsonl(db, jf) if jf else None


# ── Sync (DB → FNS) ─────────────────────────────────────────
def resolve_path_db(db, sync_dir, title, session_id):
    """Determine FNS path for a session, using DB for conflict detection."""
    # Reuse existing path if already synced
    row = db.execute(
        "SELECT synced_path FROM conversations WHERE session_id = ? AND synced_path IS NOT NULL",
        (session_id,)
    ).fetchone()
    if row:
        return row["synced_path"]

    # Collect all paths in use
    used = {r["synced_path"] for r in db.execute(
        "SELECT synced_path FROM conversations WHERE synced_path IS NOT NULL"
    ).fetchall()}

    base = f"{sync_dir}/{title}.md"
    if base not in used:
        return base
    for i in range(2, 10000):
        candidate = f"{sync_dir}/{title} ({i}).md"
        if candidate not in used:
            return candidate
    return f"{sync_dir}/{title} ({session_id[:8]}).md"


def sync_session(cfg, db, session_id, echo=False):
    """Sync a single session via the configured output adapter. Returns True/None/False."""
    row = db.execute(
        "SELECT * FROM conversations WHERE session_id = ? AND status = 'unsynced'",
        (session_id,)
    ).fetchone()
    if not row:
        return None  # already synced or ignored

    # Reconstruct parsed dict from DB
    msgs = db.execute(
        "SELECT role, content, time_str, is_context FROM messages WHERE session_id = ? ORDER BY seq",
        (session_id,)
    ).fetchall()
    parsed = {
        "session_id": session_id,
        "date": row["date"],
        "project": row["project_path"] or row["project"],
        "title": row["title"],
        "messages": [{"role": m["role"], "content": m["content"],
                      "time_str": m["time_str"], "is_context": bool(m["is_context"])} for m in msgs],
    }

    adapter = get_adapter(cfg)

    if isinstance(adapter, ServerAdapter):
        ok, rel_path = _sync_server_v2(adapter, cfg, db, parsed, row, echo)
    else:
        # Lite mode: format markdown and write via adapter
        content = format_conversation(parsed)
        sync_dir = cfg.get("sync_dir", "aichatlog")
        rel_path = resolve_path_db(db, sync_dir, row["title"], session_id)
        ok, msg = adapter.write_note(rel_path, content)
        icon = "\u2705" if ok else "\u274c"
        log(f"{icon} {rel_path}", echo=echo)

    if ok:
        now_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if isinstance(adapter, ServerAdapter):
            # Server mode: store sync state for delta detection
            db.execute("""
                UPDATE conversations SET status='synced', synced_path=?, synced_at=?,
                    synced_hash=?, synced_message_count=?, updated_at=?
                WHERE session_id=?
            """, (rel_path, now_ts, row["content_hash"], row["message_count"],
                  now_ts, session_id))
        else:
            # Lite mode: no delta state needed
            db.execute("""
                UPDATE conversations SET status='synced', synced_path=?, synced_at=?, updated_at=?
                WHERE session_id=?
            """, (rel_path, now_ts, now_ts, session_id))
        db.commit()
        return True
    return False


def _sync_server_v2(adapter, cfg, db, parsed, row, echo):
    """Server mode sync using v2 conditional protocol. Returns (ok, rel_path)."""
    session_id = parsed["session_id"]
    rel_path = f"server:{parsed['title']}"

    # Determine sync mode based on local state
    synced_hash = row["synced_hash"] if "synced_hash" in row.keys() else None
    if synced_hash is None:
        mode = "full"       # never synced to server before
    elif row["content_hash"] == synced_hash:
        mode = "check"      # content unchanged, just verify with server
    else:
        mode = "delta"      # content changed, send incremental update

    conv_obj = to_conversation_object_v2(parsed, cfg, mode, row)
    ok, resp = adapter.send_sync(conv_obj)

    # Fallback to v1 if server doesn't support /sync endpoint
    if not ok and isinstance(resp, dict) and resp.get("fallback"):
        conv_obj = to_conversation_object(parsed, cfg)
        ok, resp = adapter.send_conversation(conv_obj)
        icon = "\u2705" if ok else "\u274c"
        log(f"{icon} {rel_path} (v1 fallback)", echo=echo)
        return ok, rel_path

    if not ok:
        log(f"\u274c {rel_path}: {resp}", echo=echo)
        return False, rel_path

    action = resp.get("action", "")

    # If server says need_full, retry with full payload
    if action == "need_full":
        conv_obj = to_conversation_object_v2(parsed, cfg, "full", row)
        ok, resp = adapter.send_sync(conv_obj)
        if not ok:
            log(f"\u274c {rel_path}: {resp}", echo=echo)
            return False, rel_path
        action = resp.get("action", "")

    icon = "\u2705" if ok else "\u274c"
    log(f"{icon} {rel_path} [{mode}→{action}]", echo=echo)
    return ok, rel_path


# ── Subcommands ──────────────────────────────────────────────

def parse_fns_json(text):
    """Parse FNS JSON config block: {"api": "...", "apiToken": "...", "vault": "..."}"""
    try:
        obj = json.loads(text)
        if "api" in obj and "apiToken" in obj:
            return obj
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def prompt_lang(cfg):
    """Prompt user to select language. Returns chosen lang code."""
    print(f"\n  — {t('select_lang')} —\n")
    langs = list(LANG_NAMES.items())
    for i, (code, name) in enumerate(langs, 1):
        cur = " *" if code == cfg.get("lang", "en") else ""
        print(f"    {i}. {name}{cur}")
    choice = input(f"\n  [{cfg.get('lang', 'en')}]: ").strip()
    if choice in ("1", "2", "3"):
        return langs[int(choice) - 1][0]
    if choice in LANG_NAMES:
        return choice
    return cfg.get("lang", "en")


def _setup_interactive(cfg):
    """Interactive setup wizard. Guides user through adapter selection and configuration."""
    print("\n  AIChatLog Setup\n")

    # 1. Choose adapter
    current_adapter = cfg.get("output", {}).get("adapter", "fns")
    print("  Choose output adapter:")
    adapters = [
        ("local",  "Local .md files"),
        ("fns",    "Obsidian (via Fast Note Sync)"),
        ("git",    "Git repo (auto-commit)"),
        ("server", "AIChatLog Server"),
    ]
    for i, (key, desc) in enumerate(adapters, 1):
        marker = " *" if key == current_adapter else ""
        print(f"    {i}. {key:8s} — {desc}{marker}")

    choice = input(f"\n  Adapter [{current_adapter}]: ").strip()
    if choice in ("1", "2", "3", "4"):
        current_adapter = adapters[int(choice) - 1][0]
    elif choice in [a[0] for a in adapters]:
        current_adapter = choice
    cfg["output"]["adapter"] = current_adapter

    # 2. Adapter-specific config
    if current_adapter == "local":
        acfg = cfg["output"].setdefault("local", {})
        path = input(f"  Output path [{acfg.get('path', '~/aichatlog-notes')}]: ").strip()
        if path:
            acfg["path"] = path
        elif not acfg.get("path"):
            acfg["path"] = "~/aichatlog-notes"

    elif current_adapter == "fns":
        acfg = cfg["output"].setdefault("fns", {})
        print("\n  Paste FNS JSON from Obsidian, or enter values manually:")
        fns_input = input("  FNS JSON or API URL: ").strip()
        fns_json = parse_fns_json(fns_input) if fns_input else None
        if fns_json:
            acfg["url"] = fns_json["api"].rstrip("/")
            acfg["token"] = fns_json["apiToken"]
            acfg["vault"] = fns_json.get("vault", "")
        else:
            if fns_input:
                acfg["url"] = fns_input
            else:
                url = input(f"  API URL [{acfg.get('url', '')}]: ").strip()
                if url:
                    acfg["url"] = url
            existing_token = acfg.get("token", "")
            token_hint = f"{existing_token[:8]}..." if existing_token else "not set"
            token = input(f"  Token [{token_hint}]: ").strip()
            if token:
                acfg["token"] = token
            vault = input(f"  Vault [{acfg.get('vault', '') or 'not set'}]: ").strip()
            if vault:
                acfg["vault"] = vault

    elif current_adapter == "git":
        acfg = cfg["output"].setdefault("git", {})
        repo = input(f"  Git repo path [{acfg.get('repo_path', '')}]: ").strip()
        if repo:
            acfg["repo_path"] = repo
        push = input(f"  Auto-push? (y/N) [{acfg.get('auto_push', False)}]: ").strip().lower()
        if push in ("y", "yes", "true"):
            acfg["auto_push"] = True

    elif current_adapter == "server":
        acfg = cfg["output"].setdefault("server", {})
        url = input(f"  Server URL [{acfg.get('url', 'http://localhost:8080')}]: ").strip()
        if url:
            acfg["url"] = url
        elif not acfg.get("url"):
            acfg["url"] = "http://localhost:8080"
        existing_token = acfg.get("token", "")
        token_hint = f"{existing_token[:8]}..." if existing_token else "not set"
        token = input(f"  Token [{token_hint}]: ").strip()
        if token:
            acfg["token"] = token

    # 3. Language
    print(f"\n  Language: 1) English  2) 简体中文  3) 繁體中文")
    lang_choice = input(f"  [{cfg.get('lang', 'en')}]: ").strip()
    if lang_choice == "1": cfg["lang"] = "en"
    elif lang_choice == "2": cfg["lang"] = "zh-CN"
    elif lang_choice == "3": cfg["lang"] = "zh-TW"

    return cfg


def cmd_setup():
    """Setup wizard. Interactive when no args, non-interactive with --key=value args."""
    cfg = cfg_load() or {
        "lang": "en",
        "device_name": os.uname().nodename.split(".")[0],
        "sync_dir": "aichatlog",
        "output": {"adapter": "fns", "fns": {"url": "", "token": "", "vault": ""}},
    }
    cfg.setdefault("output", {"adapter": "fns"})

    args = sys.argv[2:]
    args_text = " ".join(args).strip()

    if not args_text:
        # Interactive mode
        cfg = _setup_interactive(cfg)
    else:
        # Non-interactive: parse FNS JSON or --key=value args
        fns_json = parse_fns_json(args_text)
        if fns_json:
            cfg["output"]["adapter"] = "fns"
            cfg["output"]["fns"] = {
                "url": fns_json["api"].rstrip("/"),
                "token": fns_json["apiToken"],
                "vault": fns_json.get("vault", ""),
            }
            cfg["fns_api"] = cfg["output"]["fns"]

        for arg in args:
            if arg.startswith("--"):
                k, _, v = arg[2:].partition("=")
                if k == "adapter":
                    cfg["output"]["adapter"] = v
                elif k == "path":
                    cfg["output"].setdefault("local", {})["path"] = v
                elif k == "repo-path":
                    cfg["output"].setdefault("git", {})["repo_path"] = v
                elif k == "auto-push":
                    cfg["output"].setdefault("git", {})["auto_push"] = v.lower() in ("true", "1", "yes")
                elif k == "url":
                    adapter = cfg["output"].get("adapter", "fns")
                    cfg["output"].setdefault(adapter, {})["url"] = v
                elif k == "token":
                    adapter = cfg["output"].get("adapter", "fns")
                    cfg["output"].setdefault(adapter, {})["token"] = v
                elif k == "vault":
                    cfg["output"].setdefault("fns", {})["vault"] = v
                elif k == "lang":    cfg["lang"] = v
                elif k == "device":  cfg["device_name"] = v
                elif k == "sync-dir": cfg["sync_dir"] = v

    CC_LOGS.mkdir(parents=True, exist_ok=True)

    # Detect adapter change — reset synced conversations
    old_cfg = cfg_load() or {}
    old_adapter = old_cfg.get("output", {}).get("adapter", "fns")
    new_adapter = cfg["output"].get("adapter", "fns")
    if old_adapter != new_adapter:
        try:
            db = db_connect()
            count = db.execute(
                "UPDATE conversations SET status='unsynced', synced_hash=NULL, synced_message_count=0 WHERE status='synced'"
            ).rowcount
            db.commit()
            db.close()
            if count:
                print(f"\n  {t('adapter_changed')} ({old_adapter} → {new_adapter}): {count} {t('marked_resync')}")
        except Exception:
            pass

    cfg_save(cfg)

    # Display final config
    adapter_name = cfg["output"].get("adapter", "fns")
    adapter_cfg = cfg["output"].get(adapter_name, {})
    print(f"\n  AIChatLog — Config\n")
    print(f"  Language:  {LANG_NAMES.get(cfg.get('lang', 'en'), 'English')}")
    print(f"  Device:    {cfg['device_name']}")
    print(f"  Adapter:   {adapter_name}")
    if adapter_name == "fns":
        print(f"  API:       {adapter_cfg.get('url', '(not set)')}")
        print(f"  Vault:     {adapter_cfg.get('vault', '(not set)')}")
        token = adapter_cfg.get("token", "")
        print(f"  Token:     {token[:12]}..." if token else "  Token:     (not set)")
    elif adapter_name == "local":
        print(f"  Path:      {adapter_cfg.get('path', '(not set)')}")
    elif adapter_name == "git":
        print(f"  Repo:      {adapter_cfg.get('repo_path', '(not set)')}")
        print(f"  Commit:    {adapter_cfg.get('auto_commit', True)}")
        print(f"  Push:      {adapter_cfg.get('auto_push', False)}")
    elif adapter_name == "server":
        print(f"  Server:    {adapter_cfg.get('url', '(not set)')}")
        token = adapter_cfg.get("token", "")
        print(f"  Token:     {token[:12]}..." if token else "  Token:     (not set)")
    print(f"  Sync dir:  {cfg.get('sync_dir', 'aichatlog')}")
    print(f"  Config:    {CONFIG_FILE}")
    print(f"\n  \u2705 {t('config_saved')} {CONFIG_FILE}\n")


def cmd_hook():
    """Stop hook entry point. Syncs latest conversation via configured adapter."""
    cfg = cfg_load()
    if not cfg_is_configured(cfg):
        log("Not configured — run /aichatlog:setup"); return 0
    db = db_connect()
    sid = ingest_latest(db)
    if sid:
        result = sync_session(cfg, db, sid)
        if result:
            log(f"Synced 1 file(s) (device={cfg.get('device_name')})")
    db.close()


def cmd_run():
    """Manual one-shot sync of latest conversation. Use --force to re-sync even if already synced."""
    cfg = cfg_load()
    if not cfg: print(f"  {t('not_configured')}"); return 1
    force = "--force" in sys.argv
    print(f"  Device: {cfg['device_name']}\n")
    db = db_connect()
    if force:
        db.execute("UPDATE conversations SET source_mtime = 0")
        db.commit()
    sid = ingest_latest(db)
    if sid:
        if force:
            db.execute("UPDATE conversations SET status = 'unsynced' WHERE session_id = ?", (sid,))
            db.commit()
        result = sync_session(cfg, db, sid, echo=True)
        if result is True:
            print(f"\n  \u2705 {t('synced')} 1 {t('files')}")
        elif result is None:
            print(f"\n  \U0001f4ed {t('nothing_new')}")
        else:
            print(f"\n  \u274c {t('upload_failed')}")
    else:
        print(f"\n  \U0001f4ed {t('nothing_new')}")
    db.close()


def cmd_test():
    cfg = cfg_load()
    if not cfg: print(f"  {t('not_configured')}"); return 1

    adapter_name = cfg.get("output", {}).get("adapter", "fns")
    print(f"  Adapter: {adapter_name}")
    adapter_cfg = cfg.get("output", {}).get(adapter_name, {})
    if adapter_name == "fns":
        print(f"  URL:     {adapter_cfg.get('url')}")
        print(f"  Vault:   {adapter_cfg.get('vault')}")
        token = adapter_cfg.get("token", "")
        print(f"  Token:   {token[:12]}..." if token else "  Token:   (not set)")
    elif adapter_name == "local":
        print(f"  Path:    {adapter_cfg.get('path')}")
    elif adapter_name == "git":
        print(f"  Repo:    {adapter_cfg.get('repo_path')}")
    elif adapter_name == "server":
        print(f"  Server:  {adapter_cfg.get('url')}")
    print()

    try:
        adapter = get_adapter(cfg)
        ok, msg = adapter.test_connection()
    except ValueError as e:
        ok, msg = False, str(e)

    if ok:
        print(f"  \u2705 {t('upload_ok')}")
    else:
        print(f"  \u274c {t('upload_failed')}")
        print(f"  Error: {msg}")
        print(f"\n  \U0001f4a1 {t('check_config')}: {CONFIG_FILE}")
        print(f"     {t('or_reconfigure')}")


def cmd_status():
    cfg = cfg_load()
    if not cfg:
        print(f"  {t('not_configured')}"); return 1

    db = db_connect()
    stats = {}
    for row in db.execute("SELECT status, count(*) as n FROM conversations GROUP BY status"):
        stats[row["status"]] = row["n"]
    total = sum(stats.values())
    db.close()

    lang_name = LANG_NAMES.get(cfg.get("lang", "en"), "English")
    adapter_name = cfg.get("output", {}).get("adapter", "fns")
    print(f"  Language:  {lang_name}")
    print(f"  Device:    {cfg.get('device_name')}")
    print(f"  Adapter:   {adapter_name}")
    adapter_cfg = cfg.get("output", {}).get(adapter_name, {})
    if adapter_name == "fns":
        print(f"  FNS URL:   {adapter_cfg.get('url')}")
        print(f"  Vault:     {adapter_cfg.get('vault')}")
    elif adapter_name == "local":
        print(f"  Path:      {adapter_cfg.get('path')}")
    elif adapter_name == "git":
        print(f"  Repo:      {adapter_cfg.get('repo_path')}")
    elif adapter_name == "server":
        print(f"  Server:    {adapter_cfg.get('url')}")
    print(f"  Sync dir:  {cfg.get('sync_dir', 'aichatlog')}")
    print(f"  {t('processed')}  {total} {t('conversations')}")
    if stats:
        parts = []
        if stats.get("synced"):    parts.append(f"synced: {stats['synced']}")
        if stats.get("unsynced"):  parts.append(f"unsynced: {stats['unsynced']}")
        if stats.get("ignored"):   parts.append(f"ignored: {stats['ignored']}")
        print(f"  Status:    {', '.join(parts)}")
    print(f"  Config:    {CONFIG_FILE}")
    print(f"  Database:  {DB_FILE}")
    print(f"  Log:       {LOG_FILE}")

    if LOG_FILE.exists():
        lines = LOG_FILE.read_text().strip().split("\n")
        print(f"\n  {t('recent_activity')}")
        for l in lines[-3:]:
            print(f"    {l}")


def cmd_export():
    """Scan all conversations and sync any that haven't been uploaded yet. Use --force to re-sync all."""
    cfg = cfg_load()
    if not cfg: print(f"  {t('not_configured')}"); return 1
    force = "--force" in sys.argv

    print(f"  {t('export_scanning')}")
    db = db_connect()

    if force:
        # Force re-ingest + mark all synced as unsynced
        db.execute("UPDATE conversations SET source_mtime = 0")
        db.execute("UPDATE conversations SET status = 'unsynced' WHERE status = 'synced'")
        db.commit()
        print(f"  {t('force_resync')}")

    ingest_all(db)

    rows = db.execute(
        "SELECT session_id, title FROM conversations WHERE status = 'unsynced' ORDER BY date"
    ).fetchall()
    total = db.execute("SELECT count(*) as n FROM conversations").fetchone()["n"]
    synced = total - len(rows)

    print(f"  {t('export_found')} {len(rows)} {t('export_new')}, {synced} {t('export_skipped')}\n")

    if not rows:
        print(f"  {t('export_no_new')}")
        db.close()
        return 0

    ok_count, fail_count = 0, 0
    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] {t('export_progress')} {row['title']}...", end="", flush=True)
        result = sync_session(cfg, db, row["session_id"])
        if result is True:
            ok_count += 1
            print(" \u2705")
        elif result is None:
            print(" -")
        else:
            fail_count += 1
            print(" \u274c")

    print(f"\n  {t('export_done')}: {ok_count} {t('files')}", end="")
    if fail_count:
        print(f", {fail_count} {t('export_failed_n')}", end="")
    print()
    db.close()


def cmd_ingest():
    """Manually ingest all JSONL files into the database. Use --force to re-parse all."""
    force = "--force" in sys.argv
    db = db_connect()
    if force:
        db.execute("UPDATE conversations SET source_mtime = 0")
        db.commit()
        print(f"  {t('force_clearing')}")
    ingest_all(db)
    total = db.execute("SELECT count(*) as n FROM conversations").fetchone()["n"]
    stats = {}
    for row in db.execute("SELECT status, count(*) as n FROM conversations GROUP BY status"):
        stats[row["status"]] = row["n"]
    print(f"  {t('database')}: {DB_FILE}")
    print(f"  {t('total_conv')}: {total}")
    if stats:
        parts = []
        if stats.get("synced"):    parts.append(f"{t('synced')}: {stats['synced']}")
        if stats.get("unsynced"):  parts.append(f"unsynced: {stats['unsynced']}")
        if stats.get("ignored"):   parts.append(f"ignored: {stats['ignored']}")
        print(f"  Status: {', '.join(parts)}")
    db.close()


def cmd_log():
    if not LOG_FILE.exists(): print(f"  {t('no_log')}"); return 0
    for l in LOG_FILE.read_text().strip().split("\n")[-30:]:
        print(l)


# ── Web Dashboard ────────────────────────────────────────────
def cmd_web():
    """Launch the session management dashboard on localhost."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    # Parse --port and --no-browser
    port = 8765
    open_browser = True
    for arg in sys.argv[2:]:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg == "--no-browser":
            open_browser = False

    db = db_connect()
    print(f"  {t('ingesting')}")
    ingest_all(db)
    total = db.execute("SELECT count(*) as n FROM conversations").fetchone()["n"]
    print(f"  {total} {t('conv_in_db')}\n")

    html_path = Path(__file__).parent / "dashboard.html"

    def json_response(handler, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        handler.wfile.write(body)

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/dashboard":
                if not html_path.exists():
                    self.send_error(404, "dashboard.html not found")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_path.read_bytes())

            elif self.path.startswith("/api/conversations"):
                from urllib.parse import urlparse, parse_qs
                parsed_url = urlparse(self.path)
                path_part = parsed_url.path
                qs = parse_qs(parsed_url.query)

                # Detail: GET /api/conversations/{session_id}
                if path_part != "/api/conversations" and path_part.startswith("/api/conversations/"):
                    sid = path_part[len("/api/conversations/"):].split("/")[0]
                    if sid:
                        row = db.execute("SELECT * FROM conversations WHERE session_id = ?", (sid,)).fetchone()
                        if not row:
                            json_response(self, {"ok": False, "error": "Not found"}, 404)
                            return
                        result = dict(row)
                        if qs.get("full", [None])[0] == "true":
                            msgs = db.execute(
                                "SELECT * FROM messages WHERE session_id = ? ORDER BY seq", (sid,)
                            ).fetchall()
                            result["messages"] = [dict(m) for m in msgs]
                        json_response(self, result)
                        return

                # List: GET /api/conversations
                status_filter = qs.get("status", [None])[0]
                query = qs.get("q", [None])[0]
                sort = qs.get("sort", ["date"])[0]
                # Map server column names to plugin column names
                sort_map = {"started_at": "date", "created_at": "created_at"}
                sort = sort_map.get(sort, sort)
                # Whitelist valid sort columns
                if sort not in ("date", "title", "project", "word_count", "message_count", "created_at"):
                    sort = "date"
                order = qs.get("order", ["desc"])[0]
                limit = int(qs.get("limit", [200])[0])
                offset = int(qs.get("offset", [0])[0])

                if query:
                    # FTS5 search
                    try:
                        rows = db.execute("""
                            SELECT c.* FROM conversations c
                            JOIN conversations_fts f ON c.session_id = f.session_id
                            WHERE conversations_fts MATCH ?
                            ORDER BY c.date DESC LIMIT ? OFFSET ?
                        """, (query, limit, offset)).fetchall()
                    except Exception:
                        # FTS5 not available, fall back to LIKE
                        rows = db.execute("""
                            SELECT * FROM conversations
                            WHERE title LIKE ? OR project LIKE ?
                            ORDER BY date DESC LIMIT ? OFFSET ?
                        """, (f"%{query}%", f"%{query}%", limit, offset)).fetchall()
                elif status_filter:
                    rows = db.execute(f"""
                        SELECT * FROM conversations WHERE status = ?
                        ORDER BY {sort} {'ASC' if order == 'asc' else 'DESC'}
                        LIMIT ? OFFSET ?
                    """, (status_filter, limit, offset)).fetchall()
                else:
                    rows = db.execute(f"""
                        SELECT * FROM conversations
                        ORDER BY {sort} {'ASC' if order == 'asc' else 'DESC'}
                        LIMIT ? OFFSET ?
                    """, (limit, offset)).fetchall()

                results = []
                for r in rows:
                    d = dict(r)
                    results.append(d)
                json_response(self, results)

            elif self.path.startswith("/api/stats"):
                stats = {"unsynced": 0, "synced": 0, "ignored": 0}
                for row in db.execute("SELECT status, count(*) as n FROM conversations GROUP BY status"):
                    stats[row["status"]] = row["n"]
                stats["total"] = sum(stats.values())

                if "/summary" in self.path:
                    # Extended stats
                    wc = db.execute("SELECT COALESCE(SUM(word_count),0) as w FROM conversations").fetchone()
                    pc = db.execute("SELECT COUNT(DISTINCT project) as p FROM conversations WHERE project != ''").fetchone()
                    stats["total_input_tokens"] = 0
                    stats["total_output_tokens"] = 0
                    stats["total_words"] = wc["w"]
                    stats["extraction_count"] = 0
                    stats["project_count"] = pc["p"]
                json_response(self, stats)

            elif self.path == "/api/config":
                c = cfg_load() or {}
                output = c.get("output", {})
                adapter_name = output.get("adapter", "fns")
                adapter_cfg = output.get(adapter_name, {})
                # Build adapter-specific info for dashboard
                adapter_info = {"adapter": adapter_name}
                if adapter_name == "fns":
                    token = adapter_cfg.get("token", "")
                    adapter_info.update({
                        "url": adapter_cfg.get("url", ""),
                        "token_preview": (token[:12] + "...") if len(token) > 12 else token,
                        "token_set": bool(token),
                        "vault": adapter_cfg.get("vault", ""),
                    })
                elif adapter_name == "local":
                    adapter_info["path"] = adapter_cfg.get("path", "")
                elif adapter_name == "git":
                    adapter_info["repo_path"] = adapter_cfg.get("repo_path", "")
                    adapter_info["auto_commit"] = adapter_cfg.get("auto_commit", True)
                    adapter_info["auto_push"] = adapter_cfg.get("auto_push", False)
                elif adapter_name == "server":
                    token = adapter_cfg.get("token", "")
                    adapter_info["url"] = adapter_cfg.get("url", "")
                    adapter_info["token_set"] = bool(token)
                # Backward compat: also include fns_api for old dashboard versions
                api = c.get("fns_api", output.get("fns", {}))
                fns_token = api.get("token", "")
                json_response(self, {
                    "lang": c.get("lang", "en"),
                    "device_name": c.get("device_name", ""),
                    "sync_dir": c.get("sync_dir", "aichatlog"),
                    "output": adapter_info,
                    "fns_api": {
                        "url": api.get("url", ""),
                        "token_preview": (fns_token[:12] + "...") if len(fns_token) > 12 else fns_token,
                        "token_set": bool(fns_token),
                        "vault": api.get("vault", ""),
                    }
                })

            elif self.path.startswith("/api/extractions"):
                # Plugin has no LLM extraction — return empty list
                json_response(self, [])

            elif self.path.startswith("/api/log"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                limit = int(qs.get("limit", [100])[0])
                lines = []
                if LOG_FILE.exists():
                    all_lines = LOG_FILE.read_text().strip().split("\n")
                    if all_lines != [""]:
                        lines = all_lines[-limit:]
                json_response(self, {"lines": list(reversed(lines)), "total": len(lines)})

            elif self.path == "/api/info":
                json_response(self, {
                    "version": "0.6.0",
                    "db_path": str(DB_FILE),
                    "config_path": str(CONFIG_FILE),
                    "log_path": str(LOG_FILE),
                })

            else:
                self.send_error(404)

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else {}
            except (json.JSONDecodeError, ValueError):
                json_response(self, {"error": "Invalid JSON"}, 400)
                return

            sid = body.get("session_id", "")
            now_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            if self.path == "/api/sync":
                cfg = cfg_load()
                if not cfg_is_configured(cfg):
                    json_response(self, {"ok": False, "message": "Not configured"}, 400); return
                result = sync_session(cfg, db, sid)
                if result is True:
                    json_response(self, {"ok": True, "message": "Synced"})
                elif result is None:
                    json_response(self, {"ok": False, "message": "Not unsynced"}, 400)
                else:
                    json_response(self, {"ok": False, "message": "Upload failed"}, 500)

            elif self.path == "/api/resync":
                cfg = cfg_load()
                if not cfg_is_configured(cfg):
                    json_response(self, {"ok": False, "message": "Not configured"}, 400); return
                db.execute(
                    "UPDATE conversations SET status='unsynced', updated_at=? WHERE session_id=?",
                    (now_ts, sid))
                db.commit()
                result = sync_session(cfg, db, sid)
                ok = result is True
                json_response(self, {"ok": ok, "message": "Resynced" if ok else "Failed"})

            elif self.path == "/api/ignore":
                db.execute(
                    "UPDATE conversations SET status='ignored', updated_at=? WHERE session_id=?",
                    (now_ts, sid))
                db.commit()
                json_response(self, {"ok": True, "message": "Ignored"})

            elif self.path == "/api/unignore":
                db.execute(
                    "UPDATE conversations SET status='unsynced', updated_at=? WHERE session_id=? AND status='ignored'",
                    (now_ts, sid))
                db.commit()
                json_response(self, {"ok": True, "message": "Unignored"})

            elif self.path == "/api/ingest":
                ingest_all(db)
                total = db.execute("SELECT count(*) as n FROM conversations").fetchone()["n"]
                json_response(self, {"ok": True, "total": total})

            elif self.path == "/api/config":
                old = cfg_load() or {}
                new_cfg = {
                    "lang": body.get("lang", old.get("lang", "en")),
                    "device_name": body.get("device_name", old.get("device_name", "")),
                    "sync_dir": body.get("sync_dir", old.get("sync_dir", "aichatlog")),
                    "output": body.get("output", old.get("output", {"adapter": "fns"})),
                }
                # Backward compat: accept fns_api from old dashboard
                if "fns_api" in body and "output" not in body:
                    fns_cfg = {
                        "url": body["fns_api"].get("url", ""),
                        "token": body["fns_api"].get("token", ""),
                        "vault": body["fns_api"].get("vault", ""),
                    }
                    if not fns_cfg["token"]:
                        fns_cfg["token"] = old.get("output", {}).get("fns", old.get("fns_api", {})).get("token", "")
                    new_cfg["output"] = {"adapter": "fns", "fns": fns_cfg}
                    new_cfg["fns_api"] = fns_cfg
                cfg_save(new_cfg)
                json_response(self, {"ok": True, "message": "Config saved"})

            elif self.path == "/api/test":
                import time
                cfg = cfg_load()
                if not cfg_is_configured(cfg):
                    json_response(self, {"ok": False, "message": "Not configured", "latency_ms": 0}, 400); return
                t0 = time.time()
                try:
                    adapter = get_adapter(cfg)
                    ok, msg = adapter.test_connection()
                except ValueError as e:
                    ok, msg = False, str(e)
                latency = int((time.time() - t0) * 1000)
                json_response(self, {"ok": ok, "message": "OK" if ok else str(msg), "latency_ms": latency})

            elif self.path == "/api/sync-all":
                cfg = cfg_load()
                if not cfg_is_configured(cfg):
                    json_response(self, {"ok": False, "message": "Not configured"}, 400); return
                rows = db.execute("SELECT session_id FROM conversations WHERE status='unsynced'").fetchall()
                synced, failed = 0, 0
                for row in rows:
                    result = sync_session(cfg, db, row["session_id"])
                    if result is True: synced += 1
                    elif result is False: failed += 1
                json_response(self, {"ok": True, "synced": synced, "failed": failed, "total_unsynced": len(rows)})

            else:
                self.send_error(404)

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, format, *args):
            pass  # suppress noisy access logs

    try:
        server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    except OSError as e:
        print(f"  \u274c Cannot bind to port {port}: {e}")
        print(f"  Try: python3 aichatlog.py web --port=8766")
        db.close()
        return 1

    url = f"http://127.0.0.1:{port}"
    print(f"  \u2705 {t('dashboard_url')}: {url}")
    print(f"  {t('press_ctrl_c')}\n")

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    db.close()


# ── Hook Install/Uninstall ────────────────────────────────────
def _get_settings_path():
    """Get Claude Code user settings path."""
    return HOME / ".claude" / "settings.json"

def _is_aichatlog_hook(entry):
    """Check if a Stop hook entry belongs to aichatlog (supports both old and new format)."""
    # New format: { "hooks": [{ "type": "command", "command": "aichatlog hook" }] }
    inner = entry.get("hooks", [])
    for h in inner:
        if h.get("command", "").startswith("aichatlog "):
            return True
    # Old format (pre-2025): { "type": "command", "command": "aichatlog hook" }
    if entry.get("command", "").startswith("aichatlog "):
        return True
    return False

def cmd_install():
    """Install aichatlog as a Claude Code Stop hook."""
    settings_path = _get_settings_path()
    settings = {}
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())

    hooks = settings.setdefault("hooks", {})
    stop_hooks = hooks.setdefault("Stop", [])

    # Check if already installed (handles both old and new format)
    for hook in stop_hooks:
        if _is_aichatlog_hook(hook):
            print("  \u2705 aichatlog hook is already installed.")
            return

    # New format: matcher + hooks array
    entry = {
        "hooks": [
            {"type": "command", "command": "aichatlog hook", "timeout": 30}
        ]
    }
    stop_hooks.append(entry)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print("  \u2705 Installed aichatlog Stop hook in Claude Code settings.")
    print(f"  Settings: {settings_path}")
    print("  Restart Claude Code to activate.")

def cmd_uninstall():
    """Remove aichatlog hook from Claude Code settings."""
    settings_path = _get_settings_path()
    if not settings_path.exists():
        print("  No Claude Code settings found.")
        return

    settings = json.loads(settings_path.read_text())
    stop_hooks = settings.get("hooks", {}).get("Stop", [])
    original_len = len(stop_hooks)
    stop_hooks[:] = [h for h in stop_hooks if not _is_aichatlog_hook(h)]

    if len(stop_hooks) == original_len:
        print("  aichatlog hook not found in settings.")
        return

    if not stop_hooks:
        settings.get("hooks", {}).pop("Stop", None)
    if not settings.get("hooks"):
        settings.pop("hooks", None)

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print("  \u2705 Removed aichatlog hook from Claude Code settings.")
    print("  Restart Claude Code to apply.")

def cmd_upgrade():
    """Upgrade aichatlog to the latest version from GitHub."""
    import subprocess
    print("  Upgrading aichatlog...")
    url = "git+https://github.com/aichatlog/aichatlog.git#subdirectory=plugins/claude-code"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", url],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        # Extract version from output
        for line in result.stdout.splitlines():
            if "Successfully installed" in line:
                print(f"  \u2705 {line.strip()}")
                return
        print("  \u2705 Already up to date.")
    else:
        print(f"  \u274c Upgrade failed:")
        print(f"  {result.stderr.strip()[:300]}")


# ── Entry ────────────────────────────────────────────────────
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if   cmd == "setup":     cmd_setup()
    elif cmd == "hook":      cmd_hook()
    elif cmd == "run":       cmd_run()
    elif cmd == "export":    cmd_export()
    elif cmd == "test":      cmd_test()
    elif cmd == "status":    cmd_status()
    elif cmd == "log":       cmd_log()
    elif cmd == "ingest":    cmd_ingest()
    elif cmd == "web":       cmd_web()
    elif cmd == "install":   cmd_install()
    elif cmd == "uninstall": cmd_uninstall()
    elif cmd == "upgrade":   cmd_upgrade()
    else:
        print("  aichatlog — CC conversation sync")
        print("  Commands: setup, hook, run, export, test, status, log, ingest, web")
        print("           install, uninstall, upgrade")

if __name__ == "__main__":
    try: main()
    except Exception as e: log(f"FATAL: {e}"); sys.exit(0)
