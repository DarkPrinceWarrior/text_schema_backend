from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple

try:
    from pydantic import ConfigDict
except ImportError:
    ConfigDict = None

# --- Модели данных для нашего DSL (FlowJSON) ---

class Node(BaseModel):
    id: str
    type: str  # 'action', 'decision', 'start', 'end'
    label: str
    actor: Optional[str] = None
    sourceSpan: Optional[Tuple[int, int]] = None

class Edge(BaseModel):
    from_node: str = Field(alias="from")
    to: str
    label: Optional[str] = None

    # Совместимость с Pydantic v1/v2 для заполнения по имени поля
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
    version="0.1.0",
)

# --- Настройка CORS ---
# Позволяет нашему фронтенду (который работает на другом порту)
# делать запросы к этому бэкенду.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене стоит указать конкретный домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/process-text", response_model=FlowJSON)
async def process_text(data: TextInput):
    """
    Принимает текст и (пока что) возвращает
    заранее заготовленную схему в формате FlowJSON.
    """
    

    # ЗАГЛУШКА: Возвращаем "захардкоженный" результат
    # В следующих шагах здесь будет логика NLP
    mock_response = {
        "meta": {"version": "1.0", "title": "Обработка ДТП"},
        "nodes": [
            {"id": "n0", "type": "start", "label": "Старт"},
            {"id": "n1", "type": "action", "label": "Обеспечить безопасность, выставить знак"},
            {"id": "n2", "type": "decision", "label": "Есть пострадавшие?"},
            {"id": "n3", "type": "action", "label": "Вызвать 112"},
            {"id": "n4", "type": "action", "label": "Зафиксировать обстоятельства"},
            {"id": "n5", "type": "decision", "label": "Ущерб незначителен и участники согласны?"},
            {"id": "n6", "type": "action", "label": "Оформить извещение"},
            {"id": "n7", "type": "action", "label": "Вызвать ГИБДД"},
            {"id": "n8", "type": "end", "label": "Конец"},
        ],
        "edges": [
            {"from_node": "n0", "to": "n1"},
            {"from_node": "n1", "to": "n2"},
            {"from_node": "n2", "to": "n3", "label": "да"},
            {"from_node": "n3", "to": "n4"},
            {"from_node": "n2", "to": "n4", "label": "нет"},
            {"from_node": "n4", "to": "n5"},
            {"from_node": "n5", "to": "n6", "label": "да"},
            {"from_node": "n6", "to": "n8"},
            {"from_node": "n5", "to": "n7", "label": "нет"},
            {"from_node": "n7", "to": "n8"},
        ]
    }
    
    return mock_response

# --- Инструкция по запуску ---
# 1. Установите зависимости: pip install fastapi "uvicorn[standard]" pydantic
# 2. Сохраните этот код в файл, например, main.py
# 3. Запустите сервер командой: uvicorn main:app --reload
# Сервер будет доступен по адресу http://127.0.0.1:8000
