import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  MagnifyingGlassIcon,
  DocumentTextIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import { searchApi } from '../services/api'

interface SearchResult {
  document_id: string
  title: string
  snippet: string
  highlights: string[]
  score: number
  file_type: string
  owner_name: string
  project_name: string | null
  tags: string[]
  created_at: string
}

export default function Search() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [processingTime, setProcessingTime] = useState<number | null>(null)

  const searchMutation = useMutation({
    mutationFn: (q: string) => searchApi.search({ query: q, top_k: 10 }),
    onSuccess: (data) => {
      setResults(data.results)
      setProcessingTime(data.processing_time_ms)
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      searchMutation.mutate(query)
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Semantic Search</h1>
        <p className="mt-1 text-sm text-gray-500">
          Search through documents using natural language
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="mb-8">
        <div className="flex gap-4">
          <div className="flex-1 relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Ask a question about your documents..."
              className="input pl-10 w-full"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={searchMutation.isPending || !query.trim()}
            className="btn-primary"
          >
            {searchMutation.isPending ? 'Searching...' : 'Search'}
          </button>
        </div>
        <p className="mt-2 text-sm text-gray-500">
          Try: "How does authentication work?" or "What are the API endpoints?"
        </p>
      </form>

      {/* Results */}
      {processingTime !== null && (
        <div className="flex items-center gap-2 mb-4 text-sm text-gray-500">
          <ClockIcon className="h-4 w-4" />
          Found {results.length} results in {processingTime.toFixed(0)}ms
        </div>
      )}

      {results.length > 0 ? (
        <div className="space-y-4">
          {results.map((result) => (
            <div key={result.document_id} className="card hover:shadow-md transition-shadow">
              <div className="flex items-start gap-4">
                <DocumentTextIcon className="h-10 w-10 text-gray-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-lg font-medium text-gray-900">
                      {result.title}
                    </h3>
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                      {result.file_type.toUpperCase()}
                    </span>
                    <span className="text-xs text-gray-500">
                      Score: {(result.score * 100).toFixed(1)}%
                    </span>
                  </div>

                  <p className="text-sm text-gray-600 mb-2">
                    {result.snippet}
                  </p>

                  {result.highlights.length > 0 && (
                    <div className="mb-2">
                      <p className="text-xs font-medium text-gray-500 mb-1">Relevant passages:</p>
                      <ul className="space-y-1">
                        {result.highlights.slice(0, 3).map((highlight, idx) => (
                          <li key={idx} className="text-sm text-gray-700 bg-yellow-50 px-2 py-1 rounded">
                            ...{highlight}...
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>By: {result.owner_name}</span>
                    {result.project_name && <span>Project: {result.project_name}</span>}
                    <span>{new Date(result.created_at).toLocaleDateString()}</span>
                  </div>

                  {result.tags.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      {result.tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary-100 text-primary-800"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : searchMutation.isSuccess ? (
        <div className="card text-center py-12">
          <MagnifyingGlassIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No results found</h3>
          <p className="mt-1 text-sm text-gray-500">
            Try different keywords or upload more documents.
          </p>
        </div>
      ) : null}
    </div>
  )
}
