from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================
# DOCUMENT SCHEMA
# ============================================================
class DocumentSchema(BaseModel):
    file_name: str = Field(default="", description="Document file name")
    url: str = Field(default="", description="Path or URL to the document image")
    Output_path: str = Field(default="", description="Output path for results")


# ============================================================
# EXTRACTION MODEL SCHEMA
# ============================================================
class ExtractionModelSchema(BaseModel):
    model_id: str = Field(default="", description="Model ID for extraction")


# ============================================================
# LABEL SCHEMA
# ============================================================
class LabelSchema(BaseModel):
    label_name: str = Field(description="Name of the label to extract")
    required: bool = Field(default=True, description="Whether this label is required")
    data_type: str = Field(default="string", description="Data type (string, number, date, etc.)")
    AI_skill: bool = Field(default=False, description="Use AI for extraction")
    AI_prompt: str = Field(default="", description="Prompt for AI extraction")
    aliases: List[str] = Field(default=[], description="Alternative names for this label")


# ============================================================
# OCR SCHEMA
# ============================================================
class OCRSchema(BaseModel):
    enabled: bool = Field(default=True, description="Enable OCR processing")
    min_confidence: float = Field(default=0.8, description="Minimum confidence threshold")
    labels: List[LabelSchema] = Field(default=[], description="Labels to extract")


# ============================================================
# TABLE HEADER SCHEMA
# ============================================================
class TableHeaderSchema(BaseModel):
    header_name: str = Field(description="Header name")
    required: bool = Field(default=True, description="Whether this header is required")
    data_type: str = Field(default="string", description="Data type")
    aliases: List[str] = Field(default=[], description="Alternative names for this header")


# ============================================================
# TABLE DEFINITION SCHEMA
# ============================================================
class TableDefinitionSchema(BaseModel):
    table_name: str = Field(description="Name of the table")
    enabled: bool = Field(default=True, description="Enable this table extraction")
    min_confidence: float = Field(default=0.75, description="Minimum confidence for table detection")
    table_rowStart: List[str] = Field(default=[], description="Keywords that mark table start")
    table_rowEnd: List[str] = Field(default=[], description="Keywords that mark table end")
    headers: List[TableHeaderSchema] = Field(default=[], description="Table headers")


# ============================================================
# TABLES SCHEMA
# ============================================================
class TablesSchema(BaseModel):
    enabled: bool = Field(default=True, description="Enable table extraction")
    table_list: List[TableDefinitionSchema] = Field(default=[], description="List of tables to extract")


# ============================================================
# MATCHING SCHEMA
# ============================================================
class MatchingSchema(BaseModel):
    case_sensitive: bool = Field(default=False, description="Case-sensitive matching")
    trim_whitespace: bool = Field(default=False, description="Trim whitespace")
    fuzzy_match: bool = Field(default=True, description="Enable fuzzy matching")


# ============================================================
# COMPLETE PROCESS REQUEST SCHEMA
# ============================================================
class ProcessRequestSchema(BaseModel):
    schema_version: str = Field(default="1.0", description="Schema version")
    document: DocumentSchema = Field(description="Document configuration")
    extrcation_model: ExtractionModelSchema = Field(description="Extraction model settings")
    ocr: OCRSchema = Field(description="OCR settings")
    tables: Optional[TablesSchema] = Field(default=None, description="Table extraction settings")
    matching: Optional[MatchingSchema] = Field(default=None, description="Matching settings")
    logging_type: Optional[str] = Field(default=None, description="Logging type (INFO/DEBUG/ERROR). All logs are always stored on the server.")

    class Config:
        json_schema_extra = {
            "example": {
                "schema_version": "1.0",
                "document": {"file_name": "", "url": "", "Output_path": " "},
                "extrcation_model": {"model_id": ""},
                "ocr": {
                    "enabled": True,
                    "min_confidence": 0.8,
                    "labels": [
                        {
                            "label_name": "Invoice",
                            "required": True,
                            "data_type": "string",
                            "AI_skill": False,
                            "AI_prompt": "what is Invoice",
                            "aliases": ["Invoice"],
                        }
                    ],
                },
                "tables": {
                    "enabled": True,
                    "table_list": [
                        {
                            "table_name": "table1",
                            "enabled": True,
                            "min_confidence": 0.75,
                            "table_rowStart": ["sub", "qty"],
                            "table_rowEnd": ["Subtotal"],
                            "headers": [
                                {
                                    "header_name": "Qty",
                                    "required": True,
                                    "data_type": "string",
                                    "aliases": ["quantity"],
                                }
                            ],
                        }
                    ],
                },
                "matching": {"case_sensitive": False, "trim_whitespace": False, "fuzzy_match": True},
                "logging_type": "INFO",
            }
        }


# ============================================================
# MODEL REQUEST SCHEMAS
# ============================================================

class FormFieldRequest(BaseModel):
    """A single key-value label field definition."""
    fieldName:  str = Field(default="", description="Internal field name")
    fieldLabel: str = Field(default="", description="Display label")
    datatype:   str = Field(default="string", description="Data type")
    required:   bool = Field(default=True)
    aiEnabled:  bool = Field(default=False)
    prompt:     str = Field(default="")
    aliases:    List[str] = Field(default=[])


class TableFieldHeaderRequest(BaseModel):
    fieldName:  str = Field(default="")
    fieldLabel: str = Field(default="")
    datatype:   str = Field(default="string")
    required:   bool = Field(default=True)
    aliases:    List[str] = Field(default=[])


class TableFieldRequest(BaseModel):
    tableName:  str = Field(default="")
    required:   bool = Field(default=True)
    startRows:  List[str] = Field(default=[])
    endRows:    List[str] = Field(default=[])
    fields:     List[TableFieldHeaderRequest] = Field(default=[])


class SaveModelRequest(BaseModel):
    """Request body for POST /document/models."""
    id:           Optional[str] = Field(default=None, description="Existing model UUID (for updates)")
    name:         str = Field(default="Untitled Model")
    description:  str = Field(default="")
    engine:       Optional[str] = Field(default="OCR", description="OCR or LLM")
    documentType: Optional[str] = Field(default="invoice")
    language:     Optional[str] = Field(default="en")
    formFields:   List[FormFieldRequest] = Field(default=[])
    tableFields:  Dict[str, TableFieldRequest] = Field(default={})

    def to_dict(self) -> dict:
        """Convert to the dict shape expected by ModelRepository.save()."""
        return self.model_dump()


# ============================================================
# HISTORY REQUEST SCHEMAS
# ============================================================

class CreateHistoryRequest(BaseModel):
    """Request body for POST /document/history."""
    model_id:      str = Field(default="")
    model_name:    str = Field(default="")
    document_type: str = Field(default="")
    status:        str = Field(default="processing")
    createddate:   str = Field(default="")
    processdate:   str = Field(default="")


class UpdateHistoryRequest(BaseModel):
    """Request body for PATCH /document/history/{history_id}."""
    status: str = Field(default="")
    stp: Optional[int] = Field(default=None, description="Straight-Through Processing flag: 1 for auto, 0 for manual")
    error_message: Optional[str] = Field(default=None, description="Error message when the job fails")
