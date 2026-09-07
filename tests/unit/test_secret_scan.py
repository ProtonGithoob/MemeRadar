import subprocess

from scripts.secret_scan import scan_artifacts, scan_git_history, scan_text


def test_secret_scan_accepts_safe_placeholders_and_local_dev_values():
    text = """
    API_KEY=
    TELEGRAM_BOT_TOKEN=replace-me
    POSTGRES_PASSWORD=memeradar_local_only
    """

    assert scan_text(text) == []


def test_secret_scan_rejects_private_key_material():
    text = "-----BEGIN " + "PRIVATE KEY-----\nnot-a-real-key\n-----END PRIVATE KEY-----"

    findings = scan_text(text)

    assert findings
    assert findings[0].rule == "private_key_block"


def test_secret_scan_rejects_release_artifact_material(tmp_path):
    artifact = tmp_path / "dist" / "bundle.js"
    artifact.parent.mkdir()
    artifact.write_text("const token = 'ghp_" + "A" * 30 + "';", encoding="utf-8")

    findings = scan_artifacts(tmp_path)

    assert findings
    assert findings[0][1].rule == "github_token"


def test_secret_scan_rejects_reachable_git_history_material(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Secret Scan Test"],
        check=True,
    )
    (tmp_path / "old-config.txt").write_text("AKIA" + "A" * 16, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "old-config.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "old config"], check=True)

    findings = scan_git_history(tmp_path)

    assert findings
    assert findings[0][1].rule == "aws_access_key"
