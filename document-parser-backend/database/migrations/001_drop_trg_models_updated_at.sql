-- ============================================================================
-- Migration 001: Drop trg_models_updated_at
-- ============================================================================
-- Problem: The trigger trg_models_updated_at was overwriting the Python-set
-- IST timestamp with SYSUTCDATETIME() (UTC time). When saving an extraction
-- model, ModelRepository.save() correctly computes updated_at in IST, but
-- the trigger immediately overrode it with UTC, causing the wrong time to
-- be stored.
--
-- Fix: Drop the trigger. The Python application code already handles
-- setting updated_at correctly, so the trigger is redundant and harmful.
-- ============================================================================

IF EXISTS (SELECT * FROM sys.triggers WHERE name = 'trg_models_updated_at')
BEGIN
    DROP TRIGGER trg_models_updated_at;
    PRINT 'Dropped trigger trg_models_updated_at successfully.';
END
ELSE
BEGIN
    PRINT 'Trigger trg_models_updated_at does not exist (already dropped).';
END
GO