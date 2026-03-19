import request from './request'

export interface SupplierInput {
  supplier_name: string
  contact_person: string
  contact_phone: string
  business_scope: string
  tax_rate: string
  quoted_price: number
}

export interface ProcurementCreate {
  project_id: number
  is_draft?: boolean
  step1: {
    procurement_type: string
    procurement_method: string
  }
  step2: {
    procurement_type: string
    procurement_method: string
    leibie?: string
    project_name: string
    project_number: string
    project_id: string
    construction_unit: string
    total_contract_price: number
    project_address: string
    department: string
    site_manager: string
    site_manager_phone: string
    procurement_project_name: string
    content: string
    control_price: number
    tax_method?: string
    sign_date?: string
  }
  suppliers: SupplierInput[]
  time_records: { flow_name: string; date_val: string }[]
  parent_contract_id?: number
  section_a_name?: string
  section_b_name?: string
}

export interface Procurement {
  id: number
  project_id: number
  procurement_type: string
  procurement_method: string
  project_name: string
  content: string
  control_price: number
  contract_number: string
  supplier: string
  contract_price: number
  sign_date: string
}

export function listProcurements(projectId: number, forList = true): Promise<Procurement[]> {
  return request.get('/procurements', { params: { project_id: projectId, for_list: forList } })
}

export function getParentContractOptions(
  projectId: number,
  procurementType: string,
  isDualContract = false
): Promise<{ id: number; contract_number: string; project_name: string; content: string; contract_section: string }[]> {
  return request.get('/procurements/parent-contract-options', {
    params: { project_id: projectId, procurement_type: procurementType, is_dual_contract: isDualContract },
  })
}

export function getProcurement(id: number): Promise<any> {
  return request.get(`/procurements/${id}`)
}

export function createProcurement(data: ProcurementCreate): Promise<{ message: string; procurement_id?: number; procurement_ids?: number[] }> {
  return request.post('/procurements', data)
}

export function updateProcurement(
  id: number,
  data: { project_name?: string; content?: string; form_data?: string; suppliers?: SupplierInput[]; supplement_amount?: number; supplement_content?: string },
  options?: { draft_only?: boolean }
): Promise<any> {
  return request.put(`/procurements/${id}`, data, {
    params: options?.draft_only ? { draft_only: true } : undefined,
  })
}

export function deleteProcurement(id: number): Promise<{ message: string; warnings?: string[] }> {
  return request.delete(`/procurements/${id}`)
}
