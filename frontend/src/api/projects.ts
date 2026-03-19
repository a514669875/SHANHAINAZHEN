import request from './request'

export interface Project {
  id: number
  funding_type: string
  project_type: string
  project_number: string
  project_id: string
  project_name: string
  department: string
  site_manager: string
  site_manager_phone: string
  construction_unit: string
  total_contract_price: number
  project_duration?: string
  funding_source: string
  project_address: string
  procurement_officers: string
  create_date?: string
}

export interface ProjectCreate {
  funding_type: string
  project_type: string
  project_number: string
  project_id: string
  project_name: string
  department: string
  site_manager: string
  site_manager_phone: string
  construction_unit: string
  total_contract_price: number
  project_duration?: string
  funding_source: string
  project_address: string
  procurement_officers: string
}

export interface ProjectUpdate extends Partial<ProjectCreate> {}

export function listProjects(params: {
  keyword?: string
  page?: number
  page_size?: number
}): Promise<Project[]> {
  return request.get('/projects', { params })
}

export function countProjects(keyword?: string): Promise<{ total: number }> {
  return request.get('/projects/count', { params: { keyword } })
}

export function getProject(id: number): Promise<Project> {
  return request.get(`/projects/${id}`)
}

export function createProject(data: ProjectCreate): Promise<Project> {
  return request.post('/projects', data)
}

export function updateProject(id: number, data: ProjectUpdate): Promise<Project> {
  return request.put(`/projects/${id}`, data)
}

export function deleteProject(id: number): Promise<void> {
  return request.delete(`/projects/${id}`)
}

export function exportProjectsExcel(ids: number[]): Promise<Blob> {
  if (!ids || ids.length === 0) {
    return Promise.reject(new Error('请先勾选要导出的工程项目'))
  }
  return request.get('/projects/export/excel', {
    params: { ids: ids.join(',') },
    responseType: 'blob',
  })
}
