import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import {
  DocumentTextIcon,
  CloudArrowUpIcon,
  TrashIcon,
  StarIcon,
} from '@heroicons/react/24/outline'
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid'
import { templatesApi, generateApi } from '../services/api'

interface Template {
  id: string
  name: string
  document_type: string
  description?: string
  is_active: boolean
  is_default: boolean
  created_at: string
}

export default function Templates() {
  const queryClient = useQueryClient()
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadData, setUploadData] = useState({
    name: '',
    document_type: 'srs',
    description: '',
    is_default: false,
  })
  const [uploadFile, setUploadFile] = useState<File | null>(null)

  // Fetch templates
  const { data: templatesData, isLoading } = useQuery({
    queryKey: ['templates'],
    queryFn: () => templatesApi.list(),
  })

  // Fetch document types
  const { data: documentTypes } = useQuery({
    queryKey: ['generate-templates'],
    queryFn: () => generateApi.getTemplates(),
  })

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (data: {
      name: string
      document_type: string
      description?: string
      is_default?: boolean
      template_file: File
    }) => templatesApi.upload(data),
    onSuccess: () => {
      toast.success('Template uploaded successfully!')
      queryClient.invalidateQueries({ queryKey: ['templates'] })
      setShowUploadModal(false)
      resetUploadForm()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Upload failed')
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => templatesApi.delete(id),
    onSuccess: () => {
      toast.success('Template deleted')
      queryClient.invalidateQueries({ queryKey: ['templates'] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Delete failed')
    },
  })

  // Set default mutation
  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => templatesApi.setDefault(id),
    onSuccess: () => {
      toast.success('Default template updated')
      queryClient.invalidateQueries({ queryKey: ['templates'] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to set default')
    },
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setUploadFile(acceptedFiles[0])
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/markdown': ['.md'],
      'text/plain': ['.txt'],
    },
    maxFiles: 1,
  })

  const resetUploadForm = () => {
    setUploadData({
      name: '',
      document_type: 'srs',
      description: '',
      is_default: false,
    })
    setUploadFile(null)
  }

  const handleUpload = () => {
    if (!uploadFile) {
      toast.error('Please select a template file')
      return
    }
    if (!uploadData.name.trim()) {
      toast.error('Please enter a template name')
      return
    }

    uploadMutation.mutate({
      ...uploadData,
      template_file: uploadFile,
    })
  }

  const templates: Template[] = templatesData?.templates || []

  // Group templates by document type
  const templatesByType = templates.reduce((acc: Record<string, Template[]>, template) => {
    const type = template.document_type
    if (!acc[type]) acc[type] = []
    acc[type].push(template)
    return acc
  }, {})

  return (
    <div>
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Document Templates</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage custom templates for document generation
          </p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="btn-primary"
        >
          <CloudArrowUpIcon className="h-5 w-5 mr-2" />
          Upload Template
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent"></div>
          <p className="mt-2 text-gray-500">Loading templates...</p>
        </div>
      ) : templates.length === 0 ? (
        <div className="card text-center py-12">
          <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">No custom templates</h3>
          <p className="mt-2 text-gray-500">
            Upload your first template to start generating documents with custom formats.
          </p>
          <button
            onClick={() => setShowUploadModal(true)}
            className="mt-4 btn-primary"
          >
            Upload Template
          </button>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(templatesByType).map(([type, typeTemplates]) => (
            <div key={type} className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 capitalize">
                {type.replace('_', ' ')} Templates
              </h2>
              <div className="space-y-3">
                {typeTemplates.map((template) => (
                  <div
                    key={template.id}
                    className={`flex items-center justify-between p-4 rounded-lg border ${
                      template.is_default
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center space-x-4">
                      <DocumentTextIcon className="h-8 w-8 text-gray-400" />
                      <div>
                        <div className="flex items-center space-x-2">
                          <h3 className="font-medium text-gray-900">{template.name}</h3>
                          {template.is_default && (
                            <span className="px-2 py-0.5 text-xs bg-primary-100 text-primary-700 rounded-full">
                              Default
                            </span>
                          )}
                        </div>
                        {template.description && (
                          <p className="text-sm text-gray-500">{template.description}</p>
                        )}
                        <p className="text-xs text-gray-400 mt-1">
                          Created: {new Date(template.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setDefaultMutation.mutate(template.id)}
                        className={`p-2 rounded-lg transition-colors ${
                          template.is_default
                            ? 'text-yellow-500'
                            : 'text-gray-400 hover:text-yellow-500 hover:bg-gray-100'
                        }`}
                        title={template.is_default ? 'Default template' : 'Set as default'}
                      >
                        {template.is_default ? (
                          <StarIconSolid className="h-5 w-5" />
                        ) : (
                          <StarIcon className="h-5 w-5" />
                        )}
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('Are you sure you want to delete this template?')) {
                            deleteMutation.mutate(template.id)
                          }
                        }}
                        className="p-2 text-gray-400 hover:text-red-500 hover:bg-gray-100 rounded-lg transition-colors"
                        title="Delete template"
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Upload Template</h2>

            <div className="space-y-4">
              {/* Template Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Template Name *
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g., SRS Template - IEEE 830"
                  value={uploadData.name}
                  onChange={(e) => setUploadData({ ...uploadData, name: e.target.value })}
                />
              </div>

              {/* Document Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Document Type *
                </label>
                <select
                  className="input"
                  value={uploadData.document_type}
                  onChange={(e) => setUploadData({ ...uploadData, document_type: e.target.value })}
                >
                  {documentTypes?.templates?.map((t: any) => (
                    <option key={t.document_type} value={t.document_type}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  className="input"
                  rows={2}
                  placeholder="Brief description of this template..."
                  value={uploadData.description}
                  onChange={(e) => setUploadData({ ...uploadData, description: e.target.value })}
                />
              </div>

              {/* File Upload */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Template File *
                </label>
                <div
                  {...getRootProps()}
                  className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
                    isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <input {...getInputProps()} />
                  {uploadFile ? (
                    <div className="flex items-center justify-center space-x-2">
                      <DocumentTextIcon className="h-6 w-6 text-primary-500" />
                      <span className="text-sm text-gray-700">{uploadFile.name}</span>
                    </div>
                  ) : (
                    <>
                      <CloudArrowUpIcon className="mx-auto h-8 w-8 text-gray-400" />
                      <p className="mt-1 text-sm text-gray-500">
                        Drop your template file here (DOCX, PDF, MD, TXT)
                      </p>
                    </>
                  )}
                </div>
              </div>

              {/* Set as Default */}
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={uploadData.is_default}
                  onChange={(e) => setUploadData({ ...uploadData, is_default: e.target.checked })}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 rounded"
                />
                <span className="text-sm text-gray-700">Set as default template for this type</span>
              </label>
            </div>

            {/* Actions */}
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowUploadModal(false)
                  resetUploadForm()
                }}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={uploadMutation.isPending}
                className="btn-primary"
              >
                {uploadMutation.isPending ? 'Uploading...' : 'Upload Template'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
