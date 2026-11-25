-- ============================================================================
-- NOTE: The `users` table has been REMOVED. The Document Parser is invoked
-- from the NexaFlow workspace, where the logged-in user is authenticated by
-- the NexaFlow RBAC backend. The NexaFlow user id (INT) is passed to the
-- Document Parser API and stored as a process global (see
-- app/core/global_state.py). All user-scoped columns use INT to match the
-- NexaFlow `[User].UserID` type, and there are NO foreign keys to a users
-- table (the FK lives in the NexaFlow database).
-- ============================================================================

-- ============================================================================
-- 1. SETTINGS CONFIG (per-user logging / output settings)
-- ============================================================================
-- NOTE: The trigger trg_CreateDefaultSettingConfig has been REMOVED. Default
-- SettingConfig rows are instead inserted by the application layer
-- (SettingRepository.get_or_create) the first time a user's settings are
-- accessed, so the user can edit them later.
CREATE TABLE dbo.SettingConfig
(
    setting_id UNIQUEIDENTIFIER NOT NULL
        DEFAULT NEWID(),

    user_id INT NOT NULL,

    log_path NVARCHAR(500) NOT NULL
        DEFAULT N'C:\Program Files\ONG\logs',

    log_type NVARCHAR(20) NOT NULL
        DEFAULT N'INFO',

    checked BIT NOT NULL
        DEFAULT (0),

    file_max_size_mb INT NOT NULL
        DEFAULT (50),

    OutputBasePath NVARCHAR(500) NOT NULL
        DEFAULT N'C:\Users',

    created_at DATETIME2 NOT NULL
        DEFAULT SYSUTCDATETIME(),

    updated_at DATETIME2 NULL,

    CONSTRAINT PK_SettingConfig
        PRIMARY KEY (setting_id),

    CONSTRAINT UQ_SettingConfig_User
        UNIQUE (user_id),

    -- Validation
    CONSTRAINT CK_SettingConfig_Checked
    CHECK
    (
        (UPPER(log_type) = 'INFO' AND checked IN (0,1))
        OR
        (UPPER(log_type) IN ('DEBUG','ERROR') AND checked = 1)
    )
);
GO

-- ============================================================================
-- 2. EXTRACTION MODELS (the reusable template a user builds)
-- ============================================================================
CREATE TABLE extraction_models (
    model_id        UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    userid          INT NOT NULL,
    model_name      NVARCHAR(255) NOT NULL,
    description     NVARCHAR(1000) NULL,

    engine_type     VARCHAR(10) NOT NULL DEFAULT 'OCR'
                       CONSTRAINT ck_models_engine_type CHECK (engine_type IN ('OCR','LLM')),
    document_type   VARCHAR(20) NOT NULL DEFAULT 'invoice'
                       CONSTRAINT ck_models_document_type CHECK (document_type IN ('invoice','receipt','contract','other')),
    language        VARCHAR(10) NOT NULL DEFAULT 'en'
                       CONSTRAINT ck_models_language CHECK (language IN ('en','es','fr','de','zh','ja','ko','it','hi')),

    is_active       BIT NOT NULL DEFAULT 1,

    created_at      DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at      DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),

CONSTRAINT uq_models_userid_name UNIQUE (userid, model_name)
);
GO
CREATE INDEX idx_models_userid ON extraction_models(userid);
GO

-- ============================================================================
-- 3. MODEL FORM FIELDS (one row per configured field, e.g. Invoice Number)
-- ============================================================================
CREATE TABLE model_label_definitions (
    label_def_id     UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    model_id         UNIQUEIDENTIFIER NOT NULL,
    field_name       NVARCHAR(255) NOT NULL,
    field_label      NVARCHAR(255) NOT NULL,
    is_required      BIT NOT NULL DEFAULT 1,
    data_type        VARCHAR(50) NOT NULL DEFAULT 'string',
    ai_skill         BIT NOT NULL DEFAULT 0,
    ai_prompt        NVARCHAR(MAX) NULL,
    CONSTRAINT fk_label_defs_model FOREIGN KEY (model_id) REFERENCES extraction_models(model_id) ON DELETE CASCADE,
    CONSTRAINT uq_label_defs_model_name UNIQUE (model_id, field_name),
    CONSTRAINT ck_label_ai_prompt_required CHECK (ai_skill = 0 OR (ai_skill = 1 AND ai_prompt IS NOT NULL AND LEN(ai_prompt) > 0))
);
GO
CREATE INDEX idx_label_defs_model_id ON model_label_definitions(model_id);
GO

CREATE TABLE model_label_aliases (
    alias_id         UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    label_def_id     UNIQUEIDENTIFIER NOT NULL,
    alias_text       NVARCHAR(255) NULL,
    CONSTRAINT fk_label_aliases_def FOREIGN KEY (label_def_id) REFERENCES model_label_definitions(label_def_id) ON DELETE CASCADE,
    CONSTRAINT uq_label_aliases UNIQUE (label_def_id, alias_text)
);
GO
CREATE INDEX idx_label_aliases_label_def_id ON model_label_aliases(label_def_id);
GO

-- ============================================================================
-- 4. MODEL TABLE DEFINITIONS (the model's tables list, each with headers)
-- ============================================================================
CREATE TABLE model_table_definitions (
    table_def_id     UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    model_id         UNIQUEIDENTIFIER NOT NULL,
    table_name       NVARCHAR(255) NOT NULL,
    is_enabled       BIT NOT NULL DEFAULT 1,
    min_confidence   NUMERIC(4,3) NOT NULL DEFAULT 0.750
                        CONSTRAINT ck_table_defs_conf CHECK (min_confidence BETWEEN 0 AND 1),
    CONSTRAINT fk_table_defs_model FOREIGN KEY (model_id) REFERENCES extraction_models(model_id) ON DELETE CASCADE,
    CONSTRAINT uq_table_defs_model_name UNIQUE (model_id, table_name)
);
GO
CREATE INDEX idx_table_defs_model_id ON model_table_definitions(model_id);
GO

CREATE TABLE model_table_row_bounds (
    bound_id         UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    table_def_id     UNIQUEIDENTIFIER NOT NULL,
    bound_type       VARCHAR(10) NULL
                        CONSTRAINT ck_row_bounds_type CHECK (bound_type IS NULL OR bound_type IN ('row_start','row_end')),
    bound_text       NVARCHAR(255) NULL,
    display_order    INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_row_bounds_table_def FOREIGN KEY (table_def_id) REFERENCES model_table_definitions(table_def_id) ON DELETE CASCADE
);
GO
CREATE INDEX idx_row_bounds_table_def_id ON model_table_row_bounds(table_def_id);
GO

CREATE TABLE model_table_headers (
    header_def_id    UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    table_def_id     UNIQUEIDENTIFIER NOT NULL,
    column_name      NVARCHAR(255) NOT NULL,
    column_label     NVARCHAR(255) NOT NULL,
    is_required      BIT NOT NULL DEFAULT 1,
    data_type        VARCHAR(50) NOT NULL DEFAULT 'string',
    display_order    INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_table_headers_table_def FOREIGN KEY (table_def_id) REFERENCES model_table_definitions(table_def_id) ON DELETE CASCADE,
    CONSTRAINT uq_table_headers_name UNIQUE (table_def_id, column_name)
);
GO
CREATE INDEX idx_table_headers_table_def_id ON model_table_headers(table_def_id);
GO

CREATE TABLE model_table_header_aliases (
    alias_id         UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    header_def_id    UNIQUEIDENTIFIER NOT NULL,
    alias_text       NVARCHAR(255) NULL,
    CONSTRAINT fk_header_aliases_def FOREIGN KEY (header_def_id) REFERENCES model_table_headers(header_def_id) ON DELETE CASCADE,
    CONSTRAINT uq_header_aliases UNIQUE (header_def_id, alias_text)
);
GO
CREATE INDEX idx_header_aliases_header_def_id ON model_table_header_aliases(header_def_id);
GO

-- ============================================================================
-- 5. DOCUMENTS (one row per unique uploaded file)
-- ============================================================================
CREATE TABLE documents (
    document_id       UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    uploaded_by       INT NOT NULL,
    original_filename NVARCHAR(500)  NOT NULL,
    storage_path      NVARCHAR(1000) NOT NULL,
    file_size_bytes   BIGINT NOT NULL DEFAULT 0 CONSTRAINT ck_documents_size CHECK (file_size_bytes >= 0),
    mime_type         VARCHAR(100) NOT NULL,
    status            VARCHAR(10) NOT NULL DEFAULT 'uploaded'
                         CONSTRAINT ck_documents_status CHECK (status IN ('uploaded','archived','deleted')),
    uploaded_at       DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
GO

-- ============================================================================
-- 6. PROCESSING JOBS ("a process" -- one document run against one model)
-- ============================================================================
CREATE TABLE processing_jobs (
    job_id            UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    document_id       UNIQUEIDENTIFIER NOT NULL,
    model_id          UNIQUEIDENTIFIER NOT NULL,
    ProcessedUserID   INT NOT NULL,
    status            VARCHAR(25) NOT NULL DEFAULT 'queued'
                         CONSTRAINT ck_jobs_status CHECK (status IN ('queued','processing','pending','completed','failed','cancelled','marked_as_invalid')),
    stp               BIT NOT NULL DEFAULT 0,

    error_message     NVARCHAR(MAX) NULL,

    queued_at         DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    started_at        DATETIME2(3) NULL,
    completed_at      DATETIME2(3) NULL,

    CONSTRAINT fk_jobs_document  FOREIGN KEY (document_id)  REFERENCES documents(document_id)   ON DELETE CASCADE,
    CONSTRAINT fk_jobs_model     FOREIGN KEY (model_id)     REFERENCES extraction_models(model_id) ON DELETE NO ACTION,
    CONSTRAINT ck_jobs_dates CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
);
GO
CREATE INDEX idx_jobs_document_id  ON processing_jobs(document_id);
CREATE INDEX idx_jobs_model_id     ON processing_jobs(model_id);
CREATE INDEX idx_jobs_requested_by ON processing_jobs(ProcessedUserID);
CREATE INDEX idx_jobs_status       ON processing_jobs(status);
CREATE INDEX idx_jobs_queued_at    ON processing_jobs(queued_at DESC);
GO

-- ============================================================================
-- 7. JOB PAGES (one row per output page of a job)
-- ============================================================================
CREATE TABLE job_pages (
    process_id           UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    job_id               UNIQUEIDENTIFIER NOT NULL,
    page_number          INT NOT NULL CONSTRAINT ck_pages_number CHECK (page_number > 0),
    enhanced_image_path  NVARCHAR(1000) NULL,
    annotated_image_path NVARCHAR(1000) NULL,
    ocr_tokens           NVARCHAR(MAX) NULL,

    -- carried over from the 271-line script
    status                VARCHAR(20) NOT NULL DEFAULT 'Pending'
                              CONSTRAINT ck_pages_status CHECK (status IN ('queued','processing','Pending','Completed','Marked as Invalid','Failed')),

    error_message         NVARCHAR(MAX) NULL,
    completed_at          DATETIME2(3) NULL,

    created_at           DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_pages_job FOREIGN KEY (job_id) REFERENCES processing_jobs(job_id) ON DELETE CASCADE,
    CONSTRAINT uq_pages_job_number UNIQUE (job_id, page_number)
);
GO
CREATE INDEX idx_pages_job_id ON job_pages(job_id);
CREATE INDEX idx_pages_job_status ON job_pages(job_id, status);
GO

-- ============================================================================
-- 8. JOB EXPORTS (CSV export history)
-- ============================================================================
CREATE TABLE job_exports (
    export_id         UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    job_id            UNIQUEIDENTIFIER NOT NULL,
    exported_by       INT NOT NULL,
    output_path       NVARCHAR(1000) NOT NULL,
    exported_at       DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_exports_job  FOREIGN KEY (job_id)      REFERENCES processing_jobs(job_id) ON DELETE CASCADE
);
GO
CREATE INDEX idx_exports_job_id ON job_exports(job_id);
GO

-- ============================================================================
-- 9. AUDIT LOG
-- ============================================================================
CREATE TABLE audit_log (
    audit_id          UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    user_id           INT NULL,
    action            VARCHAR(100) NOT NULL,
    entity_type       VARCHAR(100) NOT NULL,
    entity_id         UNIQUEIDENTIFIER NULL,
    ip_address        VARCHAR(45) NULL,
    created_at        DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX idx_audit_user_id    ON audit_log(user_id);
CREATE INDEX idx_audit_entity     ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_created_at ON audit_log(created_at DESC);
GO
