from rule_u.config import Settings


def test_short_env_names_load_from_dotenv(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "CHAT_PROVIDER=compatible\nCHAT_API_KEY=test-chat-key\n"
        "EMBEDDING_PROVIDER=compatible\nEMBEDDING_MODEL=test-model\n"
        "EMBEDDING_API_KEY=test-embedding-key\nEMBEDDING_DIMENSIONS=16\n"
        "API_TIMEOUT_SECONDS=12\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=env)
    assert settings.chat_provider == "compatible"
    assert settings.chat_api_key.get_secret_value() == "test-chat-key"
    assert settings.embedding_provider == "compatible"
    assert settings.embedding_model == "test-model"
    assert settings.embedding_api_key.get_secret_value() == "test-embedding-key"
    assert settings.embedding_dimensions == 16
    assert settings.api_timeout_seconds == 12


def test_gms_key_alias(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GMS_KEY=test-gms-key\n", encoding="utf-8")
    assert Settings(_env_file=env).chat_api_key.get_secret_value() == "test-gms-key"
