import { useQuery } from '@tanstack/react-query'
import {
  DocumentTextIcon,
  UsersIcon,
  CircleStackIcon,
  ChartBarIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowTrendingUpIcon,
} from '@heroicons/react/24/outline'
import { analyticsApi } from '../services/api'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

export default function Analytics() {
  const { data: summary, isLoading: summaryLoading, error } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: () => analyticsApi.getSummary(),
  })

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Error loading analytics: {(error as Error).message}</p>
      </div>
    )
  }

  if (summaryLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const summaryCards = [
    {
      name: 'Total Documents',
      value: summary?.documents?.total_documents || 0,
      icon: DocumentTextIcon,
      color: 'bg-blue-500',
    },
    {
      name: 'Total Users',
      value: summary?.users?.total_users || 0,
      icon: UsersIcon,
      color: 'bg-green-500',
    },
    {
      name: 'Storage Used',
      value: `${(summary?.storage?.total_size_mb || 0).toFixed(2)} MB`,
      icon: CircleStackIcon,
      color: 'bg-purple-500',
    },
    {
      name: 'Active Users (30d)',
      value: summary?.users?.active_users_30d || 0,
      icon: ChartBarIcon,
      color: 'bg-yellow-500',
    },
  ]

  const statusData = summary?.documents?.by_status
    ? Object.entries(summary.documents.by_status).map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value,
      }))
    : []

  const typeData = summary?.documents?.by_file_type
    ? Object.entries(summary.documents.by_file_type).map(([name, value]) => ({
        name: name.toUpperCase(),
        value,
      }))
    : []

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Overview of system performance and document statistics
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        {summaryCards.map((card) => (
          <div key={card.name} className="card">
            <div className="flex items-center">
              <div className={`${card.color} flex h-12 w-12 items-center justify-center rounded-lg`}>
                <card.icon className="h-6 w-6 text-white" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">{card.name}</p>
                <p className="text-2xl font-semibold text-gray-900">{card.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Documents by Status */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Documents by Status</h3>
          {statusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} (${((percent || 0) * 100).toFixed(0)}%)`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {statusData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-500">
              No data available
            </div>
          )}
        </div>

        {/* Documents by Type */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Documents by Type</h3>
          {typeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={typeData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#3B82F6" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-500">
              No data available
            </div>
          )}
        </div>
      </div>

      {/* User Roles Distribution */}
      <div className="card mb-8">
        <h3 className="text-lg font-medium text-gray-900 mb-4">User Roles Distribution</h3>
        {summary?.users?.by_role && Object.keys(summary.users.by_role).length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={Object.entries(summary.users.by_role).map(([role, count]) => ({
              name: role.charAt(0).toUpperCase() + role.slice(1),
              value: count
            }))}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#10B981" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-64 text-gray-500">
            No user data available
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Workflow Statistics */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Workflow Statistics</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <ClockIcon className="h-5 w-5 text-yellow-500 mr-2" />
                <span className="text-sm text-gray-600">Pending Reviews</span>
              </div>
              <span className="text-lg font-semibold">{summary?.workflow?.pending_reviews || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                <span className="text-sm text-gray-600">Published Documents</span>
              </div>
              <span className="text-lg font-semibold">{summary?.workflow?.published_documents || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                <span className="text-sm text-gray-600">Total Actions</span>
              </div>
              <span className="text-lg font-semibold">{summary?.activity?.total_actions || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <ArrowTrendingUpIcon className="h-5 w-5 text-blue-500 mr-2" />
                <span className="text-sm text-gray-600">Period (days)</span>
              </div>
              <span className="text-lg font-semibold">
                {summary?.workflow?.period_days || 30}
              </span>
            </div>
          </div>
        </div>

        {/* Storage Statistics */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Storage Statistics</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Total Files</span>
              <span className="text-lg font-semibold">{summary?.storage?.total_documents || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Total Size</span>
              <span className="text-lg font-semibold">
                {(summary?.storage?.total_size_mb || 0).toFixed(2)} MB
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Versions Size</span>
              <span className="text-lg font-semibold">
                {(summary?.storage?.versions_size_mb || 0).toFixed(2)} MB
              </span>
            </div>
            <div className="mt-4">
              <p className="text-sm font-medium text-gray-700 mb-2">Storage by Type</p>
              {summary?.storage?.by_file_type &&
                Object.entries(summary.storage.by_file_type).map(([type, data]: [string, any]) => (
                  <div key={type} className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-600">{type.toUpperCase()} ({data.count} files)</span>
                    <span className="text-gray-900">
                      {(data.size_mb || 0).toFixed(2)} MB
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
