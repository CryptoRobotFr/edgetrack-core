import { useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/contexts/AuthContext"

export function LogoutPage() {
  const navigate = useNavigate()
  const { logout } = useAuth()

  useEffect(() => {
    logout()
    navigate("/login", { replace: true })
  }, [navigate, logout])

  // Brief loading state while redirecting
  return null
}

export default LogoutPage
