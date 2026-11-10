# DEPENDENCIAS
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Query, Depends, Header
from fastapi.responses import JSONResponse
from models import SolicitudRespuesta, HistorialRespuesta, RegistroUsuarioRespuesta, Solicitud, RegistroUsuario, ChatCompletionRequest, ChatCompletionResponse
from services import verificar_limite, obtener_historial, service_registrar_usuario, Error_UsuarioNoEncontrado, Error_RegistroUsuarioInvalido
from typing import Literal
import database, sqlite3, logging
import time
import uuid
from gemini import GeminiProvider, GeminiProviderError

# INICIO DE LA APLICACIÓN
logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
  database.inicializar_db()
  yield

app = FastAPI(lifespan=lifespan)
gemini = GeminiProvider()

@app.exception_handler(sqlite3.Error)
async def manejar_error_sqlite(request: Request, exc: sqlite3.Error):
  logging.error(
    "Error de SQLite durante la solicitud %s %s",
    request.method,
    request.url.path,
    exc_info=(type(exc), exc, exc.__traceback__)
  )
  return JSONResponse(
    status_code=500,
    content={
      "detail": "Problemas con el servidor, inténtelo más tarde."
    }
  )

@app.exception_handler(Error_UsuarioNoEncontrado)
async def manejar_usuario_no_encontrado(request: Request, exc: Error_UsuarioNoEncontrado):
  return JSONResponse(
    status_code=404,
    content={"detail": str(exc)}
  )

@app.exception_handler(Error_RegistroUsuarioInvalido)
async def manejar_registro_de_usuario_invalido(request: Request, exc: Error_RegistroUsuarioInvalido):
  return JSONResponse(
    status_code=409,
    content={"detail": str(exc)}
  )

def verificar_api_key(api_key: str | None = Header(default=None, alias="X-Api-Key")):
  if not api_key:
    raise HTTPException(status_code=401, detail="Credenciales inválidas.")

  key_hash = database.calcular_hash(api_key)
  clave = database.buscar_api_key(key_hash)

  if clave is None:
    raise HTTPException(status_code=401, detail="Credenciales inválidas.")

  return clave

# ENDPOINTS
@app.get("/")
async def root():
  return {"servicio": "AI Gateway", "estado": "activo"}

@app.post("/solicitudes")
async def solicitud(datos: Solicitud, clave: dict = Depends(verificar_api_key)):
  resultado_solicitud = verificar_limite(clave["usuario"], datos.solicitud)

  if not resultado_solicitud:
    raise HTTPException(
      status_code=429,
      detail="Demasiadas solicitudes en un lapso de 60 segundos."
    )

  return {
    "id": resultado_solicitud["id"],
    "usuario": resultado_solicitud["usuario"],
    "solicitud": resultado_solicitud["solicitud"],
    "creado_en": resultado_solicitud["creado_en"],
    "estado": "recibida"
  }

@app.get("/usuarios/{usuario}/solicitudes", response_model=HistorialRespuesta)
async def solicitudes_usuario(usuario: str, clave: dict = Depends(verificar_api_key), limite: int = Query(default=10, ge=1, le=100), desplazamiento: int = Query(default=0, ge=0), order: Literal["ASC", "DESC"] = Query(default="DESC"), desde: float | None = Query(default=None, ge=0)):

  if usuario != clave["usuario"]:
    raise HTTPException(status_code=403, detail="Usuario incorrecto.")
  
  historial = obtener_historial(usuario, order, limite, desplazamiento, desde)
  total = historial["count"]
  solicitudes = []
  
  for fila in historial["solicitudes"]:
    solicitudes.append({
      "id": fila[0],
      "usuario": fila[1],
      "solicitud": fila[2],
      "creado_en": fila[3]
    })
  
  return {"count": total, "solicitudes": solicitudes}

@app.post("/registro", response_model=RegistroUsuarioRespuesta)
async def registrar_usuario(datos: RegistroUsuario):
  registro = service_registrar_usuario(datos.usuario, datos.nombre)
  return registro

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(datos: ChatCompletionRequest, clave: dict = Depends(verificar_api_key)):
  # Por ahora solamente admitimos generación normal
  if datos.stream:
    raise HTTPException(status_code=501, detail="El streaming todavía no está implementado.")

  # Aplicamos el límite de solicitudes existente
  resultado = verificar_limite(clave["usuario"], "[chat completion]")
  if not resultado:
    raise HTTPException(status_code=429, detail="Demasiadas solicitudes en un lapso de 60 segundos.")

  try:
    respuesta = await gemini.generate(
      model=datos.model,
      messages=datos.messages,
      temperature=datos.temperature,
      max_tokens=datos.max_tokens
    )

  except GeminiProviderError:
    raise HTTPException(status_code=502, detail="El proveedor de IA no pudo procesar la solicitud.")

  # Normalizamos la razón de finalización
  finish_reason = respuesta["finish_reason"]
  finish_reason = {
    "max_tokens": "length",
    "max_output_tokens": "length",
    "safety": "content_filter"
  }.get(finish_reason, finish_reason)

  usage = respuesta["usage"]

  if all(value is not None for value in usage.values()):
    usage = {
      "prompt_tokens": usage["prompt_tokens"],
      "completion_tokens": usage["completion_tokens"],
      "total_tokens": usage["total_tokens"]
    }
  else:
    usage = None

  return {
    "id": f"chatcmpl-{uuid.uuid4().hex}",
    "created": int(time.time()),
    "model": datos.model,
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": respuesta["content"]
        },
        "finish_reason": finish_reason
      }
    ],
    "usage": usage
  }