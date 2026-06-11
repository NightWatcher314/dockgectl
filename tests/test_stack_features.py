from dockgectl.commands.stack import _env_delta, _filter_logs, _stack_text


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
    assert _service_status_ok({"web": "exited"}) is False
    assert _service_status_ok({}) is False
