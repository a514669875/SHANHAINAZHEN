/**
 * 全链路实时同步 - WebSocket 订阅与事件消费
 * 与 PRD 8.23、development 2.4 保持一致
 */
import { ref, onMounted, onUnmounted, type Ref } from 'vue'
import type { RealtimeEvent, SubscribeContext } from '@/types/event_types'
import { EventType } from '@/types/event_types'

const WS_BASE = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws`

export interface UseRealtimeSyncOptions {
  /** 订阅上下文 */
  context?: SubscribeContext
  /** 事件回调：按类型更新本地 ref/reactive */
  onEvent?: (event: RealtimeEvent) => void
}

export function useRealtimeSync(options: UseRealtimeSyncOptions = {}) {
  const connected = ref(false)
  const ws = ref<WebSocket | null>(null)
  const { context, onEvent } = options

  function connect() {
    const token = localStorage.getItem('token')
    if (!token) return
    const url = `${WS_BASE}?token=${encodeURIComponent(token)}`
    const socket = new WebSocket(url)
    ws.value = socket

    socket.onopen = () => {
      connected.value = true
      if (context) {
        socket.send(
          JSON.stringify({
            action: 'subscribe',
            context: {
              project_id: context.project_id,
              procurement_id: context.procurement_id,
              scope: context.scope,
            },
          })
        )
      }
    }

    socket.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as RealtimeEvent
        onEvent?.(event)
      } catch {
        // ignore parse error
      }
    }

    socket.onclose = () => {
      connected.value = false
      ws.value = null
    }

    socket.onerror = () => {
      connected.value = false
      // 静默处理：后端未启动时 ECONNRESET 属正常，不干扰用户
    }
  }

  function disconnect() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connected.value = false
  }

  /** 更新订阅上下文（如切换 project/procurement） */
  function updateContext(newContext: SubscribeContext) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(
        JSON.stringify({
          action: 'subscribe',
          context: newContext,
        })
      )
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    connected,
    connect,
    disconnect,
    updateContext,
  }
}

/** 根据事件类型执行对应更新逻辑（供各视图组合使用） */
export function createEventHandlers(
  handlers: Partial<Record<string, (payload: Record<string, unknown>) => void>>
) {
  return (event: RealtimeEvent) => {
    const fn = handlers[event.type]
    if (fn && typeof fn === 'function') {
      fn(event.payload || {})
    }
  }
}

export { EventType }
