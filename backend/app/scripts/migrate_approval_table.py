"""
Migration script to create approval_history table
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

    # Create approvalaction enum if not exists
    print("Creating approvalaction enum...")
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'approvalaction') THEN
                CREATE TYPE approvalaction AS ENUM (
                    'submit_for_review',
                    'approve',
                    'reject',
                    'publish',
                    'unpublish',
                    'request_changes'
                );
            END IF;
        END$$;
    """)

    # Create approval_history table
    print("Creating approval_history table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS approval_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            action approvalaction NOT NULL,
            from_status documentstatus NOT NULL,
            to_status documentstatus NOT NULL,
            performed_by UUID NOT NULL REFERENCES users(id),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create indexes
    print("Creating indexes...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_approval_history_document_id
        ON approval_history(document_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_approval_history_performed_by
        ON approval_history(performed_by);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_approval_history_created_at
        ON approval_history(created_at DESC);
    """)

    print("Migration completed successfully!")

    conn.close()


if __name__ == "__main__":
    run_migration()
