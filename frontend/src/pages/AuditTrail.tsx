import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ClockIcon,
  DocumentTextIcon,
  UserIcon,
  FunnelIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import { auditApi } from '../services/api'
import { formatDistanceToNow } from 'date-fns'

interface AuditLog {
  id: string
  user_id: string
  user_email?: string
  action: string
  resource_type: string
  resource_id?: string
  details?: Record<string, any>
  ip_address?: string
  user_agent?: string
  created_at: string
}

const actionColors: Record<string, string> = {
  create: 'bg-green-100 text-green-800',
  update: 'bg-blue-100 text-blue-800',
  delete: 'bg-red-100 text-red-800',
  view: 'bg-gray-100 text-gray-800',
  download: 'bg-purple-100 text-purple-800',
  upload: 'bg-indigo-100 text-indigo-800',
  login: 'bg-yellow-100 text-yellow-800',
  logout: 'bg-orange-100 text-orange-800',
  approve: 'bg-green-100 text-green-800',
  reject: 'bg-red-100 text-red-800',
  comment: 'bg-blue-100 text-blue-800',
}

export default function AuditTrail() {
  const [filters, setFilters] = useState({
    action: '',
    resource_type: '',
    from_date: '',
    to_date: '',
  })
  const [page, setPage] = useState(1)
  const [showFilters, setShowFilters] = useState(false)
  const pageSize = 20

  const { data: auditData, isLoading, refetch } = useQuery({
    queryKey: ['audit-logs', filters, page],
    queryFn: () =>
      auditApi.list({
        action: filters.action || undefined,
        resource_type: filters.resource_type || undefined,
        from_date: filters.from_date || undefined,
        to_date: filters.to_date || undefined,
        skip: (page - 1) * pageSize,
        limit: pageSize,
      }),
  })

  const { data: actions } = useQuery({
    queryKey: ['audit-actions'],
    queryFn: () => auditApi.getActions(),
  })

  const { data: summaryData } = useQuery({
    queryKey: ['audit-summary'],
    queryFn: () => auditApi.getSummary(7),
  })

  const { data: myActivity } = useQuery({
    queryKey: ['my-activity'],
    queryFn: () => auditApi.getMyActivity(7, 10),
  })

  const logs: AuditLog[] = auditData?.items || []
  const total = auditData?.total || 0
  const totalPages = Math.ceil(total / pageSize)

  const resourceTypes = ['document', 'project', 'user', 'template', 'prompt', 'comment', 'approval']

  const getActionColor = (action: string) => {
    const baseAction = action.split('_')[0]
    return actionColors[baseAction] || 'bg-gray-100 text-gray-800'
  }

  const handleFilterChange = (key: string, value: string) => {
    setFilters({ ...filters, [key]: value })
    setPage(1)
  }

  const clearFilters = () => {
    setFilters({ action: '', resource_type: '', from_date: '', to_date: '' })
    setPage(1)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Trail</h1>
          <p className="mt-1 text-sm text-gray-500">
            Track all activities and changes in the system
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            className="btn btn-secondary flex items-center gap-2"
          >
            <ArrowPathIcon className="h-4 w-4" />
            Refresh
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`btn ${showFilters ? 'btn-primary' : 'btn-secondary'} flex items-center gap-2`}
          >
            <FunnelIcon className="h-4 w-4" />
            Filters
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="card">
          <p className="text-sm text-gray-500">Total Events (7 days)</p>
          <p className="text-2xl font-semibold">{summaryData?.total_events || 0}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">Active Users</p>
          <p className="text-2xl font-semibold">{summaryData?.active_users || 0}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">Documents Modified</p>
          <p className="text-2xl font-semibold">{summaryData?.documents_modified || 0}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">My Actions (7 days)</p>
          <p className="text-2xl font-semibold">{myActivity?.length || 0}</p>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="card mb-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Action</label>
              <select
                value={filters.action}
                onChange={(e) => handleFilterChange('action', e.target.value)}
                className="input w-full"
              >
                <option value="">All Actions</option>
                {actions?.map((action: string) => (
                  <option key={action} value={action}>
                    {action.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Resource Type</label>
              <select
                value={filters.resource_type}
                onChange={(e) => handleFilterChange('resource_type', e.target.value)}
                className="input w-full"
              >
                <option value="">All Types</option>
                {resourceTypes.map((type) => (
                  <option key={type} value={type}>
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">From Date</label>
              <input
                type="date"
                value={filters.from_date}
                onChange={(e) => handleFilterChange('from_date', e.target.value)}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">To Date</label>
              <input
                type="date"
                value={filters.to_date}
                onChange={(e) => handleFilterChange('to_date', e.target.value)}
                className="input w-full"
              />
            </div>
            <div className="flex items-end">
              <button onClick={clearFilters} className="btn btn-secondary w-full">
                Clear Filters
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Audit Logs */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : logs.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <ClockIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No audit logs</h3>
          <p className="mt-1 text-sm text-gray-500">
            No activities recorded yet or matching your filters.
          </p>
        </div>
      ) : (
        <>
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Time
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Action
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Resource
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Details
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <div className="flex items-center">
                          <ClockIcon className="h-4 w-4 mr-2 text-gray-400" />
                          <div>
                            <p>{new Date(log.created_at).toLocaleString()}</p>
                            <p className="text-xs text-gray-400">
                              {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <UserIcon className="h-4 w-4 mr-2 text-gray-400" />
                          <span className="text-sm text-gray-900">
                            {log.user_email || log.user_id.substring(0, 8)}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getActionColor(
                            log.action
                          )}`}
                        >
                          {log.action.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <DocumentTextIcon className="h-4 w-4 mr-2 text-gray-400" />
                          <div>
                            <p className="text-sm text-gray-900">{log.resource_type}</p>
                            {log.resource_id && (
                              <p className="text-xs text-gray-500">{log.resource_id.substring(0, 8)}...</p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {log.details && Object.keys(log.details).length > 0 ? (
                          <div className="text-xs text-gray-600">
                            {Object.entries(log.details)
                              .slice(0, 2)
                              .map(([key, value]) => (
                                <p key={key}>
                                  <span className="font-medium">{key}:</span>{' '}
                                  {typeof value === 'string' ? value.substring(0, 30) : JSON.stringify(value).substring(0, 30)}
                                </p>
                              ))}
                            {Object.keys(log.details).length > 2 && (
                              <p className="text-gray-400">+{Object.keys(log.details).length - 2} more</p>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-gray-700">
                Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} results
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  className="btn btn-secondary"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-700">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page === totalPages}
                  className="btn btn-secondary"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* My Recent Activity */}
      {myActivity && myActivity.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-medium text-gray-900 mb-4">My Recent Activity</h2>
          <div className="card">
            <div className="space-y-3">
              {myActivity.map((log: AuditLog) => (
                <div key={log.id} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getActionColor(log.action)}`}>
                      {log.action.replace(/_/g, ' ')}
                    </span>
                    <span className="text-sm text-gray-600">{log.resource_type}</span>
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
