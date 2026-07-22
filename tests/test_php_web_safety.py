from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_cover_resolver_never_downloads_remote_images():
    source = (ROOT / "includes" / "image.php").read_text(encoding="utf-8")
    config = (ROOT / "config" / "config-example.php").read_text(encoding="utf-8")

    assert "file_get_contents(" not in source
    assert "foreach (['jpg', 'png', 'webp']" not in source
    assert "cache_cover(" not in source
    assert "api.bgm.tv" not in source
    assert "api_url" not in config
    assert "no_icon_url" not in config
    assert "'fallback' => 'logo.png'" in config
    assert "'subjects_directory' => 'subjects'" in config
    assert "app_config()['covers']" in source
    assert "rawurlencode($fallback)" in source
    assert "static/img/placeholder.svg" in source


def test_login_redirects_are_relative_and_validated():
    auth = (ROOT / "includes" / "auth.php").read_text(encoding="utf-8")
    login = (ROOT / "login.php").read_text(encoding="utf-8")

    assert "auth_safe_target" in auth
    assert "auth_current_target" in auth
    assert "auth_safe_target" in login
    assert "str_starts_with($next, '/')" not in login
    assert "header('Location: ./')" in login


def test_cover_cli_uses_anime_bulk_api_and_custom_user_agent_only():
    cli = (ROOT / "bin" / "bangumi_covers.php").read_text(encoding="utf-8")

    assert "SUBJECT_TYPE_ANIME = 2" in cli
    assert "PAGE_LIMIT = 100" in cli
    assert "type=' . SUBJECT_TYPE_ANIME" in cli
    assert "images']['large" in cli
    assert "images']['common" not in cli
    assert "/v0/subjects/{id}" not in cli
    assert "/image" not in cli
    assert "shakamilo1/chronoshelter-cover-archive/1.0" in cli
    assert "BANGUMI_ACCESS_TOKEN" in cli


def test_cover_partition_paths_are_documented_and_safe():
    cli = (ROOT / "bin" / "bangumi_covers.php").read_text(encoding="utf-8")
    image = (ROOT / "includes" / "image.php").read_text(encoding="utf-8")

    assert "intdiv($subjectId, 1000000)" in cli
    assert "intdiv($subjectId % 1000000, 1000)" in cli
    assert "subjects/000/491/491569_xxxxx.jpg" in (ROOT / "docs" / "bangumi_cover_sync.md").read_text(encoding="utf-8")
    assert "cover_safe_relative_path" in image
    assert "cover_partition_prefix" in image
    assert "api.bgm.tv" not in image
    assert "lain.bgm.tv" not in image


def test_all_cover_url_calls_pass_database_local_path():
    for relative in ["index.php", "collection.php", "subject.php"]:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "cover_url(" in source
        assert "cover_local_path" in source
    assert "cover_url($id)" not in (ROOT / "subject.php").read_text(encoding="utf-8")


def test_install_check_requires_cover_cache_mapping_columns():
    install = (ROOT / "includes" / "install.php").read_text(encoding="utf-8")
    check = (ROOT / "install_check.php").read_text(encoding="utf-8")

    assert "required_columns" in install
    assert "remote_filename" in install
    assert "source_url" in install
    assert "sha256" in install
    assert "column_exists" in check
