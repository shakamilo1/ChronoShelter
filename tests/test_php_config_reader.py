from tools.php_config_reader import database_config, read_php_config


def test_php_config_reader_reads_shared_php_config():
    config = read_php_config()
    assert config["db"]["public_database"] == "chrono_bangumi"
    assert config["db"]["library_database"] == "chrono_library"


def test_database_config_uses_php_config_database_names():
    assert database_config("public")["database"] == "chrono_bangumi"
    assert database_config("library")["database"] == "chrono_library"
