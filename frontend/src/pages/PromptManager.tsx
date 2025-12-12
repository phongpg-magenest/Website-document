import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  PlayIcon,
  ClockIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline'
import { promptsApi } from '../services/api'

interface PromptTemplate {
  id: string
  name: string
  description: string
  category: string
  content: string
  system_prompt?: string
  variables: Array<{ name: string; description: string; required: boolean; default_value?: string }>
  model_config?: Record<string, any>
  output_format?: string
  is_active: boolean
  is_default: boolean
  created_at: string
  updated_at: string
}

interface PromptFormData {
  name: string
  description: string
  category: string
  content: string
  system_prompt: string
  variables: Array<{ name: string; description: string; required: boolean; default_value?: string }>
  output_format: string
  is_default: boolean
}

const defaultFormData: PromptFormData = {
  name: '',
  description: '',
  category: 'document_generation',
  content: '',
  system_prompt: '',
  variables: [],
  output_format: 'markdown',
  is_default: false,
}

export default function PromptManager() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isTestModalOpen, setIsTestModalOpen] = useState(false)
  const [isVersionsModalOpen, setIsVersionsModalOpen] = useState(false)
  const [selectedPrompt, setSelectedPrompt] = useState<PromptTemplate | null>(null)
  const [formData, setFormData] = useState<PromptFormData>(defaultFormData)
  const [testVariables, setTestVariables] = useState<Record<string, string>>({})
  const [testResult, setTestResult] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const queryClient = useQueryClient()

  const { data: promptsData, isLoading, error } = useQuery({
    queryKey: ['prompts', categoryFilter, searchQuery],
    queryFn: () =>
      promptsApi.list({
        category: categoryFilter || undefined,
        search: searchQuery || undefined,
      }),
  })

  const { data: categories } = useQuery({
    queryKey: ['prompt-categories'],
    queryFn: () => promptsApi.getCategories(),
  })

  const { data: versions } = useQuery({
    queryKey: ['prompt-versions', selectedPrompt?.id],
    queryFn: () => promptsApi.getVersions(selectedPrompt!.id),
    enabled: !!selectedPrompt && isVersionsModalOpen,
  })

  const createMutation = useMutation({
    mutationFn: (data: PromptFormData) => promptsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      setIsModalOpen(false)
      setFormData(defaultFormData)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<PromptFormData> }) =>
      promptsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      setIsModalOpen(false)
      setSelectedPrompt(null)
      setFormData(defaultFormData)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => promptsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })

  const testMutation = useMutation({
    mutationFn: (data: { template_id?: string; content?: string; variables?: Record<string, string> }) =>
      promptsApi.test(data),
    onSuccess: (data) => {
      setTestResult(data.result || data.error || 'Test completed')
    },
  })

  const restoreVersionMutation = useMutation({
    mutationFn: ({ templateId, versionId }: { templateId: string; versionId: string }) =>
      promptsApi.restoreVersion(templateId, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      queryClient.invalidateQueries({ queryKey: ['prompt-versions'] })
      setIsVersionsModalOpen(false)
    },
  })

  const handleOpenCreate = () => {
    setSelectedPrompt(null)
    setFormData(defaultFormData)
    setIsModalOpen(true)
  }

  const handleOpenEdit = (prompt: PromptTemplate) => {
    setSelectedPrompt(prompt)
    setFormData({
      name: prompt.name,
      description: prompt.description || '',
      category: prompt.category,
      content: prompt.content,
      system_prompt: prompt.system_prompt || '',
      variables: prompt.variables || [],
      output_format: prompt.output_format || 'text',
      is_default: prompt.is_default,
    })
    setIsModalOpen(true)
  }

  const handleOpenTest = (prompt: PromptTemplate) => {
    setSelectedPrompt(prompt)
    const vars: Record<string, string> = {}
    prompt.variables?.forEach((v) => {
      vars[v.name] = v.default_value || ''
    })
    setTestVariables(vars)
    setTestResult('')
    setIsTestModalOpen(true)
  }

  const handleOpenVersions = (prompt: PromptTemplate) => {
    setSelectedPrompt(prompt)
    setIsVersionsModalOpen(true)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedPrompt) {
      updateMutation.mutate({ id: selectedPrompt.id, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const handleTest = () => {
    if (selectedPrompt) {
      testMutation.mutate({
        template_id: selectedPrompt.id,
        variables: testVariables,
      })
    }
  }

  const handleAddVariable = () => {
    setFormData({
      ...formData,
      variables: [
        ...formData.variables,
        { name: '', description: '', required: false, default_value: '' },
      ],
    })
  }

  const handleRemoveVariable = (index: number) => {
    setFormData({
      ...formData,
      variables: formData.variables.filter((_, i) => i !== index),
    })
  }

  const handleVariableChange = (index: number, field: string, value: any) => {
    const newVariables = [...formData.variables]
    newVariables[index] = { ...newVariables[index], [field]: value }
    setFormData({ ...formData, variables: newVariables })
  }

  const prompts: PromptTemplate[] = promptsData?.items || []
  const categoryList: Array<{value: string, label: string}> = categories || [
    {value: 'document_generation', label: 'Document Generation'},
    {value: 'document_review', label: 'Document Review'},
    {value: 'custom', label: 'Custom'}
  ]

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Error loading prompts: {(error as Error).message}</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Prompt Manager</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage AI prompt templates for document generation and analysis
          </p>
        </div>
        <button onClick={handleOpenCreate} className="btn btn-primary flex items-center gap-2">
          <PlusIcon className="h-5 w-5" />
          New Prompt
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search prompts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input w-full"
          />
        </div>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="input w-48"
        >
          <option value="">All Categories</option>
          {categoryList.map((cat) => (
            <option key={cat.value} value={cat.value}>
              {cat.label}
            </option>
          ))}
        </select>
      </div>

      {/* Prompts List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : prompts.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <DocumentDuplicateIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No prompts</h3>
          <p className="mt-1 text-sm text-gray-500">Get started by creating a new prompt template.</p>
          <button onClick={handleOpenCreate} className="mt-4 btn btn-primary">
            Create Prompt
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {prompts.map((prompt) => (
            <div key={prompt.id} className="card">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-lg font-medium text-gray-900">{prompt.name}</h3>
                    {prompt.is_default && (
                      <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                        Default
                      </span>
                    )}
                    {!prompt.is_active && (
                      <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-800">
                        Inactive
                      </span>
                    )}
                    <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
                      {prompt.category}
                    </span>
                  </div>
                  {prompt.description && (
                    <p className="text-sm text-gray-600 mb-2">{prompt.description}</p>
                  )}
                  <div className="text-xs text-gray-500">
                    Variables: {prompt.variables?.length || 0} | Format: {prompt.output_format || 'text'}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleOpenTest(prompt)}
                    className="p-2 text-gray-400 hover:text-green-600"
                    title="Test"
                  >
                    <PlayIcon className="h-5 w-5" />
                  </button>
                  <button
                    onClick={() => handleOpenVersions(prompt)}
                    className="p-2 text-gray-400 hover:text-blue-600"
                    title="Version History"
                  >
                    <ClockIcon className="h-5 w-5" />
                  </button>
                  <button
                    onClick={() => handleOpenEdit(prompt)}
                    className="p-2 text-gray-400 hover:text-primary-600"
                    title="Edit"
                  >
                    <PencilIcon className="h-5 w-5" />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm('Are you sure you want to delete this prompt?')) {
                        deleteMutation.mutate(prompt.id)
                      }
                    }}
                    className="p-2 text-gray-400 hover:text-red-600"
                    title="Delete"
                  >
                    <TrashIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>
              <div className="mt-3 bg-gray-50 rounded p-3">
                <pre className="text-xs text-gray-600 whitespace-pre-wrap overflow-hidden max-h-24">
                  {prompt.content.substring(0, 300)}
                  {prompt.content.length > 300 && '...'}
                </pre>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setIsModalOpen(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
              <form onSubmit={handleSubmit} className="p-6">
                <h2 className="text-lg font-semibold mb-4">
                  {selectedPrompt ? 'Edit Prompt' : 'Create Prompt'}
                </h2>

                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                      <input
                        type="text"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="input w-full"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                      <select
                        value={formData.category}
                        onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                        className="input w-full"
                      >
                        {categoryList.map((cat) => (
                          <option key={cat.value} value={cat.value}>
                            {cat.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                    <input
                      type="text"
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className="input w-full"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">System Prompt</label>
                    <textarea
                      value={formData.system_prompt}
                      onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                      className="input w-full h-24"
                      placeholder="System instructions for the AI..."
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Content Template <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      value={formData.content}
                      onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                      className="input w-full h-48 font-mono text-sm"
                      placeholder="Use {{variable_name}} for variables..."
                      required
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="block text-sm font-medium text-gray-700">Variables</label>
                      <button type="button" onClick={handleAddVariable} className="text-sm text-primary-600 hover:text-primary-500">
                        + Add Variable
                      </button>
                    </div>
                    {formData.variables.map((variable, index) => (
                      <div key={index} className="flex gap-2 mb-2 p-2 bg-gray-50 rounded">
                        <input
                          type="text"
                          placeholder="Name"
                          value={variable.name}
                          onChange={(e) => handleVariableChange(index, 'name', e.target.value)}
                          className="input flex-1"
                        />
                        <input
                          type="text"
                          placeholder="Description"
                          value={variable.description}
                          onChange={(e) => handleVariableChange(index, 'description', e.target.value)}
                          className="input flex-1"
                        />
                        <input
                          type="text"
                          placeholder="Default"
                          value={variable.default_value || ''}
                          onChange={(e) => handleVariableChange(index, 'default_value', e.target.value)}
                          className="input w-24"
                        />
                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={variable.required}
                            onChange={(e) => handleVariableChange(index, 'required', e.target.checked)}
                            className="mr-1"
                          />
                          <span className="text-xs">Req</span>
                        </label>
                        <button
                          type="button"
                          onClick={() => handleRemoveVariable(index)}
                          className="text-red-600 hover:text-red-800"
                        >
                          <TrashIcon className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Output Format</label>
                      <select
                        value={formData.output_format}
                        onChange={(e) => setFormData({ ...formData, output_format: e.target.value })}
                        className="input w-full"
                      >
                        <option value="text">Text</option>
                        <option value="json">JSON</option>
                        <option value="markdown">Markdown</option>
                        <option value="html">HTML</option>
                      </select>
                    </div>
                    <div className="flex items-center">
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={formData.is_default}
                          onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                          className="mr-2"
                        />
                        <span className="text-sm text-gray-700">Set as default for category</span>
                      </label>
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex justify-end gap-3">
                  <button type="button" onClick={() => setIsModalOpen(false)} className="btn btn-secondary">
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>
                    {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Test Modal */}
      {isTestModalOpen && selectedPrompt && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setIsTestModalOpen(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full">
              <div className="p-6">
                <h2 className="text-lg font-semibold mb-4">Test Prompt: {selectedPrompt.name}</h2>

                {selectedPrompt.variables?.length > 0 && (
                  <div className="mb-4">
                    <h3 className="text-sm font-medium text-gray-700 mb-2">Variables</h3>
                    <div className="space-y-2">
                      {selectedPrompt.variables.map((variable) => (
                        <div key={variable.name}>
                          <label className="block text-xs text-gray-600 mb-1">
                            {variable.name}
                            {variable.required && <span className="text-red-500">*</span>}
                            {variable.description && ` - ${variable.description}`}
                          </label>
                          <input
                            type="text"
                            value={testVariables[variable.name] || ''}
                            onChange={(e) =>
                              setTestVariables({ ...testVariables, [variable.name]: e.target.value })
                            }
                            className="input w-full"
                            placeholder={variable.default_value || ''}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  onClick={handleTest}
                  disabled={testMutation.isPending}
                  className="btn btn-primary w-full mb-4"
                >
                  {testMutation.isPending ? 'Testing...' : 'Run Test'}
                </button>

                {testResult && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">Result</h3>
                    <pre className="bg-gray-50 p-4 rounded text-sm whitespace-pre-wrap max-h-64 overflow-y-auto">
                      {testResult}
                    </pre>
                  </div>
                )}

                <div className="mt-4 flex justify-end">
                  <button onClick={() => setIsTestModalOpen(false)} className="btn btn-secondary">
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Versions Modal */}
      {isVersionsModalOpen && selectedPrompt && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setIsVersionsModalOpen(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full">
              <div className="p-6">
                <h2 className="text-lg font-semibold mb-4">Version History: {selectedPrompt.name}</h2>

                {versions?.length > 0 ? (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {versions.map((version: any) => (
                      <div key={version.id} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                        <div>
                          <p className="text-sm font-medium">Version {version.version_number}</p>
                          <p className="text-xs text-gray-500">
                            {new Date(version.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => restoreVersionMutation.mutate({
                              templateId: selectedPrompt.id,
                              versionId: version.id,
                            })}
                            className="text-sm text-primary-600 hover:text-primary-500"
                          >
                            Restore
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 text-center py-8">No version history available</p>
                )}

                <div className="mt-4 flex justify-end">
                  <button onClick={() => setIsVersionsModalOpen(false)} className="btn btn-secondary">
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
