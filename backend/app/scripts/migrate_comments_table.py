"""
Migration script to create comments and comment_mentions tables
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

    # Create comments table
    print("Creating comments table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            parent_id UUID REFERENCES comments(id) ON DELETE CASCADE,
            author_id UUID NOT NULL REFERENCES users(id),
            content TEXT NOT NULL,
            is_resolved INTEGER DEFAULT 0,
            resolved_by UUID REFERENCES users(id),
            resolved_at TIMESTAMP,
            position_start INTEGER,
            position_end INTEGER,
            position_context VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create comment_mentions table
    print("Creating comment_mentions table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comment_mentions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
            mentioned_user_id UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create indexes
    print("Creating indexes...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_comments_document_id
        ON comments(document_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_comments_parent_id
        ON comments(parent_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_comments_author_id
        ON comments(author_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_comments_is_resolved
        ON comments(is_resolved);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_comment_mentions_comment_id
        ON comment_mentions(comment_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_comment_mentions_user_id
        ON comment_mentions(mentioned_user_id);
    """)

    print("Migration completed successfully!")

    conn.close()


if __name__ == "__main__":
    run_migration()
