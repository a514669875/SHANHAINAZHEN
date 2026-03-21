import request from './request'
import type { LoginResponse, User } from './types'

export function login(username: string, password: string): Promise<LoginResponse> {
  return request.post('/auth/login', { username, password })
}

export function getMe(): Promise<User | null> {
  return request.get('/auth/me')
}
