"""Tests for aichatlog plugin — parsing, adapter connectivity, auth, upload."""
import json
import os
import sys
import tempfile
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

# Add plugin source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from aichatlog.core import parse_jsonl, to_conversation_object, ServerAdapter

# ── Test JSONL Parsing ──

# All messages carry sessionId and cwd (as Claude Code JSONL does)
_COMMON = {"sessionId": "test-session-001", "cwd": "/home/user/project"}

SAMPLE_JSONL = [
    # User text
    {"type": "user", **_COMMON, "message": {"role": "user", "content": "Fix the bug in auth.py"}, "timestamp": "2026-03-23T10:00:01Z"},
    # Assistant with text + tool_use + thinking
    {"type": "assistant", **_COMMON, "message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "Let me analyze the auth module first."},
        {"type": "text", "text": "I'll look at the auth module."},
        {"type": "tool_use", "name": "Read", "input": {"file_path": "/src/auth.py"}},
    ], "model": "claude-sonnet-4", "usage": {"input_tokens": 100, "output_tokens": 50}}, "timestamp": "2026-03-23T10:00:05Z"},
    # Tool result
    {"type": "user", **_COMMON, "message": {"role": "user", "content": [
        {"type": "tool_result", "content": [{"type": "text", "text": "def login():\n    pass"}]},
    ]}, "timestamp": "2026-03-23T10:00:06Z"},
    # Assistant final response
    {"type": "assistant", **_COMMON, "message": {"role": "assistant", "content": [
        {"type": "text", "text": "Found the issue. Here's the fix:\n\n```python\ndef login():\n    validate()\n```"},
    ], "model": "claude-sonnet-4", "usage": {"input_tokens": 200, "output_tokens": 100}}, "timestamp": "2026-03-23T10:00:10Z"},
]


def write_jsonl(lines, path):
    with open(path, 'w') as f:
        for line in lines:
            f.write(json.dumps(line) + '\n')


def test_parse_text_messages():
    """Text messages are captured."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        path = f.name
        for line in SAMPLE_JSONL:
            f.write(json.dumps(line) + '\n')
    try:
        result = parse_jsonl(Path(path))
        assert result is not None, "parse_jsonl returned None"
        msgs = result['messages']
        assert len(msgs) >= 3, f"Expected at least 3 messages, got {len(msgs)}"
        # First user message should be plain text
        user_msgs = [m for m in msgs if m['role'] == 'user' and not m.get('is_context')]
        assert any("Fix the bug" in m['content'] for m in user_msgs), "User text message not found"
        print("  PASS: text messages captured")
    finally:
        os.unlink(path)


def test_parse_tool_use():
    """tool_use blocks are captured (not discarded)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        path = f.name
        for line in SAMPLE_JSONL:
            f.write(json.dumps(line) + '\n')
    try:
        result = parse_jsonl(Path(path))
        msgs = result['messages']
        # Find assistant message with tool_use
        assistant_msgs = [m for m in msgs if m['role'] == 'assistant']
        tool_found = any("Tool: Read" in m['content'] for m in assistant_msgs)
        assert tool_found, "tool_use block not captured in assistant message"
        print("  PASS: tool_use blocks captured")
    finally:
        os.unlink(path)


def test_parse_tool_result():
    """tool_result blocks are captured."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        path = f.name
        for line in SAMPLE_JSONL:
            f.write(json.dumps(line) + '\n')
    try:
        result = parse_jsonl(Path(path))
        msgs = result['messages']
        # Find user message with tool_result (rendered as code block)
        tool_result_found = any("def login" in m['content'] for m in msgs)
        assert tool_result_found, "tool_result content not captured"
        print("  PASS: tool_result blocks captured")
    finally:
        os.unlink(path)


def test_parse_thinking():
    """thinking blocks are captured."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        path = f.name
        for line in SAMPLE_JSONL:
            f.write(json.dumps(line) + '\n')
    try:
        result = parse_jsonl(Path(path))
        msgs = result['messages']
        thinking_found = any("analyze the auth" in m['content'] for m in msgs)
        assert thinking_found, "thinking block content not captured"
        print("  PASS: thinking blocks captured")
    finally:
        os.unlink(path)


def test_parse_token_counting():
    """Token counts are aggregated."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        path = f.name
        for line in SAMPLE_JSONL:
            f.write(json.dumps(line) + '\n')
    try:
        result = parse_jsonl(Path(path))
        assert result['total_input_tokens'] == 300, f"Expected 300 input tokens, got {result['total_input_tokens']}"
        assert result['total_output_tokens'] == 150, f"Expected 150 output tokens, got {result['total_output_tokens']}"
        print("  PASS: token counting correct")
    finally:
        os.unlink(path)


def test_parse_has_code():
    """has_code flag detected from code blocks."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        path = f.name
        for line in SAMPLE_JSONL:
            f.write(json.dumps(line) + '\n')
    try:
        result = parse_jsonl(Path(path))
        assert result['has_code'] is True, "has_code should be True when ``` present"
        print("  PASS: has_code detection")
    finally:
        os.unlink(path)


def test_conversation_object():
    """to_conversation_object builds valid v1 object."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        path = f.name
        for line in SAMPLE_JSONL:
            f.write(json.dumps(line) + '\n')
    try:
        parsed = parse_jsonl(Path(path))
        cfg = {"server": {"url": ""}, "output": {"adapter": "server", "server": {"url": "", "token": ""}}}
        obj = to_conversation_object(parsed, cfg)
        assert obj['version'] == 1
        assert obj['session_id'] == 'test-session-001'
        assert len(obj['messages']) > 0
        assert all('seq' in m for m in obj['messages'])
        print("  PASS: ConversationObject v1 structure valid")
    finally:
        os.unlink(path)


# ── Server Integration Tests (require server binary) ──

def find_server_binary():
    """Find the server binary (built in CI or locally)."""
    candidates = [
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'server', 'aichatlog-server'),
        'aichatlog-server',
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return os.path.abspath(c)
    return None


class ServerProcess:
    """Context manager to start/stop an aichatlog-server for testing."""
    def __init__(self, binary, port=18765):
        self.binary = binary
        self.port = port
        self.proc = None
        self.db_path = None

    def __enter__(self):
        self.db_path = tempfile.mktemp(suffix='.db')
        data_dir = tempfile.mkdtemp()
        self.proc = subprocess.Popen(
            [self.binary, '--port', str(self.port), '--db', self.db_path, '--data', data_dir],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        # Wait for server to be ready
        base = f'http://127.0.0.1:{self.port}'
        for _ in range(30):
            try:
                urllib.request.urlopen(f'{base}/api/health', timeout=1)
                return self
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("Server failed to start")

    def __exit__(self, *args):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        if self.db_path and os.path.exists(self.db_path):
            os.unlink(self.db_path)

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}'

    def api(self, method, path, body=None, headers=None):
        """Make HTTP request, return (status, data_dict)."""
        url = f'{self.url}{path}'
        data = json.dumps(body).encode() if body else None
        hdrs = {'Content-Type': 'application/json'}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())


def test_server_health(srv):
    """Health endpoint is always accessible."""
    status, data = srv.api('GET', '/api/health')
    assert status == 200, f"Health check failed: {status}"
    assert data['status'] == 'ok'
    print("  PASS: /api/health accessible")


def test_server_setup_required(srv):
    """Fresh server requires setup."""
    status, data = srv.api('GET', '/api/auth/status')
    assert status == 200
    assert data['setup_required'] is True
    assert data['authenticated'] is False
    print("  PASS: fresh server requires setup")


def test_server_setup(srv):
    """Create admin account."""
    status, data = srv.api('POST', '/api/auth/setup', {'username': 'admin', 'password': 'test123456'})
    assert status == 200, f"Setup failed: {data}"
    assert data['ok'] is True
    assert data['user']['role'] == 'admin'
    print("  PASS: admin account created")


def test_server_setup_once(srv):
    """Cannot setup twice."""
    status, data = srv.api('POST', '/api/auth/setup', {'username': 'admin2', 'password': 'test123456'})
    assert status == 409, f"Expected 409, got {status}"
    print("  PASS: setup blocked after first time")


def test_server_login(srv):
    """Login with correct credentials."""
    status, data = srv.api('POST', '/api/auth/login', {'username': 'admin', 'password': 'test123456'})
    assert status == 200, f"Login failed: {data}"
    assert data['ok'] is True
    print("  PASS: login with correct credentials")


def test_server_login_wrong_password(srv):
    """Login with wrong password fails."""
    status, data = srv.api('POST', '/api/auth/login', {'username': 'admin', 'password': 'wrong'})
    assert status == 401, f"Expected 401, got {status}"
    print("  PASS: wrong password rejected")


def test_server_no_auth_rejected(srv):
    """Protected endpoints reject unauthenticated requests."""
    status, data = srv.api('GET', '/api/conversations')
    assert status == 401, f"Expected 401, got {status}"
    print("  PASS: unauthenticated request rejected")


def test_server_api_key_flow(srv):
    """Create API key, use it to access protected endpoint, then revoke."""
    # Login to get session (we use raw urllib to capture cookies)
    login_body = json.dumps({'username': 'admin', 'password': 'test123456'}).encode()
    req = urllib.request.Request(f'{srv.url}/api/auth/login', data=login_body,
                                 headers={'Content-Type': 'application/json'}, method='POST')
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    resp = opener.open(req, timeout=5)
    assert resp.status == 200

    # Create API key
    create_req = urllib.request.Request(
        f'{srv.url}/api/keys',
        data=json.dumps({'name': 'test-key'}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    resp = opener.open(create_req, timeout=5)
    key_data = json.loads(resp.read())
    assert key_data['ok'] is True
    raw_key = key_data['key']
    key_id = key_data['info']['id']
    assert raw_key.startswith('ak_'), f"Key should start with ak_, got: {raw_key[:10]}"
    print("  PASS: API key created")

    # Use API key to access protected endpoint
    status, data = srv.api('GET', '/api/conversations', headers={'Authorization': f'Bearer {raw_key}'})
    assert status == 200, f"API key auth failed: {status}"
    print("  PASS: API key authenticates successfully")

    # Use wrong key
    status, data = srv.api('GET', '/api/conversations', headers={'Authorization': 'Bearer ak_invalid'})
    assert status == 401, f"Expected 401 for invalid key, got {status}"
    print("  PASS: invalid API key rejected")

    # Revoke key
    revoke_req = urllib.request.Request(
        f'{srv.url}/api/keys/{key_id}',
        headers={'Content-Type': 'application/json'}, method='DELETE')
    resp = opener.open(revoke_req, timeout=5)
    assert resp.status == 200
    print("  PASS: API key revoked")

    # Revoked key should fail
    status, data = srv.api('GET', '/api/conversations', headers={'Authorization': f'Bearer {raw_key}'})
    assert status == 401, f"Revoked key should fail, got {status}"
    print("  PASS: revoked API key rejected")


def test_server_adapter_test_connection(srv):
    """ServerAdapter.test_connection validates token, not just reachability."""
    # Login + create key
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(f'{srv.url}/api/auth/login',
                                 data=json.dumps({'username': 'admin', 'password': 'test123456'}).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    opener.open(req, timeout=5)
    req = urllib.request.Request(f'{srv.url}/api/keys',
                                 data=json.dumps({'name': 'conn-test'}).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    key_data = json.loads(opener.open(req, timeout=5).read())
    raw_key = key_data['key']

    # Valid token → success
    adapter_ok = ServerAdapter({'url': srv.url, 'token': raw_key})
    ok, msg = adapter_ok.test_connection()
    assert ok, f"Valid token should pass: {msg}"
    assert 'authenticated' in msg.lower(), f"Should mention authenticated: {msg}"
    print("  PASS: test_connection with valid token succeeds")

    # Invalid token → fails with clear message
    adapter_bad = ServerAdapter({'url': srv.url, 'token': 'ak_invalid_token'})
    ok, msg = adapter_bad.test_connection()
    assert not ok, "Invalid token should fail"
    assert 'token' in msg.lower() or 'invalid' in msg.lower(), f"Should mention token issue: {msg}"
    print("  PASS: test_connection with invalid token fails clearly")

    # No token → fails
    adapter_none = ServerAdapter({'url': srv.url, 'token': ''})
    ok, msg = adapter_none.test_connection()
    assert not ok, "No token should fail"
    print("  PASS: test_connection with no token fails")

    # Wrong URL → fails with unreachable
    adapter_bad_url = ServerAdapter({'url': 'http://127.0.0.1:19999', 'token': raw_key})
    ok, msg = adapter_bad_url.test_connection()
    assert not ok, "Bad URL should fail"
    assert 'unreachable' in msg.lower(), f"Should mention unreachable: {msg}"
    print("  PASS: test_connection with bad URL fails with 'unreachable'")


def test_server_upload_with_key(srv):
    """Upload conversation using API key via ServerAdapter."""
    # Login + create key
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(f'{srv.url}/api/auth/login',
                                 data=json.dumps({'username': 'admin', 'password': 'test123456'}).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    opener.open(req, timeout=5)
    req = urllib.request.Request(f'{srv.url}/api/keys',
                                 data=json.dumps({'name': 'upload-test'}).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    key_data = json.loads(opener.open(req, timeout=5).read())
    raw_key = key_data['key']

    # Use ServerAdapter to upload
    adapter = ServerAdapter({'url': srv.url, 'token': raw_key})
    ok, result = adapter.test_connection()
    assert ok, f"test_connection failed: {result}"
    print("  PASS: ServerAdapter.test_connection()")

    conv = {
        'version': 1, 'source': 'claude-code', 'device': 'test',
        'session_id': 'upload-test-001', 'title': 'Test Upload',
        'date': '2026-03-23', 'project': 'test-project',
        'message_count': 1, 'word_count': 5,
        'content_hash': 'testhash123',
        'messages': [{'role': 'user', 'content': 'hello world', 'seq': 0}],
    }
    ok, result = adapter.send_conversation(conv)
    assert ok, f"send_conversation failed: {result}"
    print("  PASS: ServerAdapter.send_conversation()")

    # Verify it's there
    status, data = srv.api('GET', '/api/conversations', headers={'Authorization': f'Bearer {raw_key}'})
    assert status == 200
    ids = [c['id'] for c in data]
    assert len(ids) > 0, "No conversations found after upload"
    print("  PASS: uploaded conversation visible in list")

    # Upload without token should fail
    adapter_no_auth = ServerAdapter({'url': srv.url, 'token': ''})
    ok, result = adapter_no_auth.send_conversation(conv)
    assert not ok, "Upload without token should fail"
    assert '401' in str(result), f"Expected 401 error, got: {result}"
    print("  PASS: upload without token rejected")


# ── Run Tests ──

def main():
    passed = 0
    failed = 0

    print("\n=== Plugin Unit Tests ===")
    unit_tests = [
        test_parse_text_messages,
        test_parse_tool_use,
        test_parse_tool_result,
        test_parse_thinking,
        test_parse_token_counting,
        test_parse_has_code,
        test_conversation_object,
    ]
    for test in unit_tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1

    # Server integration tests (skip if no binary)
    binary = find_server_binary()
    if binary:
        print(f"\n=== Server Integration Tests (binary: {binary}) ===")
        try:
            with ServerProcess(binary) as srv:
                integration_tests = [
                    test_server_health,
                    test_server_setup_required,
                    test_server_setup,
                    test_server_setup_once,
                    test_server_login,
                    test_server_login_wrong_password,
                    test_server_no_auth_rejected,
                    test_server_api_key_flow,
                    test_server_adapter_test_connection,
                    test_server_upload_with_key,
                ]
                for test in integration_tests:
                    try:
                        test(srv)
                        passed += 1
                    except Exception as e:
                        print(f"  FAIL: {test.__name__}: {e}")
                        failed += 1
        except Exception as e:
            print(f"  SKIP: Server integration tests (could not start server: {e})")
    else:
        print("\n=== Server Integration Tests: SKIPPED (no server binary) ===")

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
