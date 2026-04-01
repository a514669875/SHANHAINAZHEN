/**
 * 全链路实时同步 - 事件类型定义
 * 与 PRD 8.23、development 2.4 保持一致
 */

export const EventType = {
  // 项目
  PROJECT_CREATED: 'PROJECT_CREATED',
  PROJECT_UPDATED: 'PROJECT_UPDATED',
  PROJECT_DELETED: 'PROJECT_DELETED',
  // 采购
  PROCUREMENT_CREATED: 'PROCUREMENT_CREATED',
  PROCUREMENT_UPDATED: 'PROCUREMENT_UPDATED',
  PROCUREMENT_DELETED: 'PROCUREMENT_DELETED',
  // 归档文件
  FILE_UPLOADED: 'FILE_UPLOADED',
  FILE_DELETED: 'FILE_DELETED',
  // 流程文件
  PROCESS_FILE_CREATED: 'PROCESS_FILE_CREATED',
  PROCESS_FILE_UPDATED: 'PROCESS_FILE_UPDATED',
  PROCESS_FILE_DELETED: 'PROCESS_FILE_DELETED',
  PROCESS_FILE_SYNC_STATUS_CHANGED: 'PROCESS_FILE_SYNC_STATUS_CHANGED',
  // 模板
  TEMPLATE_UPDATED: 'TEMPLATE_UPDATED',
  // 配置
  CONFIG_CHANGED: 'CONFIG_CHANGED',
  // 用户
  USER_CREATED: 'USER_CREATED',
  USER_UPDATED: 'USER_UPDATED',
  USER_DELETED: 'USER_DELETED',
  // 台账
  LEDGER_CREATED: 'LEDGER_CREATED',
  LEDGER_UPDATED: 'LEDGER_UPDATED',
  // 权限
  PERMISSION_CHANGED: 'PERMISSION_CHANGED',
} as const

export type EventTypeValue = (typeof EventType)[keyof typeof EventType]

export interface RealtimeEvent {
  type: EventTypeValue | string
  payload: Record<string, unknown>
  timestamp: string
}

export type SubscribeScope =
  | 'project_list'
  | 'procurement_list'
  | 'procurement_detail'
  | 'archive'
  | 'ledger'
  | 'admin'

export interface SubscribeContext {
  project_id?: number
  procurement_id?: number
  scope?: SubscribeScope
}

export interface SubscribeMessage {
  action: 'subscribe' | 'unsubscribe'
  context?: SubscribeContext
}
