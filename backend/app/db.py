import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test.db"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            -- 投标项目主表：保存一次投标工作的基本信息。
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT NOT NULL DEFAULT '',
                bidder TEXT NOT NULL DEFAULT '',
                deadline TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            -- 招标文件表：保存项目上传文件及解析结果，不保存文件正文。
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                parse_status TEXT NOT NULL,
                parse_note TEXT NOT NULL DEFAULT '',
                page_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            -- 要求矩阵表：保存从招标文件抽取或人工补录的要求条款。
            CREATE TABLE IF NOT EXISTS requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                source_file TEXT NOT NULL DEFAULT '',
                source_location TEXT NOT NULL DEFAULT '',
                confidence TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'pending',
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            -- SQLite 没有 COMMENT ON TABLE/COLUMN，使用元数据表保存可查询的说明。
            CREATE TABLE IF NOT EXISTS schema_comments (
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL DEFAULT '',
                comment TEXT NOT NULL,
                PRIMARY KEY (table_name, column_name)
            );

            INSERT OR REPLACE INTO schema_comments (table_name, column_name, comment) VALUES
                ('projects', '', '投标项目主表，记录一次投标工作的基本信息'),
                ('projects', 'id', '项目主键'),
                ('projects', 'name', '项目名称'),
                ('projects', 'code', '项目编号'),
                ('projects', 'bidder', '投标主体或投标人名称'),
                ('projects', 'deadline', '投标截止时间，当前按文本保存'),
                ('projects', 'created_at', '项目创建时间'),
                ('documents', '', '招标文件表，记录上传文件和解析状态'),
                ('documents', 'id', '文件主键'),
                ('documents', 'project_id', '所属项目主键'),
                ('documents', 'filename', '用户上传时的原始文件名'),
                ('documents', 'stored_name', '服务器端保存的文件名'),
                ('documents', 'parse_status', '解析状态，例如 ok、scan-unreadable'),
                ('documents', 'parse_note', '解析说明及人工处理提示'),
                ('documents', 'page_count', '解析出的页数'),
                ('documents', 'created_at', '文件上传时间'),
                ('requirements', '', '要求矩阵表，记录抽取或人工补录的招标要求'),
                ('requirements', 'id', '要求主键'),
                ('requirements', 'project_id', '所属项目主键'),
                ('requirements', 'document_id', '来源文件主键，可为空（人工新增）'),
                ('requirements', 'category', '要求分类，例如资格、评分、技术'),
                ('requirements', 'content', '要求条款正文'),
                ('requirements', 'source_file', '要求来源文件名'),
                ('requirements', 'source_location', '要求在来源文件中的位置'),
                ('requirements', 'confidence', '抽取置信度或 manual'),
                ('requirements', 'status', '处理状态：pending、confirmed、not_applicable'),
                ('requirements', 'note', '人工备注'),
                ('requirements', 'created_at', '要求创建时间'),
                ('schema_comments', '', '数据库表和字段说明元数据表'),
                ('schema_comments', 'table_name', '被说明的表名'),
                ('schema_comments', 'column_name', '被说明的字段名；空值表示表级说明'),
                ('schema_comments', 'comment', '表或字段的中文说明');

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            -- 项目成员：记录谁参加这个投标项目、在项目里担任什么角色。
            CREATE TABLE IF NOT EXISTS project_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id),
                project_role TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                UNIQUE (project_id, user_id, project_role)
            );
            -- 企业档案：证照、业绩、人员证书、财务、信用和模板，可被多个项目复用。
            CREATE TABLE IF NOT EXISTS archive_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_type TEXT NOT NULL,
                title TEXT NOT NULL,
                holder_name TEXT NOT NULL DEFAULT '',
                valid_until TEXT NOT NULL DEFAULT '',
                confidentiality TEXT NOT NULL DEFAULT 'internal',
                scope_note TEXT NOT NULL DEFAULT '',
                source_project TEXT NOT NULL DEFAULT '',
                stored_name TEXT NOT NULL DEFAULT '',
                last_verified_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            -- 材料任务：把一条招标要求派给部门和责任人，并给出截止日期。
            CREATE TABLE IF NOT EXISTS material_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
                department TEXT NOT NULL DEFAULT '',
                assignee_id INTEGER REFERENCES users(id),
                due_at TEXT NOT NULL DEFAULT '',
                task_status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            -- 任务证明文件：责任人针对材料任务上传的企业材料，不是招标文件本身。
            CREATE TABLE IF NOT EXISTS task_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL REFERENCES material_tasks(id) ON DELETE CASCADE,
                archive_asset_id INTEGER REFERENCES archive_assets(id),
                filename TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                uploaded_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            -- 澄清补遗：登记答疑、澄清或补遗文件，以及它相对原要求是新增、变更还是作废。
            CREATE TABLE IF NOT EXISTS clarifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                change_type TEXT NOT NULL,
                received_at TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            -- 补遗影响：一条澄清或补遗影响到哪些要求，以及是否需要重做已完成任务。
            CREATE TABLE IF NOT EXISTS clarification_impacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clarification_id INTEGER NOT NULL REFERENCES clarifications(id) ON DELETE CASCADE,
                requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
                impact_note TEXT NOT NULL DEFAULT '',
                needs_recheck INTEGER NOT NULL DEFAULT 1
            );
            -- 审计记录：谁在何时查看、下载、修改、确认或导出，不代替审批结论。
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                user_id INTEGER REFERENCES users(id),
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            INSERT OR REPLACE INTO schema_comments (table_name, column_name, comment) VALUES
                ('users', '', '本地测试账号'),
                ('users', 'id', '用户主键'),
                ('users', 'username', '登录名'),
                ('users', 'display_name', '显示名称'),
                ('users', 'role', '角色'),
                ('users', 'password_salt', '密码盐'),
                ('users', 'password_hash', '密码摘要'),
                ('sessions', '', '登录会话'),
                ('sessions', 'token', '访问令牌'),
                ('sessions', 'user_id', '登录用户'),
                ('sessions', 'created_at', '登录时间'),
                ('project_members', '', '项目成员表，记录谁参加某个投标项目以及项目内角色'),
                ('project_members', 'id', '成员记录主键'),
                ('project_members', 'project_id', '所属项目'),
                ('project_members', 'user_id', '对应的登录用户'),
                ('project_members', 'project_role', '项目内角色，如投标负责人、商务、财务'),
                ('project_members', 'created_at', '加入项目的时间'),
                ('archive_assets', '', '企业档案表，集中保存可复用的证照、业绩、人员、财务、信用和模板'),
                ('archive_assets', 'id', '档案主键'),
                ('archive_assets', 'asset_type', '档案类型：证照、业绩、人员、财务、信用、模板'),
                ('archive_assets', 'title', '档案名称'),
                ('archive_assets', 'holder_name', '持有主体或人员姓名'),
                ('archive_assets', 'valid_until', '有效期截止，空表示未登记'),
                ('archive_assets', 'confidentiality', '密级，默认 internal；报价和财务应单独标高'),
                ('archive_assets', 'scope_note', '适用范围说明，复用前需人工核对'),
                ('archive_assets', 'source_project', '来源项目名称，历史材料不能自动当成当前有效材料'),
                ('archive_assets', 'stored_name', '档案文件在服务器上的保存名，可为空'),
                ('archive_assets', 'last_verified_at', '最近一次人工核验时间'),
                ('archive_assets', 'created_at', '建档时间'),
                ('material_tasks', '', '材料任务表，把招标要求分派到部门和责任人'),
                ('material_tasks', 'id', '任务主键'),
                ('material_tasks', 'project_id', '所属项目'),
                ('material_tasks', 'requirement_id', '对应的招标要求'),
                ('material_tasks', 'department', '责任部门'),
                ('material_tasks', 'assignee_id', '责任人，对应登录用户'),
                ('material_tasks', 'due_at', '任务截止日期'),
                ('material_tasks', 'task_status', '任务状态：open、submitted、done、recheck'),
                ('material_tasks', 'created_at', '任务创建时间'),
                ('task_files', '', '任务证明文件表，保存责任人为完成任务上传的材料'),
                ('task_files', 'id', '证明文件主键'),
                ('task_files', 'task_id', '所属材料任务'),
                ('task_files', 'archive_asset_id', '若复用企业档案，指向档案；新上传则可为空'),
                ('task_files', 'filename', '原始文件名'),
                ('task_files', 'stored_name', '服务器保存名'),
                ('task_files', 'uploaded_by', '上传人'),
                ('task_files', 'created_at', '上传时间'),
                ('clarifications', '', '澄清补遗表，登记答疑、澄清和补遗及其变更类型'),
                ('clarifications', 'id', '澄清补遗主键'),
                ('clarifications', 'project_id', '所属项目'),
                ('clarifications', 'document_id', '对应上传的澄清或补遗文件'),
                ('clarifications', 'title', '澄清或补遗标题'),
                ('clarifications', 'change_type', '变更类型：added、changed、revoked'),
                ('clarifications', 'received_at', '收到时间'),
                ('clarifications', 'summary', '变更摘要，由人工确认'),
                ('clarifications', 'created_at', '登记时间'),
                ('clarification_impacts', '', '补遗影响表，标明一份补遗影响了哪些要求'),
                ('clarification_impacts', 'id', '影响记录主键'),
                ('clarification_impacts', 'clarification_id', '哪一份澄清或补遗'),
                ('clarification_impacts', 'requirement_id', '受影响的招标要求'),
                ('clarification_impacts', 'impact_note', '影响说明'),
                ('clarification_impacts', 'needs_recheck', '1 表示已完成任务需要重新检查，0 表示不需要'),
                ('audit_events', '', '审计表，记录查看、下载、修改、确认和导出，不作为审批结论'),
                ('audit_events', 'id', '审计主键'),
                ('audit_events', 'project_id', '相关项目，可为空'),
                ('audit_events', 'user_id', '操作人'),
                ('audit_events', 'action', '动作：view、download、update、confirm、export'),
                ('audit_events', 'target_type', '操作对象类型，如 requirement、task_file'),
                ('audit_events', 'target_id', '操作对象主键'),
                ('audit_events', 'detail', '补充说明'),
                ('audit_events', 'created_at', '操作时间');

            CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);
            CREATE INDEX IF NOT EXISTS idx_requirements_project_id ON requirements(project_id);
            CREATE INDEX IF NOT EXISTS idx_requirements_status ON requirements(status);
            CREATE INDEX IF NOT EXISTS idx_project_members_project ON project_members(project_id);
            CREATE INDEX IF NOT EXISTS idx_material_tasks_project ON material_tasks(project_id);
            CREATE INDEX IF NOT EXISTS idx_audit_events_project ON audit_events(project_id);
            """
        )
