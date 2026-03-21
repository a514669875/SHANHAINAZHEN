import request from './request'

export interface LedgerItem {
  id: number
  contract_number: string
  group_type: string
  procurement_method: string
  department: string
  project_number: string
  project_name: string
  procurement_name: string
  supplier: string
  contract_price: number
  sign_date: string
  content: string
  control_price: number
  funding_source: string
  officer: string
  funding_type: string
  parent_contract_number: string
  supplement_contracts: string
  pdf_preview_path?: string
}

export function listLedger(params: {
  keyword?: string
  page?: number
  /** 0 = 不分页，一次返回全部 */
  page_size?: number
  sort_by?: string
  sort_order?: string
  funding_type?: string
  group_type?: string
  procurement_method?: string
}): Promise<{ items: LedgerItem[]; total: number }> {
  return request.get('/ledger', { params })
}

export function exportLedgerExcel(ids: number[]): Promise<Blob> {
  if (!ids || ids.length === 0) {
    return Promise.reject(new Error('请先勾选要导出的台账项'))
  }
  return request.get('/ledger/export/excel', {
    params: { ids: ids.join(',') },
    responseType: 'blob',
  })
}

export function importLedgerExcel(file: File): Promise<{ created: number }> {
  const form = new FormData()
  form.append('file', file)
  return request.post('/ledger/import/excel', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
