from typing import Literal
from pydantic import BaseModel, Field, field_validator, ValidationInfo

class Solicitud(BaseModel):
  solicitud: str = Field(..., min_length=1)

  @field_validator("solicitud")
  @classmethod
  def validar_campo(cls, valor: str, info: ValidationInfo) -> str:
    valor = valor.strip()
    if not valor:
      raise ValueError("La solicitud no puede estar vacía")
    return valor

class SolicitudRespuesta(BaseModel):
  id: int
  usuario: str
  solicitud: str
  creado_en: float

class HistorialRespuesta(BaseModel):
  count: int
  solicitudes: list[SolicitudRespuesta]

class RegistroUsuarioRespuesta(BaseModel):
  id: int
  usuario: str
  api_key: str
  nombre: str
  creado_en: float


class RegistroUsuario(BaseModel):
  usuario: str = Field(..., min_length=1)
  nombre: str = Field(..., min_length=1)

  @field_validator("usuario", "nombre")
  @classmethod
  def validar_campo(cls, valor: str, info: ValidationInfo) -> str:
    valor = valor.strip()
    if not valor:
      raise ValueError("El campo no puede estar vacío")
    return valor

class ChatMessage(BaseModel):
  role: Literal["system", "user", "assistant"]
  content: str = Field(min_length=1)

  @field_validator("content")
  @classmethod
  def validar_contenido(cls, valor: str) -> str:
    valor = valor.strip()

    if not valor:
      raise ValueError("El contenido del mensaje no puede estar vacío.")

    return valor

class ChatCompletionRequest(BaseModel):
  model: str = Field(min_length=1)
  messages: list[ChatMessage] = Field(min_length=1)
  temperature: float | None = Field(default=None, ge=0, le=2)
  max_tokens: int | None = Field(default=None, gt=0)
  stream: bool = False

class ChatCompletionMessage(BaseModel):
  role: Literal["assistant"]
  content: str

class ChatCompletionChoice(BaseModel):
  index: int
  message: ChatCompletionMessage
  finish_reason: str | None

class ChatCompletionUsage(BaseModel):
  prompt_tokens: int
  completion_tokens: int
  total_tokens: int

class ChatCompletionResponse(BaseModel):
  id: str
  object: Literal["chat.completion"] = "chat.completion"
  created: int
  model: str
  choices: list[ChatCompletionChoice]
  usage: ChatCompletionUsage | None = None