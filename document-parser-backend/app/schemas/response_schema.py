from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ============================================================
# GENERIC
# ============================================================

class StatusResponse(BaseModel):
    status: str


class ProcessResponse(BaseModel):
    status: str
    data: Any


# ============================================================
# MODEL RESPONSES
# ============================================================

class FormFieldResponse(BaseModel):
    fieldName:  str
    fieldLabel: str
    datatype:   str
    required:   bool
    aiEnabled:  bool
    prompt:     str
    aliases:    List[str]


class TableFieldHeaderResponse(BaseModel):
    fieldName:  str
    fieldLabel: str
    datatype:   str
    required:   bool
    aliases:    List[str]


class TableFieldResponse(BaseModel):
    tableName:  str
    required:   bool
    startRows:  List[str]
    endRows:    List[str]
    fields:     List[TableFieldHeaderResponse]


class ModelResponse(BaseModel):
    id:           str
    name:         str
    engine:       str
    documentType: str
    language:     str
    description:  str
    created:      str
    updated:      str
    processCount:  int = 0
    formFields:   List[FormFieldResponse] = []
    tableFields:  Dict[str, TableFieldResponse] = {}


class ModelsListResponse(BaseModel):
    status: str
    models: List[ModelResponse]


class SingleModelResponse(BaseModel):
    status: str
    model:  ModelResponse


# ============================================================
# HISTORY RESPONSES
# ============================================================

class HistoryEntryResponse(BaseModel):
    historyid:    str
    modelid:      str
    status:       str
    modelname:    str
    documenttype: str
    createddate:  str
    processdate:  str
    documentname: str = ""
    stp:          bool = False
    error_message: str = ""


class HistoryListResponse(BaseModel):
    status:  str
    history: List[HistoryEntryResponse]


class SingleHistoryResponse(BaseModel):
    status:  str
    history: HistoryEntryResponse