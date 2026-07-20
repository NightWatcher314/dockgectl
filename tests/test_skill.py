from pathlib import Path

import yaml


def test_skill_frontmatter_and_executor_guidance():
    text = Path("skills/dockge/SKILL.md").read_text()
    assert text.startswith("---\n")
    _start, frontmatter, body = text.split("---", 2)
    data = yaml.safe_load(frontmatter)
    assert data["name"] == "dockge"
    assert "Dockge" in data["description"]
    assert "uv run dockgectl" in body
    assert "Destructive or disruptive actions" in body
    assert "dockgectl stack list -o json" in body
    assert "composeENV" in body
    assert "Compose field allowlist" in body
    assert "stack logs --tail" in body
