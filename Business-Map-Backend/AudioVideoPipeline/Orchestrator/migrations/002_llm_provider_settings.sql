-- Set search_path to the configured Orchestrator database schema before applying.
ALTER TABLE user_llm_settings
    ADD COLUMN IF NOT EXISTS provider VARCHAR(32) NOT NULL DEFAULT 'openrouter';

ALTER TABLE user_llm_settings
    ADD COLUMN IF NOT EXISTS model VARCHAR(255);

ALTER TABLE user_llm_settings
    DROP COLUMN IF EXISTS secondary_api_key;
