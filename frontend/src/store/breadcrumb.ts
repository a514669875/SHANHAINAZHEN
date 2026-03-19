import { defineStore } from 'pinia'
import { ref } from 'vue'

/** Breadcrumb context for dynamic path display (UI 3.5) */
export const useBreadcrumbStore = defineStore('breadcrumb', () => {
  const projectId = ref<number | null>(null)
  const projectNumber = ref<string>('') // 工程编号
  const projectName = ref<string>('')
  const procurementId = ref<number | null>(null)
  const procurementName = ref<string>('')
  const isAddProcurementOpen = ref(false)
  const activeFileTab = ref<'process' | 'archive'>('process')
  const ledgerContractNumber = ref<string>('')

  function setProcurementContext(p: {
    projectId?: number | null
    projectNumber?: string
    projectName?: string
    procurementId?: number | null
    procurementName?: string
    isAddProcurementOpen?: boolean
    activeFileTab?: 'process' | 'archive'
  }) {
    if (p.projectId !== undefined) projectId.value = p.projectId
    if (p.projectNumber !== undefined) projectNumber.value = p.projectNumber
    if (p.projectName !== undefined) projectName.value = p.projectName
    if (p.procurementId !== undefined) procurementId.value = p.procurementId
    if (p.procurementName !== undefined) procurementName.value = p.procurementName
    if (p.isAddProcurementOpen !== undefined) isAddProcurementOpen.value = p.isAddProcurementOpen
    if (p.activeFileTab !== undefined) activeFileTab.value = p.activeFileTab
  }

  function setArchiveContext(p: {
    projectId?: number | null
    projectNumber?: string
    projectName?: string
    procurementId?: number | null
    procurementName?: string
  }) {
    if (p.projectId !== undefined) projectId.value = p.projectId
    if (p.projectNumber !== undefined) projectNumber.value = p.projectNumber
    if (p.projectName !== undefined) projectName.value = p.projectName
    if (p.procurementId !== undefined) procurementId.value = p.procurementId
    if (p.procurementName !== undefined) procurementName.value = p.procurementName
  }

  function setLedgerContext(contractNumber?: string) {
    ledgerContractNumber.value = contractNumber || ''
  }

  function clear() {
    projectId.value = null
    projectNumber.value = ''
    projectName.value = ''
    procurementId.value = null
    procurementName.value = ''
    isAddProcurementOpen.value = false
    activeFileTab.value = 'process'
    ledgerContractNumber.value = ''
  }

  return {
    projectId,
    projectNumber,
    projectName,
    procurementId,
    procurementName,
    isAddProcurementOpen,
    activeFileTab,
    ledgerContractNumber,
    setProcurementContext,
    setArchiveContext,
    setLedgerContext,
    clear,
  }
})
