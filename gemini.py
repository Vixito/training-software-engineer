import os
from google import genai
from google.genai import types

class GeminiProviderError(Exception):
  pass

class GeminiProvider:
  async def generate(self, model, messages, temperature=None, max_tokens=None):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
      raise GeminiProviderError("El proveedor de IA no está configurado.")

    # Gemini maneja las instrucciones del sistema por separado.
    system_instruction = None
    contents = []

    for message in messages:
      role = message.role
      content = message.content

      if role == "system":
        system_instruction = content
      else:
        gemini_role = "model" if role == "assistant" else "user"
        contents.append(
          types.Content(role=gemini_role, parts=[types.Part.from_text(text=content)])
        )

    config = types.GenerateContentConfig(
      system_instruction=system_instruction,
      temperature=temperature,
      max_output_tokens=max_tokens
    )

    try:
      async with genai.Client(api_key=api_key).aio as client:
        response = await client.models.generate_content(
          model=model,
          contents=contents,
          config=config
        )

      usage = response.usage_metadata

      return {
        "content": response.text,
        "usage": {
          "prompt_tokens": usage.prompt_token_count if usage else None,
          "completion_tokens": usage.candidates_token_count if usage else None,
          "total_tokens": usage.total_token_count if usage else None
        },
        "finish_reason": {
          str(response.candidates[0].finish_reason).split(".")[-1].lower()
          if response.candidates else None
        }
      }

    except Exception as error:
      raise GeminiProviderError("No fue posible generar una respuesta con Gemini.") from error