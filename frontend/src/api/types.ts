export interface User {
  id: number
  username: string
  role: string
  real_name?: string
  phone?: string
  email?: string
  computer_name?: string
  is_active: boolean
  create_time?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}
