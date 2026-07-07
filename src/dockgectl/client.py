from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable

import socketio

from .errors import ApiError, AuthError, ConfigError, NotFoundError

STATUS_NAMES = {
    0: "unknown",
    1: "draft",
    2: "created_stack",
    3: "running",
    4: "exited",
}


class DockgeClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        verify_tls: bool = True,
        endpoint: str = "",
        timeout: float = 20,
        socket_factory: Callable[[], Any] | None = None,
    ):
        if not base_url:
            raise ConfigError("Dockge URL is not configured. Run: dockgectl config set-url URL")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify_tls = verify_tls
        self.endpoint = endpoint or ""
        self.timeout = timeout
        self.socket_factory = socket_factory
        self.sio: Any | None = None
        self.connected = False
        self.logged_in = False
        self.info: dict[str, Any] | None = None
        self.need_setup = False
        self.agent_list: dict[str, Any] | None = None
        self._info_event = threading.Event()
        self._auto_login = threading.Event()
        self._agent_list_event = threading.Event()
        self._stack_lists: queue.Queue[dict[str, Any]] = queue.Queue()
        self._terminal_writes: queue.Queue[tuple[str, str]] = queue.Queue()

    def _new_socket(self) -> Any:
        if self.socket_factory:
            return self.socket_factory()
        return socketio.Client(
            logger=False,
            engineio_logger=False,
            reconnection=False,
            ssl_verify=self.verify_tls,
            request_timeout=self.timeout,
        )

    def connect(self) -> None:
        if self.connected:
            return
        self.sio = self._new_socket()
        self.sio.on("info", self._on_info)
        self.sio.on("setup", self._on_setup)
        self.sio.on("autoLogin", self._on_auto_login)
        self.sio.on("agent", self._on_agent)
        self.sio.on("agentList", self._on_agent_list)
        try:
            self.sio.connect(self.base_url, wait_timeout=self.timeout)
        except Exception as exc:  # pragma: no cover - exact exception type depends on transport
            raise ApiError(f"Unable to connect to Dockge at {self.base_url}: {exc}") from exc
        self.connected = True

    def disconnect(self) -> None:
        if self.sio and self.connected:
            self.sio.disconnect()
        self.connected = False

    def _on_info(self, data: dict[str, Any]) -> None:
        self.info = data
        self._info_event.set()

    def _on_setup(self, *_args: Any) -> None:
        self.need_setup = True

    def _on_auto_login(self, *_args: Any) -> None:
        self.logged_in = True
        self._auto_login.set()

    def _on_agent(self, event_name: str, *args: Any) -> None:
        if event_name == "stackList" and args and isinstance(args[0], dict):
            self._stack_lists.put(args[0])
        if event_name == "terminalWrite" and len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], str):
            self._terminal_writes.put((args[0], args[1]))

    def _on_agent_list(self, data: dict[str, Any]) -> None:
        if data.get("ok"):
            self.agent_list = data.get("agentList") or {}
            self._agent_list_event.set()

    def _call(self, event: str, *args: Any, timeout: float | None = None) -> Any:
        self.connect()
        try:
            return self.sio.call(event, data=args, timeout=timeout or self.timeout)
        except socketio.exceptions.TimeoutError as exc:
            raise ApiError(f"Timed out waiting for Dockge event: {event}") from exc
        except Exception as exc:  # pragma: no cover - transport-specific
            raise ApiError(f"Dockge event failed: {event}: {exc}") from exc

    @staticmethod
    def _require_ok(res: Any) -> Any:
        if isinstance(res, dict) and res.get("ok") is False:
            msg = res.get("msg") or res.get("message") or "Dockge returned ok=false"
            if "not found" in str(msg).lower():
                raise NotFoundError(str(msg))
            raise ApiError(str(msg))
        return res

    def login(self, username: str, password: str, token: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"username": username, "password": password}
        if token:
            payload["token"] = token
        res = self._call("login", payload)
        if isinstance(res, dict) and res.get("tokenRequired"):
            raise AuthError("2FA token required. Re-run with: dockgectl auth login --totp CODE")
        self._require_ok(res)
        if not isinstance(res, dict) or not res.get("token"):
            raise AuthError("Login succeeded but Dockge did not return a token")
        self.token = res["token"]
        self.logged_in = True
        return res

    def login_by_token(self, token: str | None = None) -> dict[str, Any]:
        token = token or self.token
        if not token:
            raise AuthError("No token configured. Run: dockgectl auth login")
        res = self._call("loginByToken", token)
        self._require_ok(res)
        self.logged_in = True
        return res

    def ensure_authenticated(self) -> None:
        self.connect()
        if self.logged_in:
            return
        if self._auto_login.wait(0.2):
            return
        self.login_by_token(self.token)

    def wait_for_info(self, timeout: float = 1) -> dict[str, Any] | None:
        self.connect()
        self._info_event.wait(timeout)
        return self.info

    def get_settings(self) -> dict[str, Any]:
        self.ensure_authenticated()
        res = self._require_ok(self._call("getSettings"))
        return res.get("data", {}) if isinstance(res, dict) else {}

    def composerize(self, docker_run_command: str) -> str:
        self.ensure_authenticated()
        res = self._require_ok(self._call("composerize", docker_run_command))
        return res.get("composeTemplate", "") if isinstance(res, dict) else ""

    def list_agents(self) -> dict[str, Any]:
        self.ensure_authenticated()
        if self.agent_list is None:
            self._agent_list_event.wait(self.timeout)
        if self.agent_list is None:
            raise ApiError("Timed out waiting for Dockge agentList")
        return self.agent_list

    def agent_call(self, event: str, *args: Any, endpoint: str | None = None, timeout: float | None = None) -> Any:
        self.ensure_authenticated()
        return self._require_ok(self._call("agent", self.endpoint if endpoint is None else endpoint, event, *args, timeout=timeout))

    def list_stacks(self, endpoint: str | None = None) -> dict[str, Any]:
        wanted = self.endpoint if endpoint is None else endpoint
        while not self._stack_lists.empty():
            self._stack_lists.get_nowait()

        last_error: ApiError | None = None
        for attempt in range(2):
            try:
                self.agent_call("requestStackList", endpoint=wanted)
                last_error = None
                break
            except ApiError as exc:
                last_error = exc
                if attempt == 0 and "Timed out waiting for Dockge event: agent" in str(exc):
                    while not self._stack_lists.empty():
                        self._stack_lists.get_nowait()
                    time.sleep(3)
                    continue
                raise
        if last_error is not None:
            raise last_error

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                payload = self._stack_lists.get(timeout=max(0.0, min(0.5, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if payload.get("endpoint", "") == wanted:
                return payload.get("stackList") or {}
        raise ApiError("Timed out waiting for Dockge stackList push")

    def get_stack(self, name: str, endpoint: str | None = None) -> dict[str, Any]:
        res = self.agent_call("getStack", name, endpoint=endpoint)
        return res.get("stack", {}) if isinstance(res, dict) else {}

    def stack_logs(self, name: str, endpoint: str | None = None, follow: bool = False, wait: float = 2.0):
        wanted = self.endpoint if endpoint is None else endpoint
        terminal_name = combined_terminal_name(wanted, name)
        while not self._terminal_writes.empty():
            self._terminal_writes.get_nowait()
        self.get_stack(name, endpoint=wanted)
        res = self.agent_call("terminalJoin", terminal_name, endpoint=wanted)
        buffer = res.get("buffer", "") if isinstance(res, dict) else ""
        if buffer:
            yield buffer
        deadline = time.monotonic() + wait
        while follow or time.monotonic() < deadline:
            timeout = 0.5 if follow else max(0.0, min(0.5, deadline - time.monotonic()))
            if timeout == 0:
                break
            try:
                received_name, data = self._terminal_writes.get(timeout=timeout)
            except queue.Empty:
                continue
            if received_name == terminal_name:
                yield data

    def save_stack(self, name: str, compose_yaml: str, compose_env: str, is_add: bool, endpoint: str | None = None) -> Any:
        return self.agent_call("saveStack", name, compose_yaml, compose_env, is_add, endpoint=endpoint, timeout=max(self.timeout, 60))

    def deploy_stack(self, name: str, compose_yaml: str, compose_env: str, is_add: bool, endpoint: str | None = None) -> Any:
        return self.agent_call("deployStack", name, compose_yaml, compose_env, is_add, endpoint=endpoint, timeout=max(self.timeout, 120))

    def stack_action(self, action: str, name: str, endpoint: str | None = None) -> Any:
        event = {
            "start": "startStack",
            "stop": "stopStack",
            "restart": "restartStack",
            "update": "updateStack",
            "down": "downStack",
            "delete": "deleteStack",
        }[action]
        return self.agent_call(event, name, endpoint=endpoint, timeout=max(self.timeout, 60))

    def service_status(self, stack: str, endpoint: str | None = None) -> dict[str, Any]:
        res = self.agent_call("serviceStatusList", stack, endpoint=endpoint)
        return res.get("serviceStatusList", {}) if isinstance(res, dict) else {}

    def service_action(self, action: str, stack: str, service: str, endpoint: str | None = None) -> Any:
        event = {
            "start": "startService",
            "stop": "stopService",
            "restart": "restartService",
        }[action]
        return self.agent_call(event, stack, service, endpoint=endpoint, timeout=max(self.timeout, 60))

    def docker_networks(self, endpoint: str | None = None) -> list[str]:
        res = self.agent_call("getDockerNetworkList", endpoint=endpoint)
        return res.get("dockerNetworkList", []) if isinstance(res, dict) else []


def status_name(value: Any) -> str:
    try:
        return STATUS_NAMES.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


def combined_terminal_name(endpoint: str, stack: str) -> str:
    return f"combined-{endpoint}-{stack}"
