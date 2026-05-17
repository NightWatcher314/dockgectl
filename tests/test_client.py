import pytest

from dockgectl.client import DockgeClient, status_name
from dockgectl.errors import AuthError, NotFoundError


class FakeSocket:
    def __init__(self):
        self.handlers = {}
        self.connected = False
        self.calls = []

    def on(self, event, handler):
        self.handlers[event] = handler

    def connect(self, _url, wait_timeout=20):
        self.connected = True
        self.handlers["info"]({"version": "1.5.0"})

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
            return {"ok": True, "token": "jwt"}
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
            return {"ok": True}
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
