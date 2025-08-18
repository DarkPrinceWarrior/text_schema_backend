import os
import httpx 
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple

# --- Конфигурация ---
# ВАЖНО: Для продакшена лучше вернуть os.environ.get("OPENROUTER_API_KEY")
# Я оставляю ключ здесь для удобства дальнейшего тестирования.
OPENROUTER_API_KEY = "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"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "mistralai/mistral-medium-3.1" 

# --- Модели данных (без изменений) ---

try:
    from pydantic import ConfigDict
except ImportError:
    ConfigDict = None

class Node(BaseModel):
    id: str
    type: str
    label: str
    actor: Optional[str] = None
    sourceSpan: Optional[Tuple[int, int]] = None

class Edge(BaseModel):
    from_node: str = Field(alias="from")
    to: str
    label: Optional[str] = None

    if ConfigDict is not None:
        model_config = ConfigDict(populate_by_name=True)
    else:
        class Config:
            allow_population_by_field_name = True

class Lane(BaseModel):
    id: str
    label: str
    nodes: List[str]

class FlowJSON(BaseModel):
    meta: dict
    nodes: List[Node]
    edges: List[Edge]
    lanes: Optional[List[Lane]] = None

class TextInput(BaseModel):
    text: str

# --- Создание FastAPI приложения ---

app = FastAPI(
    title="Text to Diagram API",
    description="API для преобразования текста в FlowJSON-схему",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ОБНОВЛЕННЫЙ Системный промпт для LLM ---
SYSTEM_PROMPT = """
You are an expert business process analyst. Your task is to convert a user's text description of a process into a structured FlowJSON format.

**Your Goal:**
1.  Identify all process steps (`action`), decision points (`decision`), start, and end points.
2.  Identify the actor (person, role, or system) responsible for each action.
3.  **For each node, provide the character indices from the original text in the `sourceSpan` field as a `[start, end]` array.** This is crucial for traceability.

**FlowJSON Schema:**
- `nodes`: A list of process steps. Each node must have `id`, `type`, `label`, and `sourceSpan`.
- `edges`: A list of connections between nodes.
- `lanes`: A list of actors.

**Rules:**
- Your output MUST be ONLY a valid JSON object. No explanations or markdown.
- `sourceSpan` must be accurate. For "The client submits a request.", the span for the corresponding node should be `[4, 31]`.

**Example:**

**User Text:**
The process starts when a client submits a request. The system automatically registers the request. Then, a support specialist reviews the request. If the request is complete, the specialist processes it. Otherwise, they contact the client for more information.

**Your JSON Output:**
{
  "meta": { "version": "1.0", "title": "Обработка запроса клиента" },
  "nodes": [
    { "id": "n0", "type": "start", "label": "Старт", "sourceSpan": [0, 0] },
    { "id": "n1", "type": "action", "label": "Клиент подает запрос", "actor": "Клиент", "sourceSpan": [25, 49] },
    { "id": "n2", "type": "action", "label": "Система регистрирует запрос", "actor": "Система", "sourceSpan": [51, 88] },
    { "id": "n3", "type": "action", "label": "Специалист поддержки проверяет запрос", "actor": "Специалист поддержки", "sourceSpan": [96, 134] },
    { "id": "n4", "type": "decision", "label": "Запрос полный?", "sourceSpan": [136, 159] },
    { "id": "n5", "type": "action", "label": "Обработать запрос", "actor": "Специалист поддержки", "sourceSpan": [161, 186] },
    { "id": "n6", "type": "action", "label": "Связаться с клиентом для уточнений", "actor": "Специалист поддержки", "sourceSpan": [197, 237] },
    { "id": "n7", "type": "end", "label": "Конец", "sourceSpan": [237, 237] }
  ],
  "edges": [
    { "from": "n0", "to": "n1" }, { "from": "n1", "to": "n2" }, { "from": "n2", "to": "n3" },
    { "from": "n3", "to": "n4" }, { "from": "n4", "to": "n5", "label": "да" },
    { "from": "n4", "to": "n6", "label": "нет" }, { "from": "n5", "to": "n7" }, { "from": "n6", "to": "n3" }
  ],
  "lanes": [
      { "id": "l1", "label": "Клиент", "nodes": ["n1"] },
      { "id": "l2", "label": "Система", "nodes": ["n2"] },
      { "id": "l3", "label": "Специалист поддержки", "nodes": ["n3", "n5", "n6"] }
  ]
}
"""

async def call_llm_for_schema(text: str) -> dict:
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY не установлен.")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            llm_response = response.json()
            json_content_str = llm_response['choices'][0]['message']['content']
            return json.loads(json_content_str)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Ошибка при запросе к OpenRouter: {exc}")
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            raise HTTPException(status_code=500, detail=f"Не удалось разобрать ответ от LLM: {exc}")


@app.post("/process-text", response_model=FlowJSON)
async def process_text(data: TextInput):
    print(f"Получен текст для обработки LLM: {data.text[:100]}...")
    llm_generated_json = await call_llm_for_schema(data.text)
    
    try:
        if hasattr(FlowJSON, 'model_validate'):
             validated_schema = FlowJSON.model_validate(llm_generated_json)
             return validated_schema
        else:
             validated_schema = FlowJSON.parse_obj(llm_generated_json)
             return validated_schema
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка валидации схемы от LLM: {e}")