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

export function createTask(projectId: number, body: { requirement_id: number; department: string; due_at: string }) {
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
