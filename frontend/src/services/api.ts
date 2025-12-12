import axios from 'axios'

// Sử dụng biến môi trường hoặc fallback về relative path (cho nginx proxy)
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: async (email: string, password: string) => {
    const formData = new URLSearchParams()
    formData.append('username', email)
    formData.append('password', password)
    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    return response.data
  },
  register: async (data: { email: string; name: string; password: string }) => {
    const response = await api.post('/auth/register', data)
    return response.data
  },
  getCurrentUser: async () => {
    const response = await api.get('/auth/me')
    return response.data
  },
}

// Documents API
export const documentsApi = {
  list: async (params?: {
    page?: number
    page_size?: number
    project_id?: string
    status?: string
    search?: string
  }) => {
    const response = await api.get('/documents', { params })
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/documents/${id}`)
    return response.data
  },
  upload: async (file: File, data: {
    title?: string
    project_id?: string
    category_id?: string
    tags?: string
  }) => {
    const formData = new FormData()
    formData.append('file', file)
    if (data.title) formData.append('title', data.title)
    if (data.project_id) formData.append('project_id', data.project_id)
    if (data.category_id) formData.append('category_id', data.category_id)
    if (data.tags) formData.append('tags', data.tags)

    const response = await api.post('/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
  update: async (id: string, data: any) => {
    const response = await api.put(`/documents/${id}`, data)
    return response.data
  },
  delete: async (id: string) => {
    const response = await api.delete(`/documents/${id}`)
    return response.data
  },
  download: async (id: string) => {
    const response = await api.get(`/documents/${id}/download`)
    return response.data
  },
}

// Search API
export const searchApi = {
  search: async (query: {
    query: string
    project_id?: string
    top_k?: number
  }) => {
    const response = await api.post('/search', query)
    return response.data
  },
  suggestions: async (q: string) => {
    const response = await api.get('/search/suggestions', { params: { q } })
    return response.data
  },
}

// Generate API
export const generateApi = {
  generate: async (data: FormData) => {
    const response = await api.post('/generate', data, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
  getTemplates: async () => {
    const response = await api.get('/generate/templates')
    return response.data
  },
  getJobStatus: async (jobId: string) => {
    const response = await api.get(`/generate/${jobId}`)
    return response.data
  },
  getResult: async (jobId: string) => {
    const response = await api.get(`/generate/${jobId}/result`)
    return response.data
  },
  getExportFormats: async (jobId: string) => {
    const response = await api.get(`/generate/${jobId}/export-formats`)
    return response.data
  },
  download: async (jobId: string, format: string) => {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/generate/${jobId}/download?format=${format}`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
    if (!response.ok) {
      throw new Error('Download failed')
    }
    const blob = await response.blob()
    const contentDisposition = response.headers.get('content-disposition')
    let filename = `document.${format}`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="(.+)"/)
      if (match) {
        filename = match[1]
      }
    }
    return { blob, filename }
  },
}

// Projects API
export const projectsApi = {
  list: async () => {
    const response = await api.get('/projects')
    return response.data
  },
  create: async (data: { name: string; description?: string }) => {
    const response = await api.post('/projects', data)
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/projects/${id}`)
    return response.data
  },
}

// Templates API
export const templatesApi = {
  list: async (params?: { document_type?: string; active_only?: boolean }) => {
    const response = await api.get('/templates', { params })
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/templates/${id}`)
    return response.data
  },
  upload: async (data: {
    name: string
    document_type: string
    description?: string
    is_default?: boolean
    template_file: File
  }) => {
    const formData = new FormData()
    formData.append('name', data.name)
    formData.append('document_type', data.document_type)
    if (data.description) formData.append('description', data.description)
    formData.append('is_default', String(data.is_default || false))
    formData.append('template_file', data.template_file)

    const response = await api.post('/templates/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
  update: async (id: string, data: any) => {
    const response = await api.put(`/templates/${id}`, data)
    return response.data
  },
  delete: async (id: string) => {
    const response = await api.delete(`/templates/${id}`)
    return response.data
  },
  setDefault: async (id: string) => {
    const response = await api.post(`/templates/${id}/set-default`)
    return response.data
  },
}

// Analytics API
export const analyticsApi = {
  getSummary: async () => {
    const response = await api.get('/analytics/summary')
    return response.data
  },
  getDocumentStats: async (projectId?: string) => {
    const response = await api.get('/analytics/documents', { params: { project_id: projectId } })
    return response.data
  },
  getActivityStats: async (days = 7) => {
    const response = await api.get('/analytics/activity', { params: { days } })
    return response.data
  },
  getWorkflowStats: async (days = 30) => {
    const response = await api.get('/analytics/workflow', { params: { days } })
    return response.data
  },
  getStorageStats: async () => {
    const response = await api.get('/analytics/storage')
    return response.data
  },
}

// Notifications API
export const notificationsApi = {
  list: async (params?: { unread_only?: boolean; skip?: number; limit?: number }) => {
    const response = await api.get('/notifications', { params })
    return response.data
  },
  getUnreadCount: async () => {
    const response = await api.get('/notifications/unread-count')
    return response.data
  },
  markAsRead: async (id: string) => {
    const response = await api.post(`/notifications/${id}/read`)
    return response.data
  },
  markAllAsRead: async () => {
    const response = await api.post('/notifications/read-all')
    return response.data
  },
  delete: async (id: string) => {
    const response = await api.delete(`/notifications/${id}`)
    return response.data
  },
}

// Audit API
export const auditApi = {
  list: async (params?: {
    action?: string
    user_id?: string
    resource_type?: string
    resource_id?: string
    from_date?: string
    to_date?: string
    skip?: number
    limit?: number
  }) => {
    const response = await api.get('/audit', { params })
    return response.data
  },
  getDocumentHistory: async (documentId: string, limit = 100) => {
    const response = await api.get(`/audit/document/${documentId}`, { params: { limit } })
    return response.data
  },
  getMyActivity: async (days = 30, limit = 50) => {
    const response = await api.get('/audit/my-activity', { params: { days, limit } })
    return response.data
  },
  getSummary: async (days = 7) => {
    const response = await api.get('/audit/summary', { params: { days } })
    return response.data
  },
  getActions: async () => {
    const response = await api.get('/audit/actions')
    return response.data
  },
}

// Prompt Manager API
export const promptsApi = {
  list: async (params?: {
    category?: string
    is_active?: boolean
    search?: string
    skip?: number
    limit?: number
  }) => {
    const response = await api.get('/prompts', { params })
    return response.data
  },
  get: async (id: string) => {
    const response = await api.get(`/prompts/${id}`)
    return response.data
  },
  create: async (data: {
    name: string
    description?: string
    category: string
    content: string
    system_prompt?: string
    variables?: any[]
    model_config?: any
    output_format?: string
    is_default?: boolean
  }) => {
    const response = await api.post('/prompts', data)
    return response.data
  },
  update: async (id: string, data: any) => {
    const response = await api.put(`/prompts/${id}`, data)
    return response.data
  },
  delete: async (id: string) => {
    const response = await api.delete(`/prompts/${id}`)
    return response.data
  },
  getCategories: async () => {
    const response = await api.get('/prompts/categories')
    return response.data
  },
  getVersions: async (id: string) => {
    const response = await api.get(`/prompts/${id}/versions`)
    return response.data
  },
  restoreVersion: async (templateId: string, versionId: string) => {
    const response = await api.post(`/prompts/${templateId}/versions/${versionId}/restore`)
    return response.data
  },
  preview: async (content: string, variables: Record<string, string>) => {
    const response = await api.post('/prompts/preview', { content, variables })
    return response.data
  },
  test: async (data: { template_id?: string; content?: string; variables?: Record<string, string> }) => {
    const response = await api.post('/prompts/test', data)
    return response.data
  },
}
