from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_cover_resolver_never_downloads_remote_images():
    source = (ROOT / "includes" / "image.php").read_text(encoding="utf-8")
    config = (ROOT / "config" / "config-example.php").read_text(encoding="utf-8")

    assert "file_get_contents(" not in source
    assert "cache_cover(" not in source
    assert "api.bgm.tv" not in source
    assert "api_url" not in config
    assert "no_icon_url" not in config
    assert "'placeholder' => 'logo.png'" in config
    assert "app_config()['covers']" in source
    assert "rawurlencode($placeholder)" in source
    assert "static/img/placeholder.svg" in source


def test_login_redirects_are_relative_and_validated():
    auth = (ROOT / "includes" / "auth.php").read_text(encoding="utf-8")
    login = (ROOT / "login.php").read_text(encoding="utf-8")

    assert "auth_safe_target" in auth
    assert "auth_current_target" in auth
    assert "auth_safe_target" in login
    assert "str_starts_with($next, '/')" not in login
    assert "header('Location: ./')" in login
