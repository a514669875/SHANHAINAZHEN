import request from './request'

export interface TemplateStructure {
  path: string
  files: string[]
}

export interface TemplateConfig {
  word_templates_dir: string
}

export function getTemplateConfig(): Promise<TemplateConfig> {
  return request.get('/templates/config')
}

export function updateTemplateConfig(wordTemplatesDir: string): Promise<{ message: string; word_templates_dir: string }> {
  return request.put('/templates/config', { word_templates_dir: wordTemplatesDir })
}

export function getTemplateStructure(): Promise<TemplateStructure[]> {
  return request.get('/templates/structure')
}

export function uploadTemplate(
  file: File,
  fundingType: string,
  projectType: string,
  procurementType: string,
  procurementMethod: string
): Promise<{ message: string; path: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('funding_type', fundingType)
  form.append('project_type', projectType)
  form.append('procurement_type', procurementType)
  form.append('procurement_method', procurementMethod)
  return request.post('/templates/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
