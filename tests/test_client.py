import pytest
import socketio

from dockgectl.client import DockgeClient, status_name
from dockgectl.errors import ApiError, AuthError, NotFoundError


class FakeSocket:
    def __init__(self, *, info_mode=None, login_mode=None, agent_status="online"):
        self.handlers = {}
        self.connected = False
        self.calls = []
        self.connection_auth = None
        self.info_mode = info_mode
        self.login_mode = login_mode
        self.agent_status = agent_status

    def on(self, event, handler):
        self.handlers[event] = handler

    def connect(self, _url, wait_timeout=20, auth=None):
        self.connected = True
        self.connection_auth = auth
        info = {"version": "1.5.0"}
        if self.info_mode:
            info["agentConnectionMode"] = self.info_mode
        self.handlers["info"](info)

    def disconnect(self):
        self.connected = False

    def call(self, event, data=(), timeout=20):
        self.calls.append((event, data, timeout))
        if event == "login":
            payload = data[0]
            if payload.get("token") == "000000":
                return {"ok": True, "token": "jwt"}
            if payload.get("username") == "2fa":
                return {"tokenRequired": True}
            response = {"ok": True, "token": "jwt"}
            if self.login_mode:
                response["agentConnectionMode"] = self.login_mode
            return response
        if event == "loginByToken":
            self.handlers["agentList"]({
                "ok": True,
                "agentList": {
                    "": {"endpoint": "", "name": "", "url": "", "username": ""},
                    "remote.example.com": {
                        "endpoint": "remote.example.com",
                        "name": "remote",
                        "url": "https://remote.example.com",
                        "username": "admin",
                    },
                },
            })
            if self.agent_status:
                self.handlers["agentStatus"]({"endpoint": "remote.example.com", "status": self.agent_status})
            response = {"ok": True}
            if self.login_mode:
                response["agentConnectionMode"] = self.login_mode
            return response
        if event == "composerize":
            return {"ok": True, "composeTemplate": "services:\n  web:\n    image: nginx\n"}
        if event == "agent":
            endpoint, agent_event, *args = data
            if agent_event == "requestStackList":
                self.handlers["agent"]("stackList", {"ok": True, "endpoint": endpoint, "stackList": {"app": {"name": "app", "status": 3, "endpoint": endpoint}}})
                return {"ok": True}
            if agent_event == "getStack":
                if args[0] == "missing":
                    return {"ok": False, "msg": "Stack not found"}
                return {"ok": True, "stack": {"name": args[0], "status": 3}}
            if agent_event == "terminalJoin":
                return {"ok": True, "buffer": "existing log\n"}
            if agent_event == "serviceStatusList":
                return {"ok": True, "serviceStatusList": {"web": "running"}}
            if agent_event == "getDockerNetworkList":
                return {"ok": True, "dockerNetworkList": ["bridge"]}
            return {"ok": True, "msg": "OK"}
        raise AssertionError(event)


def client(fake):
    return DockgeClient("https://dockge.example.com", token="token", socket_factory=lambda: fake)


def test_login_returns_and_stores_token():
    fake = FakeSocket()
    c = DockgeClient("https://dockge.example.com", socket_factory=lambda: fake)
    res = c.login("admin", "pw")
    assert res["token"] == "jwt"
    assert c.token == "jwt"


def test_connect_marks_dockgectl_in_handshake_auth():
    fake = FakeSocket()
    c = client(fake)

    c.connect()

    assert fake.connection_auth == {"clientType": "dockgectl"}


def test_login_by_token_keeps_scalar_token_protocol():
    fake = FakeSocket()
    c = client(fake)

    c.login_by_token()

    assert ("loginByToken", ("token",), 20) in fake.calls


def test_login_raises_for_2fa_requirement():
    fake = FakeSocket()
    c = DockgeClient("https://dockge.example.com", socket_factory=lambda: fake)
    with pytest.raises(AuthError):
        c.login("2fa", "pw")


def test_list_stacks_waits_for_stacklist_push():
    fake = FakeSocket()
    c = client(fake)
    stacks = c.list_stacks(endpoint="")
    assert stacks["app"]["name"] == "app"
    assert stacks["app"]["status"] == 3


def test_read_only_agent_call_retries_explicit_not_ready_ack(monkeypatch):
    fake = FakeSocket()
    attempts = 0
    original_call = fake.call

    def flaky_call(event, data=(), timeout=20):
        nonlocal attempts
        if event == "agent" and data[1] == "requestStackList":
            attempts += 1
            if attempts == 1:
                return {"ok": False, "code": "AGENT_NOT_READY", "msg": "Agent bootstrap in progress"}
        return original_call(event, data, timeout)

    monkeypatch.setattr(fake, "call", flaky_call)
    monkeypatch.setattr("dockgectl.client.time.sleep", lambda _seconds: None)
    c = client(fake)
    stacks = c.list_stacks(endpoint="remote.example.com")

    assert attempts == 2
    assert stacks["app"]["endpoint"] == "remote.example.com"


def test_read_only_agent_call_does_not_retry_ambiguous_timeout(monkeypatch):
    fake = FakeSocket()
    attempts = 0
    original_call = fake.call

    def flaky_call(event, data=(), timeout=20):
        nonlocal attempts
        if event == "agent" and data[1] == "getStack":
            attempts += 1
            raise socketio.exceptions.TimeoutError()
        return original_call(event, data, timeout)

    monkeypatch.setattr(fake, "call", flaky_call)
    monkeypatch.setattr("dockgectl.client.time.sleep", lambda _seconds: None)
    c = client(fake)

    with pytest.raises(ApiError, match="Timed out waiting for Dockge event: agent"):
        c.get_stack("app", endpoint="remote.example.com")

    assert attempts == 1


@pytest.mark.parametrize(
    ("invoke", "agent_event"),
    [
        (lambda c: c.save_stack("app", "services: {}\n", "", False, endpoint="remote.example.com"), "saveStack"),
        (lambda c: c.deploy_stack("app", "services: {}\n", "", False, endpoint="remote.example.com"), "deployStack"),
        (lambda c: c.stack_action("start", "app", endpoint="remote.example.com"), "startStack"),
        (lambda c: c.stack_action("stop", "app", endpoint="remote.example.com"), "stopStack"),
        (lambda c: c.stack_action("restart", "app", endpoint="remote.example.com"), "restartStack"),
        (lambda c: c.stack_action("update", "app", endpoint="remote.example.com"), "updateStack"),
        (lambda c: c.stack_action("down", "app", endpoint="remote.example.com"), "downStack"),
        (lambda c: c.stack_action("delete", "app", endpoint="remote.example.com"), "deleteStack"),
        (lambda c: c.service_action("start", "app", "web", endpoint="remote.example.com"), "startService"),
        (lambda c: c.service_action("stop", "app", "web", endpoint="remote.example.com"), "stopService"),
        (lambda c: c.service_action("restart", "app", "web", endpoint="remote.example.com"), "restartService"),
    ],
)
def test_write_agent_calls_never_retry_not_ready_ack(monkeypatch, invoke, agent_event):
    fake = FakeSocket()
    attempts = 0
    original_call = fake.call

    def not_ready_call(event, data=(), timeout=20):
        nonlocal attempts
        if event == "agent" and data[1] == agent_event:
            attempts += 1
            return {"ok": False, "code": "AGENT_NOT_READY", "msg": "Agent bootstrap in progress"}
        return original_call(event, data, timeout)

    monkeypatch.setattr(fake, "call", not_ready_call)
    monkeypatch.setattr("dockgectl.client.time.sleep", lambda _seconds: None)
    c = client(fake)

    with pytest.raises(ApiError, match="AGENT_NOT_READY: Agent bootstrap in progress.*remote.example.com") as exc_info:
        invoke(c)

    assert exc_info.value.code == "AGENT_NOT_READY"
    assert exc_info.value.endpoint == "remote.example.com"
    assert attempts == 1


@pytest.mark.parametrize("code", ["AGENT_NOT_FOUND", "AGENT_AUTH_FAILED", "AGENT_PROXY_ERROR"])
def test_read_only_agent_call_does_not_retry_non_bootstrap_ack(monkeypatch, code):
    fake = FakeSocket()
    attempts = 0
    original_call = fake.call

    def failed_call(event, data=(), timeout=20):
        nonlocal attempts
        if event == "agent" and data[1] == "getStack":
            attempts += 1
            return {"ok": False, "code": code, "message": "proxy failed"}
        return original_call(event, data, timeout)

    monkeypatch.setattr(fake, "call", failed_call)
    monkeypatch.setattr("dockgectl.client.time.sleep", lambda _seconds: None)
    c = client(fake)

    with pytest.raises(ApiError, match=rf"{code}: proxy failed.*remote.example.com") as exc_info:
        c.get_stack("app", endpoint="remote.example.com")

    assert exc_info.value.code == code
    assert attempts == 1


def test_offline_target_fails_before_agent_event_is_sent():
    fake = FakeSocket()
    original_call = fake.call

    def offline_login(event, data=(), timeout=20):
        result = original_call(event, data, timeout)
        if event == "loginByToken":
            fake.handlers["agentStatus"]({"endpoint": "remote.example.com", "status": "offline", "msg": "connection failed"})
        return result

    fake.call = offline_login
    c = client(fake)

    with pytest.raises(ApiError, match="remote.example.com.*offline.*connection failed") as exc_info:
        c.get_stack("app", endpoint="remote.example.com")

    assert exc_info.value.code == "AGENT_OFFLINE"
    assert not any(call[0] == "agent" for call in fake.calls)


def test_unrelated_offline_agent_does_not_block_online_target():
    fake = FakeSocket()
    original_call = fake.call

    def mixed_status_login(event, data=(), timeout=20):
        result = original_call(event, data, timeout)
        if event == "loginByToken":
            fake.handlers["agentStatus"]({"endpoint": "us.example.com", "status": "offline"})
        return result

    fake.call = mixed_status_login
    c = client(fake)

    stack = c.get_stack("app", endpoint="remote.example.com")

    assert stack["name"] == "app"


def test_unknown_agent_endpoint_fails_without_sending_agent_event():
    fake = FakeSocket()
    c = client(fake)

    with pytest.raises(ApiError, match="not configured: missing.example.com") as exc_info:
        c.get_stack("app", endpoint="missing.example.com")

    assert exc_info.value.code == "AGENT_NOT_FOUND"
    assert not any(call[0] == "agent" for call in fake.calls)


@pytest.mark.parametrize("capability_source", ["info", "login"])
def test_lazy_server_allows_first_proxy_request_without_agent_status(capability_source):
    fake = FakeSocket(
        info_mode="lazy" if capability_source == "info" else None,
        login_mode="lazy" if capability_source == "login" else None,
        agent_status=None,
    )
    c = client(fake)

    stack = c.get_stack("app", endpoint="remote.example.com")

    assert stack["name"] == "app"
    assert any(call[0] == "agent" and call[1][1] == "getStack" for call in fake.calls)


def test_legacy_server_waits_when_agent_status_is_missing():
    fake = FakeSocket(agent_status=None)
    c = DockgeClient(
        "https://dockge.example.com",
        token="token",
        timeout=0.01,
        socket_factory=lambda: fake,
    )

    with pytest.raises(ApiError, match="did not become ready.*unknown") as exc_info:
        c.get_stack("app", endpoint="remote.example.com")

    assert exc_info.value.code == "AGENT_NOT_READY"
    assert not any(call[0] == "agent" for call in fake.calls)


def test_only_exact_lazy_capability_skips_missing_status_wait():
    fake = FakeSocket(info_mode="LAZY", agent_status=None)
    c = DockgeClient(
        "https://dockge.example.com",
        token="token",
        timeout=0.01,
        socket_factory=lambda: fake,
    )

    with pytest.raises(ApiError, match="did not become ready"):
        c.get_stack("app", endpoint="remote.example.com")

    assert not any(call[0] == "agent" for call in fake.calls)


def test_legacy_server_waits_briefly_while_agent_is_connecting():
    fake = FakeSocket(agent_status="connecting")
    c = DockgeClient(
        "https://dockge.example.com",
        token="token",
        timeout=0.01,
        socket_factory=lambda: fake,
    )

    with pytest.raises(ApiError, match="did not become ready.*connecting") as exc_info:
        c.get_stack("app", endpoint="remote.example.com")

    assert exc_info.value.code == "AGENT_NOT_READY"
    assert not any(call[0] == "agent" for call in fake.calls)


def test_disconnect_clears_authentication_and_agent_state_for_reuse():
    fake = FakeSocket()
    c = client(fake)
    c.get_stack("app", endpoint="remote.example.com")

    c.disconnect()

    assert c.logged_in is False
    assert c.agent_list is None
    assert c.agent_connection_mode is None
    assert c._agent_statuses == {}

    c.get_stack("app", endpoint="remote.example.com")
    token_logins = [call for call in fake.calls if call[0] == "loginByToken"]
    assert len(token_logins) == 2


def test_list_stacks_ignores_unrelated_stacklist_pushes():
    fake = FakeSocket()
    original_call = fake.call

    def noisy_call(event, data=(), timeout=20):
        if event == "agent" and data[1] == "requestStackList":
            fake.handlers["agent"]("stackList", {"ok": True, "endpoint": "other-1", "stackList": {}})
            fake.handlers["agent"]("stackList", {"ok": True, "endpoint": "other-2", "stackList": {}})
        return original_call(event, data, timeout)

    fake.call = noisy_call
    c = client(fake)
    stacks = c.list_stacks(endpoint="remote.example.com")

    assert stacks["app"]["endpoint"] == "remote.example.com"


def test_agent_helpers_extract_payloads():
    fake = FakeSocket()
    c = client(fake)
    assert c.get_stack("app")["name"] == "app"
    assert c.service_status("app") == {"web": "running"}
    assert c.docker_networks() == ["bridge"]


def test_list_agents_waits_for_agent_list_push():
    fake = FakeSocket()
    c = client(fake)
    agents = c.list_agents()
    assert agents["remote.example.com"]["name"] == "remote"


def test_stack_logs_joins_combined_terminal_for_endpoint():
    fake = FakeSocket()
    c = client(fake)
    chunks = list(c.stack_logs("app", endpoint="remote.example.com", wait=0))
    assert chunks == ["existing log\n"]
    assert ("agent", ("remote.example.com", "getStack", "app"), 20) in fake.calls
    assert ("agent", ("remote.example.com", "terminalJoin", "combined-remote.example.com-app"), 20) in fake.calls


def test_get_stack_not_found_raises_not_found():
    fake = FakeSocket()
    c = client(fake)
    with pytest.raises(NotFoundError):
        c.get_stack("missing")


def test_status_name_maps_known_values():
    assert status_name(3) == "running"
    assert status_name("x") == "x"
