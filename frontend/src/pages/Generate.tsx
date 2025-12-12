import { useState, useCallback, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import ReactMarkdown from 'react-markdown'
import {
  DocumentPlusIcon,
  CloudArrowUpIcon,
  XMarkIcon,
  ArrowDownTrayIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  GlobeAltIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import { generateApi, promptsApi } from '../services/api'

const EXPORT_FORMATS = [
  { value: 'docx', label: 'Word (.docx)', icon: DocumentTextIcon },
  { value: 'pdf', label: 'PDF (.pdf)', icon: DocumentTextIcon },
  { value: 'md', label: 'Markdown (.md)', icon: CodeBracketIcon },
  { value: 'html', label: 'HTML (.html)', icon: GlobeAltIcon },
]

export default function Generate() {
  const [selectedType, setSelectedType] = useState('')
  const [language, setLanguage] = useState('vi')
  const [context, setContext] = useState('')
  const [textInput, setTextInput] = useState('')  // Direct text input
  const [files, setFiles] = useState<File[]>([])
  const [generatedContent, setGeneratedContent] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [_selectedFormat, _setSelectedFormat] = useState('docx')
  const [isDownloading, setIsDownloading] = useState(false)
  const [showFormatDropdown, setShowFormatDropdown] = useState(false)
  const [selectedPrompt, setSelectedPrompt] = useState<any>(null)
  const [showPromptSelector, setShowPromptSelector] = useState(false)

  const { data: templates } = useQuery({
    queryKey: ['generate-templates'],
    queryFn: () => generateApi.getTemplates(),
  })

  // Fetch prompts for document generation
  const { data: promptsData } = useQuery({
    queryKey: ['prompts-for-generate'],
    queryFn: () => promptsApi.list({ category: 'document_generation', is_active: true }),
  })

  // When document type changes, find matching prompt
  useEffect(() => {
    if (selectedType && promptsData?.items) {
      // Find default prompt for this category or first matching one
      const matchingPrompts = promptsData.items.filter((p: any) =>
        p.category === 'document_generation' && p.is_active
      )
      const defaultPrompt = matchingPrompts.find((p: any) => p.is_default) || matchingPrompts[0]
      if (defaultPrompt && !selectedPrompt) {
        setSelectedPrompt(defaultPrompt)
      }
    }
  }, [selectedType, promptsData])

  const generateMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData()
      formData.append('document_type', selectedType)
      formData.append('language', language)
      if (context) formData.append('context', context)
      if (textInput) formData.append('text_input', textInput)
      files.forEach((file) => formData.append('reference_files', file))

      return generateApi.generate(formData)
    },
    onSuccess: async (data) => {
      setIsPolling(true)
      setCurrentJobId(data.job_id)
      // Poll for result
      const pollResult = async () => {
        try {
          const status = await generateApi.getJobStatus(data.job_id)
          if (status.status === 'completed') {
            const result = await generateApi.getResult(data.job_id)
            setGeneratedContent(result.content)
            setIsPolling(false)
            toast.success('Document generated successfully!')
          } else if (status.status === 'failed') {
            toast.error(status.error_message || 'Generation failed')
            setIsPolling(false)
            setCurrentJobId(null)
          } else {
            setTimeout(pollResult, 2000)
          }
        } catch (error) {
          setIsPolling(false)
          setCurrentJobId(null)
          toast.error('Failed to get generation status')
        }
      }
      pollResult()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Generation failed')
    },
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles((prev) => [...prev, ...acceptedFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/markdown': ['.md'],
    },
  })

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleGenerate = () => {
    if (!selectedType) {
      toast.error('Please select a document type')
      return
    }
    if (files.length === 0 && !textInput.trim()) {
      toast.error('Please enter requirements text or upload reference files')
      return
    }
    generateMutation.mutate()
  }

  const handleDownload = async (format: string) => {
    if (!currentJobId) {
      toast.error('No document to download')
      return
    }

    setIsDownloading(true)
    setShowFormatDropdown(false)
    try {
      const token = localStorage.getItem('token')
      // Use direct link download - simpler and more reliable
      const downloadUrl = `/api/v1/generate/${currentJobId}/download?format=${format}`

      const response = await fetch(downloadUrl, {
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

      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      toast.success(`Downloaded as ${format.toUpperCase()}`)
    } catch (error) {
      console.error('Download error:', error)
      toast.error('Failed to download document')
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Generate Document</h1>
        <p className="mt-1 text-sm text-gray-500">
          Generate professional documents from your reference materials
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Input Panel */}
        <div className="space-y-6">
          {/* Document Type Selection */}
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              1. Select Document Type
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {templates?.templates?.map((template: any) => (
                <button
                  key={template.document_type}
                  onClick={() => setSelectedType(template.document_type)}
                  className={`p-4 border rounded-lg text-left transition-colors ${
                    selectedType === template.document_type
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="font-medium text-gray-900">{template.name}</div>
                  <div className="text-xs text-gray-500">{template.template_standard}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Language Selection */}
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              2. Select Output Language
            </h3>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  value="vi"
                  checked={language === 'vi'}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500"
                />
                <span className="ml-2">Vietnamese</span>
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  value="en"
                  checked={language === 'en'}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500"
                />
                <span className="ml-2">English</span>
              </label>
            </div>
          </div>

          {/* Requirements Input */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">
                3. Enter Requirements
              </h3>
              {/* Prompt Template Selector */}
              {promptsData?.items && promptsData.items.length > 0 && (
                <div className="relative">
                  <button
                    onClick={() => setShowPromptSelector(!showPromptSelector)}
                    className="flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    <SparklesIcon className="h-4 w-4" />
                    {selectedPrompt ? 'Change Prompt Template' : 'Use Prompt Template'}
                  </button>

                  {showPromptSelector && (
                    <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50 max-h-64 overflow-y-auto">
                      <div className="px-3 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider border-b">
                        Select Prompt Template
                      </div>
                      {promptsData.items.map((prompt: any) => (
                        <button
                          key={prompt.id}
                          onClick={() => {
                            setSelectedPrompt(prompt)
                            setShowPromptSelector(false)
                            // Pre-fill with prompt content if textInput is empty
                            if (!textInput.trim()) {
                              // Replace variables with placeholders
                              let content = prompt.content
                              if (prompt.variables) {
                                prompt.variables.forEach((v: any) => {
                                  content = content.replace(
                                    new RegExp(`\\{\\{${v.name}\\}\\}`, 'g'),
                                    v.default_value || `[${v.description || v.name}]`
                                  )
                                })
                              }
                              setTextInput(content)
                            }
                            toast.success(`Loaded prompt: ${prompt.name}`)
                          }}
                          className={`w-full text-left px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-0 ${
                            selectedPrompt?.id === prompt.id ? 'bg-primary-50' : ''
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-gray-900">{prompt.name}</span>
                            {prompt.is_default && (
                              <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full">
                                Default
                              </span>
                            )}
                          </div>
                          {prompt.description && (
                            <p className="text-xs text-gray-500 mt-1 line-clamp-2">{prompt.description}</p>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <p className="text-sm text-gray-500 mb-3">
              Nhập mô tả yêu cầu hoặc upload file tài liệu tham khảo (hoặc cả hai)
            </p>

            {/* Selected Prompt Info */}
            {selectedPrompt && (
              <div className="mb-3 p-3 bg-primary-50 rounded-lg border border-primary-200">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <SparklesIcon className="h-4 w-4 text-primary-600" />
                    <span className="text-sm font-medium text-primary-700">
                      Using: {selectedPrompt.name}
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      setSelectedPrompt(null)
                      setTextInput('')
                    }}
                    className="text-xs text-primary-600 hover:text-primary-700"
                  >
                    Clear
                  </button>
                </div>
                {selectedPrompt.variables && selectedPrompt.variables.length > 0 && (
                  <div className="mt-2 text-xs text-primary-600">
                    Variables: {selectedPrompt.variables.map((v: any) => v.name).join(', ')}
                  </div>
                )}
              </div>
            )}

            {/* Text Input */}
            <textarea
              rows={8}
              className="input mb-4 font-mono text-sm"
              placeholder={selectedPrompt
                ? "Edit the prompt template above or fill in the variables..."
                : "Nhập yêu cầu của bạn tại đây...\n\nVí dụ:\n- Tên dự án: Hệ thống quản lý kho hàng\n- Mục tiêu: Quản lý nhập xuất kho, theo dõi tồn kho\n- Người dùng: Nhân viên kho, quản lý\n- Tính năng chính: Nhập hàng, xuất hàng, báo cáo tồn kho..."}
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
            />

            {/* File Upload */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">hoặc upload file</span>
              </div>
            </div>

            <div
              {...getRootProps()}
              className={`mt-4 border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
                isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <input {...getInputProps()} />
              <CloudArrowUpIcon className="mx-auto h-8 w-8 text-gray-400" />
              <p className="mt-1 text-sm text-gray-600">
                Drop files here (PDF, DOCX, MD)
              </p>
            </div>

            {files.length > 0 && (
              <ul className="mt-4 space-y-2">
                {files.map((file, index) => (
                  <li
                    key={index}
                    className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded"
                  >
                    <span className="text-sm text-gray-700">{file.name}</span>
                    <button
                      onClick={() => removeFile(index)}
                      className="text-gray-400 hover:text-red-500"
                    >
                      <XMarkIcon className="h-5 w-5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Additional Context */}
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              4. Additional Context (Optional)
            </h3>
            <textarea
              rows={4}
              className="input"
              placeholder="Add any additional instructions or context..."
              value={context}
              onChange={(e) => setContext(e.target.value)}
            />
          </div>

          {/* Generate Button */}
          <button
            onClick={handleGenerate}
            disabled={generateMutation.isPending || isPolling}
            className="btn-primary w-full py-3"
          >
            <DocumentPlusIcon className="h-5 w-5 mr-2" />
            {generateMutation.isPending || isPolling ? 'Generating...' : 'Generate Document'}
          </button>
        </div>

        {/* Output Panel */}
        <div className="card h-fit sticky top-24">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              Generated Document
            </h3>
            {generatedContent && currentJobId && (
              <div className="relative">
                <button
                  onClick={() => setShowFormatDropdown(!showFormatDropdown)}
                  disabled={isDownloading}
                  className="btn-primary flex items-center gap-2"
                >
                  <ArrowDownTrayIcon className="h-5 w-5" />
                  {isDownloading ? 'Downloading...' : 'Download'}
                </button>

                {showFormatDropdown && (
                  <div
                    className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="px-3 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Select Format
                    </div>
                    {EXPORT_FORMATS.map((format) => (
                      <button
                        key={format.value}
                        onClick={(e) => {
                          e.stopPropagation()
                          e.preventDefault()
                          console.log('Downloading format:', format.value)
                          handleDownload(format.value)
                        }}
                        className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
                      >
                        <format.icon className="h-5 w-5 text-gray-400" />
                        <span>{format.label}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          {generateMutation.isPending || isPolling ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent"></div>
              <p className="mt-4 text-gray-600 font-medium">
                {generateMutation.isPending ? 'Đang gửi yêu cầu...' : 'Đang tạo tài liệu...'}
              </p>
              <p className="mt-2 text-sm text-gray-500">
                Quá trình này có thể mất 30-60 giây
              </p>
              <div className="mt-4 w-full bg-gray-200 rounded-full h-2">
                <div className="bg-primary-500 h-2 rounded-full animate-pulse" style={{ width: '60%' }}></div>
              </div>
            </div>
          ) : generatedContent ? (
            <div className="prose prose-sm max-w-none max-h-[600px] overflow-y-auto">
              <ReactMarkdown>{generatedContent}</ReactMarkdown>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <DocumentPlusIcon className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2">Your generated document will appear here</p>
            </div>
          )}
        </div>
      </div>

    </div>
  )
}
