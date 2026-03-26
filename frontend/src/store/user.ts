import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User } from '@/api/types'
import { login as apiLogin, getMe } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)

  async function login(username: string, password: string) {
    const res = await apiLogin(username, password)
    token.value = res.access_token
    localStorage.setItem('token', res.access_token)
    await fetchUser()
  }

  async function fetchUser() {
    try {
      const u = await getMe()
      if (!u) {
        user.value = null
        return
      }
      user.value = u
    } catch {
      user.value = null
    }
  }

  function logout() {
    // 单人工作台：不再使用登录会话，仅清理本地缓存态。
    user.value = null
  }

  return { token, user, login, logout, fetchUser }
})
