import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  DocumentTextIcon,
  MagnifyingGlassIcon,
  DocumentPlusIcon,
  FolderIcon,
} from '@heroicons/react/24/outline'
import { documentsApi, projectsApi } from '../services/api'
import { useAuth } from '../hooks/useAuth'

const actions = [
  {
    title: 'Upload Document',
    description: 'Upload new documents to the system',
    href: '/documents?upload=true',
    icon: DocumentTextIcon,
    iconBackground: 'bg-blue-500',
  },
  {
    title: 'Search Documents',
    description: 'Search through all documents using AI',
    href: '/search',
    icon: MagnifyingGlassIcon,
    iconBackground: 'bg-green-500',
  },
  {
    title: 'Generate Document',
    description: 'Generate SRS, PRD, and other documents',
    href: '/generate',
    icon: DocumentPlusIcon,
    iconBackground: 'bg-purple-500',
  },
  {
    title: 'Manage Projects',
    description: 'View and manage your projects',
    href: '/projects',
    icon: FolderIcon,
    iconBackground: 'bg-yellow-500',
  },
]

export default function Dashboard() {
  const { user } = useAuth()

  const { data: documentsData } = useQuery({
    queryKey: ['documents', { page: 1, page_size: 5 }],
    queryFn: () => documentsApi.list({ page: 1, page_size: 5 }),
  })

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list(),
  })

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome back, {user?.name}!
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Here's what's happening with your documents today.
        </p>
      </div>

      {/* Quick Actions */}
      <div className="mb-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {actions.map((action) => (
            <Link
              key={action.title}
              to={action.href}
              className="relative flex items-center space-x-3 rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm hover:border-gray-400 focus:outline-none"
            >
              <div className={`${action.iconBackground} flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg`}>
                <action.icon className="h-6 w-6 text-white" />
              </div>
              <div className="min-w-0 flex-1">
                <span className="absolute inset-0" aria-hidden="true" />
                <p className="text-sm font-medium text-gray-900">{action.title}</p>
                <p className="truncate text-sm text-gray-500">{action.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="mb-8 grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="card">
          <dt className="truncate text-sm font-medium text-gray-500">Total Documents</dt>
          <dd className="mt-1 text-3xl font-semibold tracking-tight text-gray-900">
            {documentsData?.total || 0}
          </dd>
        </div>
        <div className="card">
          <dt className="truncate text-sm font-medium text-gray-500">Projects</dt>
          <dd className="mt-1 text-3xl font-semibold tracking-tight text-gray-900">
            {projects?.length || 0}
          </dd>
        </div>
        <div className="card">
          <dt className="truncate text-sm font-medium text-gray-500">Your Role</dt>
          <dd className="mt-1 text-3xl font-semibold tracking-tight text-gray-900 capitalize">
            {user?.role || 'Member'}
          </dd>
        </div>
      </div>

      {/* Recent Documents */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">Recent Documents</h2>
          <Link to="/documents" className="text-sm text-primary-600 hover:text-primary-500">
            View all
          </Link>
        </div>
        {documentsData?.items?.length > 0 ? (
          <ul className="divide-y divide-gray-200">
            {documentsData.items.map((doc: any) => (
              <li key={doc.id} className="py-4">
                <div className="flex items-center space-x-4">
                  <DocumentTextIcon className="h-8 w-8 text-gray-400" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{doc.title}</p>
                    <p className="text-sm text-gray-500">
                      {doc.file_type.toUpperCase()} • {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    doc.status === 'published' ? 'bg-green-100 text-green-800' :
                    doc.status === 'approved' ? 'bg-blue-100 text-blue-800' :
                    doc.status === 'review' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {doc.status}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-500 text-center py-4">
            No documents yet. Upload your first document!
          </p>
        )}
      </div>
    </div>
  )
}
