import time
import database

class Error_UsuarioNoEncontrado(Exception):
  pass

def obtener_tiempo():
  return time.time()

def verificar_limite(usuario, solicitud):
  momento = obtener_tiempo()
  verificar_usuario_registrado(usuario)
  return database.registrar_solicitud_si_permitida(usuario=usuario, solicitud=solicitud, momento=momento)

def obtener_historial(usuario, order, limite, desplazamiento, desde=None):
  verificar_usuario_registrado(usuario)
  return database.historial(usuario, order, limite, desplazamiento, desde)

def verificar_usuario_registrado(usuario):
  if not database.usuario_existe(usuario):
    raise Error_UsuarioNoEncontrado("Usuario no registrado.")

def registrar_usuario(usuario, nombre):
  api_key = database.registrar_api_key(usuario, nombre)
  database.registrar_usuario(usuario)
  return {"usuario": usuario, "nombre": nombre, "api_key": api_key}
  