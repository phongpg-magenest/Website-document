import axios from 'axios'

const API_BASE_URL = '/api/v1'

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
    const response = await fetch(`/api/v1/generate/${jobId}/download?format=${format}`, {
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
