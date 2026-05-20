"""
Run with:
    pip install -r requirements.txt
    uvicorn app:app --reload

Try:
    curl -X POST http://127.0.0.1:8000/todos \
        -H "Content-Type: application/json" \
        -d '{"title": "Write docs", "priority": 2, "tags": ["docs"]}'
"""

from typing import Dict, List, Optional

from micropie import App
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class TodoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    priority: int = Field(default=3, ge=1, le=5)
    tags: List[str] = Field(default_factory=list)


class Todo(TodoCreate):
    id: int
    completed: bool = False


class Root(App):
    def __init__(self):
        super().__init__()
        self._todos: Dict[int, Todo] = {}
        self._next_id = 1

    async def index(self):
        return {
            "message": "MicroPie + pydantic example",
            "routes": {
                "GET /todos": "List todos",
                "GET /todos/<id>": "Fetch one todo",
                "POST /todos": "Create a todo from a JSON body",
            },
            "example": {
                "title": "Write a MicroPie example",
                "priority": 2,
                "tags": ["docs", "pydantic"],
            },
        }

    async def todos(self, todo_id: Optional[str] = None):
        if self.request.method == "GET":
            if todo_id is None:
                return {"todos": [todo.model_dump() for todo in self._todos.values()]}

            try:
                todo = self._todos[int(todo_id)]
            except (KeyError, ValueError):
                return 404, {"error": "Todo not found"}

            return todo.model_dump()

        if self.request.method == "POST":
            try:
                todo_in = TodoCreate.model_validate(self.request.json())
            except ValidationError as exc:
                return 422, {"errors": exc.errors()}

            todo = Todo(id=self._next_id, **todo_in.model_dump())
            self._todos[todo.id] = todo
            self._next_id += 1
            return 201, todo.model_dump()

        return 405, {"error": "Method not allowed"}


app = Root()  # Run with `uvicorn app:app --reload`
