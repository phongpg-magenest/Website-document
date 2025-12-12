"""
Migration script để cập nhật bảng document_versions với các columns mới cho Version Control

Usage:
    cd backend
    python -m app.scripts.migrate_version_table
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_connection():
    """Get database connection from DATABASE_URL"""
    database_url = os.getenv("DATABASE_URL", "")

    # Convert async URL to sync URL
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    return psycopg2.connect(database_url)


def migrate():
    """Add new columns to document_versions table"""

    alter_statements = [
        # Add version_number column
        """
        ALTER TABLE document_versions
        ADD COLUMN IF NOT EXISTS version_number INTEGER DEFAULT 1;
        """,

        # Add file_size column
        """
        ALTER TABLE document_versions
        ADD COLUMN IF NOT EXISTS file_size INTEGER;
        """,

        # Create change_type enum if not exists
        """
        DO $$ BEGIN
            CREATE TYPE changetype AS ENUM ('created', 'content_updated', 'metadata_updated', 'status_changed', 'file_replaced', 'restored');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """,

        # Add change_type column
        """
        ALTER TABLE document_versions
        ADD COLUMN IF NOT EXISTS change_type changetype DEFAULT 'content_updated';
        """,

        # Add file_type column (reuse existing filetype enum)
        """
        ALTER TABLE document_versions
        ADD COLUMN IF NOT EXISTS file_type filetype;
        """,

        # Add changes_detail column (JSON text)
        """
        ALTER TABLE document_versions
        ADD COLUMN IF NOT EXISTS changes_detail TEXT;
        """,

        # Add previous_status column
        """
        ALTER TABLE document_versions
        ADD COLUMN IF NOT EXISTS previous_status documentstatus;
        """,

        # Add new_status column
        """
        ALTER TABLE document_versions
        ADD COLUMN IF NOT EXISTS new_status documentstatus;
        """,

        # Add is_major_version column
        """
        ALTER TABLE document_versions
        ADD COLUMN IF NOT EXISTS is_major_version INTEGER DEFAULT 0;
        """,

        # Update existing records to have version_number based on created_at order
        """
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY created_at) as rn
            FROM document_versions
            WHERE version_number IS NULL OR version_number = 1
        )
        UPDATE document_versions
        SET version_number = numbered.rn
        FROM numbered
        WHERE document_versions.id = numbered.id;
        """,

        # Set change_type to 'created' for first versions
        """
        UPDATE document_versions
        SET change_type = 'created'
        WHERE version_number = 1 AND (change_type IS NULL OR change_type = 'content_updated');
        """,
    ]

    conn = get_connection()
    cur = conn.cursor()

    print("Starting migration for document_versions table...")

    for i, stmt in enumerate(alter_statements, 1):
        try:
            cur.execute(stmt)
            conn.commit()
            print(f"  [{i}/{len(alter_statements)}] Executed successfully")
        except Exception as e:
            conn.rollback()
            print(f"  [{i}/{len(alter_statements)}] Warning: {e}")

    cur.close()
    conn.close()

    print("\nMigration completed!")


def check_table_structure():
    """Check current table structure"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'document_versions'
        ORDER BY ordinal_position;
    """)
    rows = cur.fetchall()

    print("\nCurrent document_versions table structure:")
    print("-" * 60)
    for row in rows:
        print(f"  {row[0]:25} {row[1]:20} {'NULL' if row[2] == 'YES' else 'NOT NULL'}")
    print("-" * 60)

    cur.close()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Document Versions Table Migration")
    print("=" * 60)

    check_table_structure()
    migrate()
    check_table_structure()
