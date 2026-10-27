import shutil
import uuid
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .auth import current_user, login, logout, seed_users
from .db import connect, init_db
from .parser import extract_requirements, extract_text
from .agents import task_plan_graph

UPLOADS = Path(__file__).resolve().parents[1] / "data" / "uploads"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_users()
    UPLOADS.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="招投标材料智能编制与核验平台 · 测试版", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPEN_PATHS = {"/api/health", "/api/auth/login"}


@app.middleware("http")
async def require_login(request: Request, call_next):
    if request.url.path.startswith("/api") and request.url.path not in OPEN_PATHS:
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if current_user(token) is None:
            return JSONResponse({"detail": "请先登录"}, status_code=401)
    return await call_next(request)


class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def auth_login(body: LoginIn) -> dict:
    result = login(body.username, body.password)
    if result is None:
        raise HTTPException(401, "账号或密码不正确")
    return result


@app.get("/api/auth/me")
def auth_me(request: Request) -> dict:
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    user = current_user(token)
    if user is None:
        raise HTTPException(401, "请先登录")
    return user


@app.post("/api/auth/logout")
def auth_logout(request: Request) -> dict:
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    logout(token)
    return {"ok": True}


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


class TaskIn(BaseModel):
    requirement_id: int
    department: str = ""
    assignee_id: int | None = None
    due_at: str = ""


class TaskPatch(BaseModel):
    department: str | None = None
    assignee_id: int | None = None
    due_at: str | None = None
    task_status: str | None = None


class ArchiveIn(BaseModel):
    asset_type: str
    title: str = Field(min_length=1, max_length=200)
    holder_name: str = ""
    valid_until: str = ""
    confidentiality: str = "internal"
    scope_note: str = ""
    source_project: str = ""


class ClarificationIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    change_type: str = "changed"
    received_at: str = ""
    summary: str = ""


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
        tasks = conn.execute(
            """
            SELECT t.*, r.content AS requirement_content, u.display_name AS assignee_name
            FROM material_tasks t
            JOIN requirements r ON r.id = t.requirement_id
            LEFT JOIN users u ON u.id = t.assignee_id
            WHERE t.project_id = ? ORDER BY t.id DESC
            """,
            (project_id,),
        ).fetchall()
    return {
        "project": dict(project),
        "documents": [dict(row) for row in documents],
        "requirements": [dict(row) for row in requirements],
        "tasks": [dict(row) for row in tasks],
    }


@app.get("/api/projects/{project_id}/tasks")
def list_tasks(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT t.*, r.content AS requirement_content, u.display_name AS assignee_name
            FROM material_tasks t JOIN requirements r ON r.id = t.requirement_id
            LEFT JOIN users u ON u.id = t.assignee_id
            WHERE t.project_id = ? ORDER BY t.id DESC
            """, (project_id,)
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/projects/{project_id}/agent/task-plan")
def generate_task_plan(project_id: int) -> dict:
    with connect() as conn:
        project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if project is None:
            raise HTTPException(404, "项目不存在")
        requirements = conn.execute(
            "SELECT id, category, content, status FROM requirements WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
    result = task_plan_graph.invoke({"requirements": [dict(row) for row in requirements]})
    return {
        "project_id": project_id,
        "suggestions": result.get("suggestions", []),
        "needs_human_review": result.get("needs_human_review", True),
        "trace": result.get("trace", []),
        "model_used": False,
    }


@app.get("/api/projects/{project_id}/checks")
def project_checks(project_id: int) -> dict:
    with connect() as conn:
        project = conn.execute("SELECT id, name FROM projects WHERE id = ?", (project_id,)).fetchone()
        if project is None:
            raise HTTPException(404, "项目不存在")
        rows = conn.execute(
            """
            SELECT r.id, r.category, r.content, r.status,
                   COUNT(DISTINCT t.id) AS task_count,
                   COUNT(DISTINCT f.id) AS file_count
            FROM requirements r
            LEFT JOIN material_tasks t ON t.requirement_id = r.id
            LEFT JOIN task_files f ON f.task_id = t.id
            WHERE r.project_id = ?
            GROUP BY r.id ORDER BY r.id
            """, (project_id,)
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        problems = []
        if item["status"] == "pending":
            problems.append("要求尚未人工确认")
        if item["status"] != "not_applicable" and item["task_count"] == 0:
            problems.append("尚未分派材料任务")
        if item["task_count"] > 0 and item["file_count"] == 0:
            problems.append("任务尚未上传证明材料")
        if problems:
            item["problems"] = problems
            items.append(item)
    return {
        "project_id": project_id,
        "project_name": project["name"],
        "total_requirements": len(rows),
        "problem_count": len(items),
        "pass": not items,
        "items": items,
    }


@app.get("/api/projects/{project_id}/clarifications")
def list_clarifications(project_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM clarifications WHERE project_id = ? ORDER BY id DESC", (project_id,)).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/projects/{project_id}/clarifications")
def create_clarification(project_id: int, body: ClarificationIn) -> dict:
    if body.change_type not in {"added", "changed", "revoked"}:
        raise HTTPException(400, "变更类型不合法")
    with connect() as conn:
        if conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
            raise HTTPException(404, "项目不存在")
        cur = conn.execute(
            """INSERT INTO clarifications (project_id, title, change_type, received_at, summary)
            VALUES (?, ?, ?, ?, ?)""",
            (project_id, body.title.strip(), body.change_type, body.received_at.strip(), body.summary.strip()),
        )
        row = conn.execute("SELECT * FROM clarifications WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.get("/api/projects/{project_id}/checks/export")
def export_project_checks(project_id: int) -> StreamingResponse:
    report = project_checks(project_id)
    import csv
    import io
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["项目", "要求编号", "类别", "要求内容", "待处理问题"])
    for item in report["items"]:
        writer.writerow([report["project_name"], item["id"], item["category"], item["content"], "；".join(item["problems"])])
    data = stream.getvalue().encode("utf-8-sig")
    return StreamingResponse(iter([data]), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="project-{project_id}-check-report.csv"'
    })


@app.post("/api/projects/{project_id}/tasks")
def create_task(project_id: int, body: TaskIn) -> dict:
    with connect() as conn:
        requirement = conn.execute(
            "SELECT id FROM requirements WHERE id = ? AND project_id = ?",
            (body.requirement_id, project_id),
        ).fetchone()
        if requirement is None:
            raise HTTPException(404, "要求不存在或不属于该项目")
        cur = conn.execute(
            """INSERT INTO material_tasks
            (project_id, requirement_id, department, assignee_id, due_at)
            VALUES (?, ?, ?, ?, ?)""",
            (project_id, body.requirement_id, body.department.strip(), body.assignee_id, body.due_at.strip()),
        )
        row = conn.execute(
            """SELECT t.*, r.content AS requirement_content, u.display_name AS assignee_name
            FROM material_tasks t JOIN requirements r ON r.id=t.requirement_id
            LEFT JOIN users u ON u.id=t.assignee_id WHERE t.id=?""", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch) -> dict:
    allowed = {"open", "submitted", "done", "recheck"}
    if body.task_status is not None and body.task_status not in allowed:
        raise HTTPException(400, "任务状态不合法")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "没有要更新的字段")
    sets = ", ".join(f"{k} = ?" for k in fields)
    with connect() as conn:
        existing = conn.execute("SELECT id FROM material_tasks WHERE id = ?", (task_id,)).fetchone()
        if existing is None:
            raise HTTPException(404, "任务不存在")
        conn.execute(f"UPDATE material_tasks SET {sets} WHERE id = ?", (*fields.values(), task_id))
        row = conn.execute(
            """SELECT t.*, r.content AS requirement_content, u.display_name AS assignee_name
            FROM material_tasks t JOIN requirements r ON r.id=t.requirement_id
            LEFT JOIN users u ON u.id=t.assignee_id WHERE t.id=?""", (task_id,)
        ).fetchone()
    return dict(row)


@app.post("/api/tasks/{task_id}/files")
async def upload_task_file(task_id: int, file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"}:
        raise HTTPException(400, "任务材料仅支持常见文档、表格和压缩包")
    with connect() as conn:
        task = conn.execute("SELECT id FROM material_tasks WHERE id = ?", (task_id,)).fetchone()
        if task is None:
            raise HTTPException(404, "任务不存在")
    stored = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOADS / stored
    with dest.open("wb") as out:
        import shutil
        shutil.copyfileobj(file.file, out)
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO task_files (task_id, filename, stored_name) VALUES (?, ?, ?)",
            (task_id, file.filename or stored, stored),
        )
        row = conn.execute("SELECT * FROM task_files WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.get("/api/archive-assets")
def list_archive_assets() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM archive_assets ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/archive-assets")
def create_archive_asset(body: ArchiveIn) -> dict:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO archive_assets
            (asset_type, title, holder_name, valid_until, confidentiality, scope_note, source_project)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (body.asset_type.strip(), body.title.strip(), body.holder_name.strip(), body.valid_until.strip(),
             body.confidentiality.strip(), body.scope_note.strip(), body.source_project.strip()),
        )
        row = conn.execute("SELECT * FROM archive_assets WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


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
def index() -> dict:
    return {
        "service": "bid-materials-test",
        "ui": "http://127.0.0.1:5173",
        "note": "页面由 Vite 提供，接口仍在本服务。",
    }
