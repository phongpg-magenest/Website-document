import { Fragment, useState } from 'react'
import { Popover, Transition } from '@headlessui/react'
import { BellIcon, CheckIcon, TrashIcon } from '@heroicons/react/24/outline'
import { BellAlertIcon } from '@heroicons/react/24/solid'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { notificationsApi } from '../services/api'
import { formatDistanceToNow } from 'date-fns'

interface Notification {
  id: string
  type: string
  title: string
  message: string
  is_read: boolean
  created_at: string
  data?: Record<string, any>
}

const typeColors: Record<string, string> = {
  document_uploaded: 'bg-blue-100 text-blue-800',
  document_processed: 'bg-green-100 text-green-800',
  document_failed: 'bg-red-100 text-red-800',
  approval_requested: 'bg-yellow-100 text-yellow-800',
  approval_approved: 'bg-green-100 text-green-800',
  approval_rejected: 'bg-red-100 text-red-800',
  comment_added: 'bg-purple-100 text-purple-800',
  mention: 'bg-indigo-100 text-indigo-800',
  system: 'bg-gray-100 text-gray-800',
}

export default function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => notificationsApi.getUnreadCount(),
    refetchInterval: 30000,
  })

  const { data: notificationsData, isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list({ limit: 10 }),
    enabled: isOpen,
  })

  const markAsReadMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markAsRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    },
  })

  const markAllAsReadMutation = useMutation({
    mutationFn: () => notificationsApi.markAllAsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    },
  })

  const unreadCount = unreadData?.unread_count || 0
  const notifications: Notification[] = notificationsData?.items || []

  return (
    <Popover className="relative">
      {({ open }) => {
        if (open !== isOpen) setIsOpen(open)
        return (
          <>
            <Popover.Button className="relative flex items-center justify-center p-2 text-gray-500 hover:text-gray-700 focus:outline-none">
              {unreadCount > 0 ? (
                <BellAlertIcon className="h-6 w-6 text-primary-600" />
              ) : (
                <BellIcon className="h-6 w-6" />
              )}
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-medium text-white">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </Popover.Button>

            <Transition
              as={Fragment}
              enter="transition ease-out duration-200"
              enterFrom="opacity-0 translate-y-1"
              enterTo="opacity-100 translate-y-0"
              leave="transition ease-in duration-150"
              leaveFrom="opacity-100 translate-y-0"
              leaveTo="opacity-0 translate-y-1"
            >
              <Popover.Panel className="absolute right-0 z-50 mt-2 w-96 origin-top-right rounded-lg bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                <div className="p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-gray-900">Notifications</h3>
                    {unreadCount > 0 && (
                      <button
                        onClick={() => markAllAsReadMutation.mutate()}
                        className="text-sm text-primary-600 hover:text-primary-500"
                      >
                        Mark all as read
                      </button>
                    )}
                  </div>

                  {isLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
                    </div>
                  ) : notifications.length === 0 ? (
                    <div className="py-8 text-center text-gray-500">
                      <BellIcon className="mx-auto h-12 w-12 text-gray-300" />
                      <p className="mt-2">No notifications yet</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {notifications.map((notification) => (
                        <div
                          key={notification.id}
                          className={`p-3 rounded-lg ${
                            notification.is_read ? 'bg-gray-50' : 'bg-blue-50'
                          }`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span
                                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                                    typeColors[notification.type] || typeColors.system
                                  }`}
                                >
                                  {notification.type.replace(/_/g, ' ')}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {formatDistanceToNow(new Date(notification.created_at), {
                                    addSuffix: true,
                                  })}
                                </span>
                              </div>
                              <p className="text-sm font-medium text-gray-900">
                                {notification.title}
                              </p>
                              <p className="text-sm text-gray-600">{notification.message}</p>
                            </div>
                            <div className="flex items-center gap-1 ml-2">
                              {!notification.is_read && (
                                <button
                                  onClick={() => markAsReadMutation.mutate(notification.id)}
                                  className="p-1 text-gray-400 hover:text-green-600"
                                  title="Mark as read"
                                >
                                  <CheckIcon className="h-4 w-4" />
                                </button>
                              )}
                              <button
                                onClick={() => deleteMutation.mutate(notification.id)}
                                className="p-1 text-gray-400 hover:text-red-600"
                                title="Delete"
                              >
                                <TrashIcon className="h-4 w-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Popover.Panel>
            </Transition>
          </>
        )
      }}
    </Popover>
  )
}
