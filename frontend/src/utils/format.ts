/**
 * 日期格式：Y.M.D，例 2026.3.13（月、日无前导零）
 */
export function formatDateYMD(val: string | number | Date | null | undefined): string {
  if (val == null || val === '') return '-'
  if (typeof val === 'string' && /^\d{4}\.\d{1,2}\.\d{1,2}$/.test(val)) return val
  const d = typeof val === 'string' ? new Date(val.replace(/-/g, '/').replace(/\./g, '/')) : val instanceof Date ? val : new Date(val)
  if (isNaN(d.getTime())) return String(val)
  const y = d.getFullYear()
  const m = d.getMonth() + 1
  const day = d.getDate()
  return `${y}.${m}.${day}`
}

/** 数值展示：null/undefined 显示为 "/" */
export function formatNumeric(val: number | null | undefined): string {
  if (val == null || val === '' || (typeof val === 'number' && isNaN(val))) return '/'
  return String(val)
}

/** 数值展示（带千分位）：null 显示为 "/" */
export function formatNumericLocale(val: number | null | undefined): string {
  if (val == null || val === '' || (typeof val === 'number' && isNaN(val))) return '/'
  return Number(val).toLocaleString()
}

/** 合同价等金额：保留两位小数，末位零也保留 */
export function formatContractPrice(val: number | null | undefined): string {
  if (val == null || val === '' || (typeof val === 'number' && isNaN(val))) return '/'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
