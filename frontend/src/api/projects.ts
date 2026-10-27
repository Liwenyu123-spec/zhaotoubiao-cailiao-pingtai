import { api } from './http'

export interface Project {
  id: number
  name: string
  code: string
  bidder: string
  deadline: string
  created_at: string
  requirement_count?: number
  pending_count?: number
}

export interface BidDocument {
  id: number
  filename: string
  parse_status: string
  parse_note: string
  page_count: number
}

export interface Requirement {
  id: number
  category: string
  content: string
  source_file: string
  source_location: string
  confidence: string
  status: 'pending' | 'confirmed' | 'not_applicable'
  note: string
}
export interface MaterialTask {
  id: number
  requirement_id: number
  requirement_content: string
  department: string
  assignee_name?: string
  due_at: string
  task_status: 'open' | 'submitted' | 'done' | 'recheck'
}
export interface TaskSuggestion {
  requirement_id: number
  department: string
  reason: string
}

export interface ProjectDetail {
  project: Project
  documents: BidDocument[]
  requirements: Requirement[]
  tasks: MaterialTask[]
}

export function listProjects() {
  return api<Project[]>('/api/projects')
}
export interface ProjectUser { id: number; username: string; display_name: string; role: string }
export function listUsers() { return api<ProjectUser[]>('/api/users') }

export function createProject(body: Pick<Project, 'name' | 'code' | 'bidder' | 'deadline'>) {
  return api<Project>('/api/projects', { method: 'POST', body: JSON.stringify(body) })
}

export function getProject(id: number) {
  return api<ProjectDetail>(`/api/projects/${id}`)
}

export function uploadDocument(projectId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  return api<{ extracted: number; parse_note: string }>(`/api/projects/${projectId}/documents`, {
    method: 'POST',
    body: form,
  })
}

export function addRequirement(projectId: number, body: { category: string; content: string }) {
  return api<Requirement>(`/api/projects/${projectId}/requirements`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function patchRequirement(id: number, body: { status: Requirement['status'] }) {
  return api<Requirement>(`/api/requirements/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function createTask(projectId: number, body: { requirement_id: number; department: string; assignee_id?: number; due_at: string }) {
  return api<MaterialTask>(`/api/projects/${projectId}/tasks`, { method: 'POST', body: JSON.stringify(body) })
}

export function patchTask(id: number, body: { task_status: MaterialTask['task_status'] }) {
  return api<MaterialTask>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
}

export function uploadTaskFile(taskId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  return api<{ id: number; filename: string }>(`/api/tasks/${taskId}/files`, { method: 'POST', body: form })
}

export function generateTaskPlan(projectId: number) {
  return api<{ suggestions: TaskSuggestion[]; needs_human_review: boolean; trace: string[]; model_used: boolean }>(
    `/api/projects/${projectId}/agent/task-plan`, { method: 'POST' },
  )
}

export function runProjectChecks(projectId: number) {
  return api<{ total_requirements: number; problem_count: number; pass: boolean; items: Array<{ id: number; category: string; content: string; problems: string[] }> }>(
    `/api/projects/${projectId}/checks`,
  )
}

export function exportProjectChecks(projectId: number) {
  const token = localStorage.getItem('access_token')
  return fetch(`/api/projects/${projectId}/checks/export`, { headers: token ? { Authorization: `Bearer ${token}` } : {} }).then((response) => {
    if (!response.ok) throw new Error('导出失败')
    return response.blob()
  })
}

export interface Clarification { id: number; title: string; change_type: string; received_at: string; summary: string }
export function listClarifications(projectId: number) { return api<Clarification[]>(`/api/projects/${projectId}/clarifications`) }
export function createClarification(projectId: number, body: Omit<Clarification, 'id'>) {
  return api<Clarification>(`/api/projects/${projectId}/clarifications`, { method: 'POST', body: JSON.stringify(body) })
}
export function createClarificationImpact(clarificationId: number, body: { requirement_id: number; impact_note: string }) {
  return api(`/api/clarifications/${clarificationId}/impacts`, { method: 'POST', body: JSON.stringify({ ...body, needs_recheck: true }) })
}
export interface AuditEvent { id: number; action: string; target_type: string; target_id?: number; detail: string; created_at: string }
export function listAuditEvents(projectId: number) { return api<AuditEvent[]>(`/api/projects/${projectId}/audit-events`) }
export function getPackageManifest(projectId: number) { return api<Record<string, unknown>>(`/api/projects/${projectId}/package-manifest`) }
