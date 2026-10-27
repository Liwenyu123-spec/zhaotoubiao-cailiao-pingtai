import { api } from './http'

export interface ArchiveAsset {
  id: number
  asset_type: string
  title: string
  holder_name: string
  valid_until: string
  confidentiality: string
  scope_note: string
  source_project: string
}

export function listArchiveAssets() {
  return api<ArchiveAsset[]>('/api/archive-assets')
}

export function createArchiveAsset(body: Omit<ArchiveAsset, 'id'>) {
  return api<ArchiveAsset>('/api/archive-assets', { method: 'POST', body: JSON.stringify(body) })
}
