import request from './request'
import type { User } from './types'

export interface UserCreate {
  username: string
  password: string
  role?: string
  real_name?: string
  phone?: string
  email?: string
  computer_name?: string
  computer_ip?: string
  file_share_path?: string
}

export interface UserUpdate {
  role?: string
  real_name?: string
  phone?: string
  email?: string
  computer_name?: string
  computer_ip?: string
  file_share_path?: string
  is_active?: boolean
}

export function listUsers(): Promise<User[]> {
  return request.get('/users')
}

export function createUser(data: UserCreate): Promise<User> {
  return request.post('/users', data)
}

export function updateUser(id: number, data: UserUpdate): Promise<User> {
  return request.put(`/users/${id}`, data)
}

export function deleteUser(id: number): Promise<void> {
  return request.delete(`/users/${id}`)
}
