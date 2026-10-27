import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .db import connect, init_db
from .parser import extract_requirements, extract_text

ROOT = Path(__file__).resolve().parents[2]
UPLOADS = Path(__file__).resolve().parents[1] / "data" / "uploads"
FRONTEND = ROOT / "frontend"

app = FastAPI(title="招投标材料智能编制与核验平台 · 测试版")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = ""
    bidder: str = ""
    deadline: str = ""


class RequirementIn(BaseModel):
    category: str = "其他"
    content: str = Field(min_length=1, max_length=1000)
    source_location: str = "人工新增"
    note: str = ""


class RequirementPatch(BaseModel):
    content: str | None = None
    category: str | None = None
    status: str | None = None
    note: str | None = None


@app.on_event("startup")
def startup() -> None:
    init_db()
    UPLOADS.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "stage": "test-v0", "external_model": False}


@app.get("/api/projects")
def list_projects() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.*,
                   (SELECT COUNT(*) FROM requirements r WHERE r.project_id = p.id) AS requirement_count,
                   (SELECT COUNT(*) FROM requirements r WHERE r.project_id = p.id AND r.status = 'pending') AS pending_count
            FROM projects p
            ORDER BY p.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/projects")
def create_project(body: ProjectIn) -> dict:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, code, bidder, deadline) VALUES (?, ?, ?, ?)",
            (body.name.strip(), body.code.strip(), body.bidder.strip(), body.deadline.strip()),
        )
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.get("/api/projects/{project_id}")
def get_project(project_id: int) -> dict:
    with connect() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if project is None:
            raise HTTPException(404, "项目不存在")
        documents = conn.execute(
            "SELECT * FROM documents WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
        requirements = conn.execute(
            "SELECT * FROM requirements WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
    return {
        "project": dict(project),
        "documents": [dict(row) for row in documents],
        "requirements": [dict(row) for row in requirements],
    }


@app.post("/api/projects/{project_id}/documents")
async def upload_document(project_id: int, file: UploadFile = File(...)) -> dict:
    with connect() as conn:
        project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise HTTPException(404, "项目不存在")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".pdf", ".docx"}:
        raise HTTPException(400, "测试版仅接受 txt、md、pdf、docx")
    stored = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOADS / stored
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    pages, status = extract_text(dest)
    note = _status_note(status)
    items = extract_requirements(pages, file.filename or stored) if status not in {"scan-unreadable", "empty-pdf", "empty-docx"} else []
    if status.startswith("partial-empty") and not items:
        note += "；未能抽出可确认条款，请人工补录。"
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO documents (project_id, filename, stored_name, parse_status, parse_note, page_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, file.filename or stored, stored, status, note, len(pages)),
        )
        document_id = cur.lastrowid
        for item in items:
            conn.execute(
                """
                INSERT INTO requirements
                (project_id, document_id, category, content, source_file, source_location, confidence, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    project_id,
                    document_id,
                    item["category"],
                    item["content"],
                    item["source_file"],
                    item["source_location"],
                    item["confidence"],
                ),
            )
    return {"document_id": document_id, "parse_status": status, "parse_note": note, "extracted": len(items)}


def _status_note(status: str) -> str:
    if status == "ok":
        return "文本已读取。以下为规则抽取，需人工确认，不是审查结论。"
    if status == "scan-unreadable":
        return "各页均未读出文字，按扫描件处理。测试版不做 OCR，不会猜测内容，请人工补录。"
    if status.startswith("partial-empty"):
        return f"部分页面无文字（{status.split(':', 1)[-1]}），这些页未猜测填补。"
    if status.startswith("unsupported"):
        return "文件类型暂不支持。"
    if status.startswith("empty"):
        return "文件没有可读正文。"
    return status


@app.post("/api/projects/{project_id}/requirements")
def add_requirement(project_id: int, body: RequirementIn) -> dict:
    with connect() as conn:
        project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if project is None:
            raise HTTPException(404, "项目不存在")
        cur = conn.execute(
            """
            INSERT INTO requirements
            (project_id, category, content, source_file, source_location, confidence, status, note)
            VALUES (?, ?, ?, '人工', ?, 'manual', 'confirmed', ?)
            """,
            (project_id, body.category, body.content.strip(), body.source_location, body.note),
        )
        row = conn.execute("SELECT * FROM requirements WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.patch("/api/requirements/{requirement_id}")
def patch_requirement(requirement_id: int, body: RequirementPatch) -> dict:
    allowed_status = {"pending", "confirmed", "not_applicable"}
    if body.status is not None and body.status not in allowed_status:
        raise HTTPException(400, "状态只能是 pending、confirmed、not_applicable")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "没有要更新的字段")
    sets = ", ".join(f"{key} = ?" for key in fields)
    with connect() as conn:
        existing = conn.execute("SELECT id FROM requirements WHERE id = ?", (requirement_id,)).fetchone()
        if existing is None:
            raise HTTPException(404, "要求不存在")
        conn.execute(f"UPDATE requirements SET {sets} WHERE id = ?", (*fields.values(), requirement_id))
        row = conn.execute("SELECT * FROM requirements WHERE id = ?", (requirement_id,)).fetchone()
    return dict(row)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")
