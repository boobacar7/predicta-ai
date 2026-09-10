from pathlib import Path

from tests.conftest import TEST_SPORTMONKS_TOKEN

from predicta_ingestion.secrets import redact_text, redact_url


def test_fixtures_and_examples_contain_no_live_secrets() -> None:
    root = Path(__file__).resolve().parents[1]
    scanned = list((root / "fixtures").rglob("*"))
    scanned.extend((root / "src").rglob("*.py"))
    scanned.extend((root / "tests").rglob("*.py"))
    scanned.append(root / ".env.example")
    for path in scanned:
        if not path.is_file() or path.suffix in {".pyc", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        if path.name == ".env.example":
            assert "SPORTMONKS_API_TOKEN=" in text
            assert not any(
                line.startswith("SPORTMONKS_API_TOKEN=") and line.strip() != "SPORTMONKS_API_TOKEN="
                for line in text.splitlines()
            )
            continue
        if "tests" in path.parts:
            continue
        assert TEST_SPORTMONKS_TOKEN not in text
        assert "sk_live" not in text
        if path.suffix == ".json":
            assert "api_token=" not in text.lower()


def test_redact_strips_token_from_urls_and_errors() -> None:
    url = f"https://api.sportmonks.com/v3/football/leagues/8?api_token={TEST_SPORTMONKS_TOKEN}"
    redacted = redact_url(url, TEST_SPORTMONKS_TOKEN)
    assert TEST_SPORTMONKS_TOKEN not in redacted
    assert "api_token=[redacted]" in redacted
    message = redact_text(f"Authorization: {TEST_SPORTMONKS_TOKEN} failed", TEST_SPORTMONKS_TOKEN)
    assert TEST_SPORTMONKS_TOKEN not in message
