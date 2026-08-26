from scripts.secret_scan import scan_text


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
