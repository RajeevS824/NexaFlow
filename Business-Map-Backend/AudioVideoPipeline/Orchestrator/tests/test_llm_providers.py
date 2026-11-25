import asyncio
import os

import pytest

# Prevent module-level clients and dotenv loading from seeing real credentials.
_key_environment = (
    "PROCESSIQ_LLM_PRIMARY_API_KEY",
    "PRIMARY_LLM_API_KEY",
    "OPENROUTER_API_KEY",
    "SECONDARY_LLM_API_KEY",
    "PROCESSIQ_LLM_ENCRYPTION_KEY",
    "LLM_CONFIG_ENCRYPTION_KEY",
)
_saved_environment = {name: os.environ.get(name) for name in _key_environment}
for _name in _key_environment:
    os.environ[_name] = ""

import database
import integrated_pipeline
import job_manager

for _name, _value in _saved_environment.items():
    if _value is None:
        os.environ.pop(_name, None)
    else:
        os.environ[_name] = _value
del _name, _value, _saved_environment, _key_environment


class MockResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


@pytest.mark.parametrize(
    ("provider_id", "expected_url"),
    [
        ("openai", "https://api.openai.com/v1/chat/completions"),
        ("openrouter", "https://openrouter.ai/api/v1/chat/completions"),
        ("groq", "https://api.groq.com/openai/v1/chat/completions"),
        ("mistral", "https://api.mistral.ai/v1/chat/completions"),
        ("deepseek", "https://api.deepseek.com/chat/completions"),
        ("xai", "https://api.x.ai/v1/chat/completions"),
    ],
)
def test_openai_compatible_provider_request(monkeypatch, provider_id, expected_url):
    seen = {}

    def mock_post(**kwargs):
        seen.update(kwargs)
        return MockResponse(
            {"choices": [{"message": {"content": "provider result"}}]}
        )

    monkeypatch.setattr(job_manager.requests, "post", mock_post)
    client = job_manager.LLMClient(
        {"llm": {"retry": {"max_attempts": 1}}},
        {
            "provider": provider_id,
            "model": "test-model",
            "primary_api_key": "test-api-key",
        },
    )

    result = client.call("system prompt", "user prompt")

    assert result == "provider result"
    assert seen["url"] == expected_url
    assert seen["headers"]["Authorization"] == "Bearer test-api-key"
    assert seen["json"] == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
    }


def test_anthropic_uses_messages_protocol(monkeypatch):
    seen = {}

    def mock_post(**kwargs):
        seen.update(kwargs)
        return MockResponse(
            {"content": [
                {"type": "text", "text": "first "},
                {"type": "text", "text": "second"},
            ]}
        )

    monkeypatch.setattr(job_manager.requests, "post", mock_post)
    client = job_manager.LLMClient(
        {"llm": {"retry": {"max_attempts": 1}}},
        {
            "provider": "anthropic",
            "model": "claude-test",
            "primary_api_key": "test-api-key",
        },
    )

    assert client.call("system prompt", "user prompt") == "first second"
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "test-api-key"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["json"]["system"] == "system prompt"
    assert seen["json"]["messages"] == [
        {"role": "user", "content": "user prompt"}
    ]


def test_gemini_uses_generate_content_protocol(monkeypatch):
    seen = {}

    def mock_post(**kwargs):
        seen.update(kwargs)
        return MockResponse(
            {"candidates": [{
                "content": {"parts": [{"text": "Gemini "}, {"text": "result"}]}
            }]}
        )

    monkeypatch.setattr(job_manager.requests, "post", mock_post)
    client = job_manager.LLMClient(
        {"llm": {"retry": {"max_attempts": 1}}},
        {
            "provider": "gemini",
            "model": "gemini-test",
            "primary_api_key": "test-api-key",
        },
    )

    assert client.call("system prompt", "user prompt") == "Gemini result"
    assert (
        seen["url"]
        == "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-test:generateContent"
    )
    assert seen["headers"]["x-goog-api-key"] == "test-api-key"
    assert seen["json"]["systemInstruction"] == {
        "parts": [{"text": "system prompt"}]
    }
    assert seen["json"]["contents"] == [{
        "role": "user",
        "parts": [{"text": "user prompt"}],
    }]


def test_model_refresh_uses_fixed_provider_catalog_endpoint(monkeypatch):
    seen = {}

    def mock_get(**kwargs):
        seen.update(kwargs)
        return MockResponse({"data": [{"id": "test-model"}]})

    monkeypatch.setattr(job_manager.requests, "get", mock_get)

    models = job_manager.fetch_provider_models("groq", "test-api-key")

    assert seen["url"] == "https://api.groq.com/openai/v1/models"
    assert seen["headers"]["Authorization"] == "Bearer test-api-key"
    assert models == [{"id": "test-model", "name": "test-model"}]


def test_model_refresh_rejects_unlisted_provider_without_request(monkeypatch):
    def unexpected_get(**kwargs):
        raise AssertionError("an unsupported provider must not make a request")

    monkeypatch.setattr(job_manager.requests, "get", unexpected_get)

    with pytest.raises(ValueError, match="Unsupported"):
        job_manager.fetch_provider_models("https://example.test", "test-api-key")


def test_refresh_route_uses_verified_user_and_does_not_return_key(monkeypatch):
    observed = {}
    monkeypatch.setattr(integrated_pipeline.database, "DB_ENABLED", True)

    def get_settings(user_id):
        observed["user_id"] = user_id
        return None

    def fetch_models(provider_id, api_key):
        observed["provider"] = provider_id
        observed["api_key"] = api_key
        return [{"id": "test-model", "name": "Test Model"}]

    monkeypatch.setattr(
        integrated_pipeline.database, "get_llm_settings", get_settings
    )
    monkeypatch.setattr(integrated_pipeline, "fetch_provider_models", fetch_models)

    response = asyncio.run(
        integrated_pipeline.refresh_llm_models(
            {"provider": "groq", "api_key": "test-only-key"},
            user_id=82,
        )
    )

    assert observed == {
        "user_id": 82,
        "provider": "groq",
        "api_key": "test-only-key",
    }
    assert response == {
        "provider": "groq",
        "models": [{"id": "test-model", "name": "Test Model"}],
    }
    assert "api_key" not in response


def test_gemini_model_catalog_filters_generation_models(monkeypatch):
    seen = {}

    def mock_get(**kwargs):
        seen.update(kwargs)
        return MockResponse({
            "models": [
                {
                    "name": "models/gemini-test",
                    "displayName": "Gemini Test",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/embed-test",
                    "displayName": "Embed Test",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        })

    monkeypatch.setattr(job_manager.requests, "get", mock_get)

    models = job_manager.fetch_provider_models("gemini", "test-api-key")

    assert seen["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models"
    )
    assert seen["headers"]["x-goog-api-key"] == "test-api-key"
    assert models == [{"id": "gemini-test", "name": "Gemini Test"}]


def test_anthropic_model_catalog_uses_anthropic_headers(monkeypatch):
    seen = {}

    def mock_get(**kwargs):
        seen.update(kwargs)
        return MockResponse({"data": [{"id": "claude-test"}]})

    monkeypatch.setattr(job_manager.requests, "get", mock_get)

    models = job_manager.fetch_provider_models("anthropic", "test-api-key")

    assert seen["url"] == "https://api.anthropic.com/v1/models"
    assert seen["headers"]["x-api-key"] == "test-api-key"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert models == [{"id": "claude-test", "name": "claude-test"}]


def test_application_key_prefers_processiq_environment(monkeypatch):
    monkeypatch.setenv("PROCESSIQ_LLM_PRIMARY_API_KEY", "preferred-test-key")
    monkeypatch.setenv("PRIMARY_LLM_API_KEY", "legacy-test-key")

    assert job_manager.get_application_llm_api_key() == "preferred-test-key"


def test_default_client_remains_openrouter(monkeypatch):
    assert job_manager._llm_client._providers == []
    monkeypatch.setenv("PROCESSIQ_LLM_PRIMARY_API_KEY", "application-test-key")
    client = job_manager.LLMClient(
        {"llm": {"primary": {"model": "default-model"}}}
    )

    assert len(client._providers) == 1
    assert client._providers[0]["provider"] == "openrouter"
    assert client._providers[0]["base_url"] == "https://openrouter.ai/api/v1"
    assert client._providers[0]["api_key"] == "application-test-key"


def test_encryption_prefers_processiq_key(monkeypatch):
    from cryptography.fernet import Fernet, InvalidToken

    processiq_key = Fernet.generate_key()
    legacy_key = Fernet.generate_key()
    monkeypatch.setattr(database, "_fernet", None)
    monkeypatch.setattr(database, "_fernet_warned", False)
    monkeypatch.setenv("PROCESSIQ_LLM_ENCRYPTION_KEY", processiq_key.decode())
    monkeypatch.setenv("LLM_CONFIG_ENCRYPTION_KEY", legacy_key.decode())

    cipher = database._get_fernet()
    encrypted = cipher.encrypt(b"test-only-secret")
    assert Fernet(processiq_key).decrypt(encrypted) == b"test-only-secret"
    with pytest.raises(InvalidToken):
        Fernet(legacy_key).decrypt(encrypted)


def test_encryption_accepts_legacy_key_when_new_key_is_unset(monkeypatch):
    from cryptography.fernet import Fernet

    legacy_key = Fernet.generate_key()
    monkeypatch.setattr(database, "_fernet", None)
    monkeypatch.setattr(database, "_fernet_warned", False)
    monkeypatch.delenv("PROCESSIQ_LLM_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("LLM_CONFIG_ENCRYPTION_KEY", legacy_key.decode())

    cipher = database._get_fernet()

    assert Fernet(legacy_key).decrypt(
        cipher.encrypt(b"test-only-secret")
    ) == b"test-only-secret"


def test_llm_settings_response_masks_the_user_key(monkeypatch):
    secret = "test-only-user-key-123456"
    monkeypatch.setattr(
        database,
        "get_llm_settings",
        lambda user_id: {
            "use_custom_key": True,
            "provider": "anthropic",
            "model": "claude-test",
            "primary_api_key": secret,
        },
    )
    monkeypatch.setattr(database, "llm_encryption_available", lambda: True)

    response = database.llm_config_response(74)

    assert response["provider"] == "anthropic"
    assert response["model"] == "claude-test"
    assert response["primary_key_configured"] is True
    assert response["primary_key_masked"] != secret
    assert secret not in repr(response)
    assert response["user_id"] == 74
