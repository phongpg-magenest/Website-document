"""
Migration script to create prompt_templates and prompt_template_versions tables
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

    # Create promptcategory enum
    print("Creating promptcategory enum...")
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'promptcategory') THEN
                CREATE TYPE promptcategory AS ENUM (
                    'document_generation',
                    'document_review',
                    'rag_query',
                    'summarization',
                    'keyword_extraction',
                    'custom'
                );
            END IF;
        END$$;
    """)

    # Create prompt_templates table
    print("Creating prompt_templates table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            description TEXT,
            category promptcategory DEFAULT 'custom',
            content TEXT NOT NULL,
            system_prompt TEXT,
            variables JSONB DEFAULT '[]',
            model_config JSONB DEFAULT '{}',
            output_format VARCHAR(50) DEFAULT 'plain_text',
            version VARCHAR(20) DEFAULT '1.0',
            is_active INTEGER DEFAULT 1,
            is_default INTEGER DEFAULT 0,
            created_by UUID NOT NULL REFERENCES users(id),
            updated_by UUID REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create prompt_template_versions table
    print("Creating prompt_template_versions table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prompt_template_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            template_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
            version VARCHAR(20) NOT NULL,
            version_number INTEGER NOT NULL DEFAULT 1,
            content TEXT NOT NULL,
            system_prompt TEXT,
            variables JSONB DEFAULT '[]',
            model_config JSONB DEFAULT '{}',
            changed_by UUID NOT NULL REFERENCES users(id),
            change_summary VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create indexes
    print("Creating indexes...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_templates_category
        ON prompt_templates(category);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_templates_is_active
        ON prompt_templates(is_active);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_templates_is_default
        ON prompt_templates(is_default);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_templates_name
        ON prompt_templates(name);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_template_versions_template_id
        ON prompt_template_versions(template_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_prompt_template_versions_version_number
        ON prompt_template_versions(version_number);
    """)

    print("Migration completed successfully!")

    conn.close()


if __name__ == "__main__":
    run_migration()
