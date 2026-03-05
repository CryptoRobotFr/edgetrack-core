import createClient, { type Middleware } from "openapi-fetch"
import type { paths } from "./schema"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"

// Callback for handling 401/403 responses (set by AuthContext)
let onUnauthorized: ((reason?: string) => void) | null = null

export function setOnUnauthorized(callback: (reason?: string) => void): void {
  onUnauthorized = callback
}

// Middleware to handle 401 and 403 (inactive user) responses globally
const authMiddleware: Middleware = {
  async onResponse({ response }) {
    if (response.status === 401 && onUnauthorized) {
      onUnauthorized()
    } else if (response.status === 403 && onUnauthorized) {
      try {
        const body = await response.clone().json()
        if (body?.type === "inactive_user") {
          onUnauthorized("account_deactivated")
        }
      } catch {
        // Not JSON or unexpected format — ignore
      }
    }
    return response
  },
}

// Public client (no auth header, no 401 handling)
export const api = createClient<paths>({
  baseUrl: API_BASE_URL,
})

// Helper to get stored tokens
export function getAccessToken(): string | null {
  return localStorage.getItem("access_token")
}

export function getRefreshToken(): string | null {
  return localStorage.getItem("refresh_token")
}

// Helper to store tokens
export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem("access_token", accessToken)
  localStorage.setItem("refresh_token", refreshToken)
}

// Helper to clear tokens (logout)
export function clearTokens(): void {
  localStorage.removeItem("access_token")
  localStorage.removeItem("refresh_token")
}

// Check if user is authenticated (has a token)
export function isAuthenticated(): boolean {
  return getAccessToken() !== null
}

// Authenticated client with 401 interception
export const authApi = createClient<paths>({
  baseUrl: API_BASE_URL,
})
authApi.use(authMiddleware)

// Add auth header middleware
const authHeaderMiddleware: Middleware = {
  async onRequest({ request }) {
    const token = getAccessToken()
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`)
    }
    return request
  },
}
authApi.use(authHeaderMiddleware)
