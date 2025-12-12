"""
Migration script to create audit_logs and notifications tables
"""
import psycopg2


def run_migration():
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="mdms",
        user="postgres",
        password="postgres"
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Create auditaction enum
    print("Creating auditaction enum...")
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'auditaction') THEN
                CREATE TYPE auditaction AS ENUM (
                    'document_create', 'document_view', 'document_update',
                    'document_delete', 'document_download',
                    'version_create', 'version_restore',
                    'workflow_submit', 'workflow_approve', 'workflow_reject',
                    'workflow_publish', 'workflow_unpublish',
                    'comment_create', 'comment_update', 'comment_delete', 'comment_resolve',
                    'search_query', 'rag_query',
                    'user_login', 'user_logout',
                    'prompt_create', 'prompt_update', 'prompt_delete',
                    'template_create', 'template_update'
                );
            END IF;
        END$$;
    """)

    # Create audit_logs table
    print("Creating audit_logs table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            action auditaction NOT NULL,
            user_id UUID REFERENCES users(id),
            user_email VARCHAR(255),
            user_name VARCHAR(255),
            resource_type VARCHAR(50) NOT NULL,
            resource_id UUID,
            resource_name VARCHAR(500),
            details JSONB DEFAULT '{}',
            changes JSONB DEFAULT '{}',
            ip_address VARCHAR(50),
            user_agent VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create notificationtype enum
    print("Creating notificationtype enum...")
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationtype') THEN
                CREATE TYPE notificationtype AS ENUM (
                    'document_shared', 'document_updated', 'document_commented',
                    'review_requested', 'document_approved', 'document_rejected', 'document_published',
                    'comment_reply', 'comment_mention', 'comment_resolved',
                    'system_announcement', 'task_reminder'
                );
            END IF;
        END$$;
    """)

    # Create notificationpriority enum
    print("Creating notificationpriority enum...")
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationpriority') THEN
                CREATE TYPE notificationpriority AS ENUM (
                    'low', 'normal', 'high', 'urgent'
                );
            END IF;
        END$$;
    """)

    # Create notifications table
    print("Creating notifications table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            type notificationtype NOT NULL,
            priority notificationpriority DEFAULT 'normal',
            title VARCHAR(300) NOT NULL,
            message TEXT NOT NULL,
            resource_type VARCHAR(50),
            resource_id UUID,
            action_url VARCHAR(500),
            is_read INTEGER DEFAULT 0,
            read_at TIMESTAMP,
            sender_id UUID REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create indexes
    print("Creating indexes...")

    # Audit logs indexes
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
    """)

    # Notifications indexes
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, is_read);
    """)

    print("Migration completed successfully!")

    conn.close()


if __name__ == "__main__":
    run_migration()
