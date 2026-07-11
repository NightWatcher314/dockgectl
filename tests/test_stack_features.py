import pytest

from dockgectl.commands.stack import _assert_env_persisted, _desired_env_text, _env_delta, _filter_logs, _stack_text
from dockgectl.errors import ApiError, NotFoundError


def test_env_delta_redacts_secret_like_values():
    delta = _env_delta("API_TOKEN=old\nMODE=dev\nOLD=yes\n", "API_TOKEN=new\nMODE=prod\nNEW=yes\n")
    assert delta["added"] == ["NEW"]
    assert delta["removed"] == ["OLD"]
    assert {item["key"] for item in delta["changed"]} == {"API_TOKEN", "MODE"}
    token_change = next(item for item in delta["changed"] if item["key"] == "API_TOKEN")
    assert token_change["current"] == "<redacted>"
    assert token_change["desired"] == "<redacted>"
    mode_change = next(item for item in delta["changed"] if item["key"] == "MODE")
    assert mode_change["current"] == "dev"
    assert mode_change["desired"] == "prod"


def test_filter_logs_tail_and_grep():
    text = "one\nkeep two\nthree\nkeep four\n"
    assert _filter_logs(text, tail=1, grep=None) == "keep four\n"
    assert _filter_logs(text, tail=None, grep="keep") == "keep two\nkeep four\n"
    assert _filter_logs(text, tail=1, grep="keep") == "keep four\n"


def test_stack_text_accepts_common_dockge_keys():
    assert _stack_text({"composeYAML": "a"}, ("composeYAML", "compose")) == "a"
    assert _stack_text({"compose": "b"}, ("composeYAML", "compose")) == "b"
    assert _stack_text({}, ("composeYAML", "compose")) == ""


class StackClient:
    def __init__(self, env):
        self.env = env

    def get_stack(self, name, endpoint=None):
        return {"name": name, "endpoint": endpoint or "", "composeENV": self.env}


def test_omitted_env_file_preserves_existing_stack_env():
    assert _desired_env_text(StackClient("KEEP=1\n"), "app", None, None) == "KEEP=1\n"


def test_explicit_empty_env_file_clears_existing_stack_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("")

    assert _desired_env_text(StackClient("KEEP=1\n"), "app", None, env_file) == ""


class MissingStackClient:
    def get_stack(self, name, endpoint=None):
        raise NotFoundError(name)


def test_omitted_env_file_for_new_stack_defaults_to_empty():
    assert _desired_env_text(MissingStackClient(), "new-app", None, None) == ""


def test_assert_env_persisted_passes_when_get_stack_matches():
    stack = _assert_env_persisted(StackClient("A=1\n"), "app", "A=1\n", None)

    assert stack["name"] == "app"


def test_assert_env_persisted_fails_when_get_stack_differs():
    with pytest.raises(ApiError, match="did not persist"):
        _assert_env_persisted(StackClient("OLD=1\n"), "app", "NEW=1\n", None)

from dockgectl.commands.service import _agent_endpoints as service_agent_endpoints
from dockgectl.commands.stack import _agent_endpoints as stack_agent_endpoints, _service_status_ok


class AgentClient:
    def list_agents(self):
        return {
            "": {"endpoint": None},
            "remote.example.com": {"endpoint": "remote.example.com"},
            "fallback.example.com": {},
        }


def test_agent_endpoints_normalize_none_and_missing_values():
    assert stack_agent_endpoints(AgentClient()) == ["", "fallback.example.com", "remote.example.com"]
    assert service_agent_endpoints(AgentClient()) == ["", "fallback.example.com", "remote.example.com"]


def test_service_status_ok_handles_strings_and_dicts():
    assert _service_status_ok({"web": "running"}) is True
    assert _service_status_ok({"web": {"status": "running"}}) is True
    assert _service_status_ok({"web": {"status": "healthy"}}) is True
    assert _service_status_ok({"web": [{"name": "web", "status": "healthy"}]}) is True
    assert _service_status_ok({"web": [{"name": "web", "Status": "running"}], "worker": [{"state": "started"}]}) is True
    assert _service_status_ok({"web": "exited"}) is False
    assert _service_status_ok({"web": [{"name": "web", "status": "unhealthy"}]}) is False
    assert _service_status_ok({"web": []}) is False
    assert _service_status_ok({}) is False
