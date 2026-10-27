# 招投标材料智能编制与核验平台

## 当前版本

阶段 1 本地测试版：登录、项目管理、招标文件导入、规则抽取要求矩阵、人工确认。

## 本地运行

```powershell
pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload
```

另开一个终端启动前端。技术栈与提水工程项目相同：Vue 3、Vite、TypeScript、Element Plus、Vue Router。

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5174`。5173 留给提水工程项目。接口由 Vite 转发到 `http://127.0.0.1:8000`。

## 当前页面

- 登录页，测试账号见 [测试账号速查](./测试账号速查.md)
- 项目列表与新建项目
- 招标文件上传
- 要求矩阵查看、确认、不适用和人工新增
- 材料任务创建与部门分派（阶段 2 第一版）
- 企业档案登记接口（阶段 2 第一版）
- LangGraph 任务编排骨架（规则模式，不调用外部模型）
- 文件解析状态与人工处理提示

## 当前边界

- 不调用外部模型
- Agent 编排预留 LangGraph，组件层预留 LangChain；当前版本默认关闭外部模型
- 规则抽取结果必须人工确认
- 扫描 PDF 不做 OCR，不猜测正文
- 当前使用 SQLite 本地数据库，数据库说明见 `backend/app/db.py`

## 开发文档

- [测试账号速查](./测试账号速查.md)
- [后端接口调试教程](./后端接口调试教程.md)
- [开发问题与解决方案](./开发问题与解决方案.md)
- [更新日志](./更新日志.md)
- [项目规划书](./项目规划书.md)

## 数据与安全

真实招标文件、报价、财务资料和客户材料不得提交到 Git。仅使用 `samples/` 中的脱敏样例。
