import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  const storedUser = localStorage.getItem('user')
  const viewingAs = localStorage.getItem('viewing_as_agent')
  const isDemo = localStorage.getItem('demo_mode') === 'true'
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (viewingAs) {
    config.headers['X-View-As-Agent'] = viewingAs
    config.headers['X-Real-User-Role'] = 'manager'
  }
  if (isDemo) {
    config.headers['X-Demo-Mode'] = 'true'
  }
  if (storedUser) {
    try {
      const u = JSON.parse(storedUser)
      if (u.id) config.headers['X-User-Id'] = String(u.id)
      if (u.role) config.headers['X-User-Role'] = u.role
      if (u.email) config.headers['X-User-Email'] = u.email
      if (u.name) config.headers['X-User-Name'] = u.name
    } catch (e) {}
  }
  return config
})

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && localStorage.getItem('token')) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default apiClient
