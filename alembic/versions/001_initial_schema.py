"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2026-02-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create models table
    op.create_table('models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vendor', sa.String(length=100), nullable=False),
        sa.Column('product_family', sa.String(length=100), nullable=True),
        sa.Column('model_name', sa.String(length=200), nullable=False),
        sa.Column('aliases', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_models_id'), 'models', ['id'], unique=False)
    op.create_index(op.f('ix_models_vendor'), 'models', ['vendor'], unique=False)
    op.create_index(op.f('ix_models_product_family'), 'models', ['product_family'], unique=False)
    op.create_index(op.f('ix_models_model_name'), 'models', ['model_name'], unique=False)

    # Create software_versions table
    op.create_table('software_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=True),
        sa.Column('version_string', sa.String(length=100), nullable=False),
        sa.Column('normalized_version', sa.String(length=100), nullable=True),
        sa.Column('release_date', sa.Date(), nullable=True),
        sa.Column('eol_date', sa.Date(), nullable=True),
        sa.Column('eol_status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_software_versions_id'), 'software_versions', ['id'], unique=False)
    op.create_index(op.f('ix_software_versions_model_id'), 'software_versions', ['model_id'], unique=False)
    op.create_index(op.f('ix_software_versions_version_string'), 'software_versions', ['version_string'], unique=False)
    op.create_index(op.f('ix_software_versions_normalized_version'), 'software_versions', ['normalized_version'], unique=False)
    op.create_index(op.f('ix_software_versions_eol_date'), 'software_versions', ['eol_date'], unique=False)
    op.create_index(op.f('ix_software_versions_eol_status'), 'software_versions', ['eol_status'], unique=False)

    # Create pdf_chunks table
    op.create_table('pdf_chunks',
        sa.Column('chunk_id', sa.String(length=500), nullable=False),
        sa.Column('pdf_path', sa.String(length=500), nullable=False),
        sa.Column('page_range', sa.String(length=50), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('inserted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('chunk_id')
    )
    op.create_index(op.f('ix_pdf_chunks_chunk_id'), 'pdf_chunks', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_pdf_chunks_pdf_path'), 'pdf_chunks', ['pdf_path'], unique=False)

    # Create model_version_compatibility table
    op.create_table('model_version_compatibility',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('from_version_id', sa.Integer(), nullable=False),
        sa.Column('to_version_id', sa.Integer(), nullable=False),
        sa.Column('allowed', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ),
        sa.ForeignKeyConstraint(['from_version_id'], ['software_versions.id'], ),
        sa.ForeignKeyConstraint(['to_version_id'], ['software_versions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_version_compatibility_id'), 'model_version_compatibility', ['id'], unique=False)
    op.create_index(op.f('ix_model_version_compatibility_model_id'), 'model_version_compatibility', ['model_id'], unique=False)
    op.create_index(op.f('ix_model_version_compatibility_from_version_id'), 'model_version_compatibility', ['from_version_id'], unique=False)
    op.create_index(op.f('ix_model_version_compatibility_to_version_id'), 'model_version_compatibility', ['to_version_id'], unique=False)

    # Create upgrade_paths table
    op.create_table('upgrade_paths',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('from_version_id', sa.Integer(), nullable=False),
        sa.Column('to_version_id', sa.Integer(), nullable=False),
        sa.Column('mandatory_intermediate_version_ids', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(length=20), nullable=True),
        sa.Column('estimated_downtime_minutes', sa.Integer(), nullable=True),
        sa.Column('requires_backup', sa.Boolean(), nullable=True),
        sa.Column('requires_reboot', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ),
        sa.ForeignKeyConstraint(['from_version_id'], ['software_versions.id'], ),
        sa.ForeignKeyConstraint(['to_version_id'], ['software_versions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_upgrade_paths_id'), 'upgrade_paths', ['id'], unique=False)
    op.create_index(op.f('ix_upgrade_paths_model_id'), 'upgrade_paths', ['model_id'], unique=False)
    op.create_index(op.f('ix_upgrade_paths_from_version_id'), 'upgrade_paths', ['from_version_id'], unique=False)
    op.create_index(op.f('ix_upgrade_paths_to_version_id'), 'upgrade_paths', ['to_version_id'], unique=False)

    # Create extractions table
    op.create_table('extractions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chunk_id', sa.String(length=500), nullable=False),
        sa.Column('extracted_json', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('method', sa.String(length=20), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['chunk_id'], ['pdf_chunks.chunk_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_extractions_id'), 'extractions', ['id'], unique=False)
    op.create_index(op.f('ix_extractions_chunk_id'), 'extractions', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_extractions_method'), 'extractions', ['method'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_extractions_method'), table_name='extractions')
    op.drop_index(op.f('ix_extractions_chunk_id'), table_name='extractions')
    op.drop_index(op.f('ix_extractions_id'), table_name='extractions')
    op.drop_table('extractions')
    
    op.drop_index(op.f('ix_upgrade_paths_to_version_id'), table_name='upgrade_paths')
    op.drop_index(op.f('ix_upgrade_paths_from_version_id'), table_name='upgrade_paths')
    op.drop_index(op.f('ix_upgrade_paths_model_id'), table_name='upgrade_paths')
    op.drop_index(op.f('ix_upgrade_paths_id'), table_name='upgrade_paths')
    op.drop_table('upgrade_paths')
    
    op.drop_index(op.f('ix_model_version_compatibility_to_version_id'), table_name='model_version_compatibility')
    op.drop_index(op.f('ix_model_version_compatibility_from_version_id'), table_name='model_version_compatibility')
    op.drop_index(op.f('ix_model_version_compatibility_model_id'), table_name='model_version_compatibility')
    op.drop_index(op.f('ix_model_version_compatibility_id'), table_name='model_version_compatibility')
    op.drop_table('model_version_compatibility')
    
    op.drop_index(op.f('ix_pdf_chunks_pdf_path'), table_name='pdf_chunks')
    op.drop_index(op.f('ix_pdf_chunks_chunk_id'), table_name='pdf_chunks')
    op.drop_table('pdf_chunks')
    
    op.drop_index(op.f('ix_software_versions_eol_status'), table_name='software_versions')
    op.drop_index(op.f('ix_software_versions_eol_date'), table_name='software_versions')
    op.drop_index(op.f('ix_software_versions_normalized_version'), table_name='software_versions')
    op.drop_index(op.f('ix_software_versions_version_string'), table_name='software_versions')
    op.drop_index(op.f('ix_software_versions_model_id'), table_name='software_versions')
    op.drop_index(op.f('ix_software_versions_id'), table_name='software_versions')
    op.drop_table('software_versions')
    
    op.drop_index(op.f('ix_models_model_name'), table_name='models')
    op.drop_index(op.f('ix_models_product_family'), table_name='models')
    op.drop_index(op.f('ix_models_vendor'), table_name='models')
    op.drop_index(op.f('ix_models_id'), table_name='models')
    op.drop_table('models')
