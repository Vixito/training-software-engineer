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

class RegistroUsuario(BaseModel):
  usuario: str = Field(..., min_length=1)
  nombre: str = Field(..., min_length=1)
  api_key: str

  @field_validator("usuario", "nombre")
  @classmethod
  def validar_campo(cls, valor: str, info: ValidationInfo) -> str:
    valor = valor.strip()
    if not valor:
      raise ValueError("El campo no puede estar vacío")
    return valor
