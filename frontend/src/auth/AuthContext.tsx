import { createContext, useContext, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../api/client'
import type { User } from '../api/types'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  loginError: string | null
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [loginError, setLoginError] = useState<string | null>(null)

  const { data: user, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await api.get<User>('/api/auth/me')
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    retry: false,
    staleTime: Infinity,
  })

  async function login(username: string, password: string) {
    setLoginError(null)
    try {
      const loggedInUser = await api.post<User>('/api/auth/login', { username, password })
      queryClient.setQueryData(['me'], loggedInUser)
    } catch (e) {
      setLoginError(e instanceof ApiError ? e.message : 'Sign-in failed.')
      throw e
    }
  }

  async function logout() {
    await api.post('/api/auth/logout')
    queryClient.setQueryData(['me'], null)
    queryClient.clear()
  }

  return (
    <AuthContext.Provider value={{ user: user ?? null, isLoading, login, logout, loginError }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
