"""
Database module for product labeling system.
Uses SQLAlchemy Core with PostgreSQL for minimal, robust persistence.

Tables:
- products: product folders
- images: individual images with labeling status
- labels: labeling results with mask/cutout paths

Environment variables:
- DATABASE_URL: Database URL (optional). Examples:
  - PostgreSQL: postgresql://user:password@host:5432/dbname
  - SQLite (custom path): sqlite:////absolute/path/to/labeling.db
  If unset, uses SQLite at project data/labeling.db.
- LOCK_MINUTES: Lock timeout in minutes (default: 30)
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, 
    Float, Boolean, DateTime, ForeignKey, Index, text, select
)
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global engine and metadata
_engine = None
_metadata = MetaData()

# Table definitions
products_table = Table(
    'products',
    _metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String, nullable=False),
    Column('folder_relpath', String, unique=True, nullable=False),
    Column('created_at', DateTime, default=datetime.utcnow),
)

images_table = Table(
    'images',
    _metadata,
    Column('id', Integer, primary_key=True),
    Column('product_id', Integer, ForeignKey('products.id'), nullable=False),
    Column('image_relpath', String, unique=True, nullable=False),
    Column('status', String, default='unlabeled', nullable=False),
    Column('assigned_to', String, nullable=True),
    Column('locked_at', DateTime, nullable=True),
    Column('created_at', DateTime, default=datetime.utcnow),
    Index('idx_images_status', 'status'),
    Index('idx_images_locked_at', 'locked_at'),
)

labels_table = Table(
    'labels',
    _metadata,
    Column('id', Integer, primary_key=True),
    Column('image_id', Integer, ForeignKey('images.id'), nullable=False),
    Column('packaging', String, nullable=True),
    Column('product_name', String, nullable=True),
    Column('mask_relpath', String, nullable=True),
    Column('cutout_relpath', String, nullable=True),
    Column('overlay_relpath', String, nullable=True),
    Column('similarity_score', Float, nullable=True),
    Column('created_by', String, nullable=True),
    Column('created_at', DateTime, default=datetime.utcnow),
    Index('idx_labels_image_id', 'image_id'),
)


def get_engine():
    """Get or create database engine. Uses DATABASE_URL if set, else SQLite in project data/."""
    global _engine
    if _engine is None:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            # Fallback: local SQLite so the labeling UI works without PostgreSQL
            db_dir = Path(__file__).resolve().parent.parent / "data"
            db_dir.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{db_dir / 'labeling.db'}"
            logger.info(f"Using default SQLite database: {db_dir / 'labeling.db'}")
            _engine = create_engine(
                database_url,
                echo=False,
                connect_args={"check_same_thread": False},
            )
        else:
            logger.info(f"Database engine created: {database_url.split('@')[-1]}")
            _engine = create_engine(database_url, echo=False)
    return _engine


def init_db():
    """Create all tables if they don't exist."""
    try:
        engine = get_engine()
        _metadata.create_all(engine)
        logger.info("Database tables initialized successfully")
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def healthcheck() -> bool:
    """Check database connectivity."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database healthcheck failed: {e}")
        return False


def upsert_product(folder_relpath: str, name: str) -> int:
    """
    Insert or get existing product by folder_relpath.
    Returns product_id.
    """
    engine = get_engine()
    try:
        with engine.begin() as conn:
            # Try to get existing
            result = conn.execute(
                select(products_table.c.id).where(
                    products_table.c.folder_relpath == folder_relpath
                )
            ).fetchone()
            
            if result:
                return result[0]
            
            # Insert new
            result = conn.execute(
                products_table.insert().values(
                    name=name,
                    folder_relpath=folder_relpath
                )
            )
            return result.inserted_primary_key[0]
    except SQLAlchemyError as e:
        logger.error(f"Failed to upsert product {folder_relpath}: {e}")
        raise


def upsert_image(product_id: int, image_relpath: str) -> int:
    """
    Insert or get existing image by image_relpath.
    Returns image_id.
    """
    engine = get_engine()
    try:
        with engine.begin() as conn:
            # Try to get existing
            result = conn.execute(
                select(images_table.c.id).where(
                    images_table.c.image_relpath == image_relpath
                )
            ).fetchone()
            
            if result:
                return result[0]
            
            # Insert new
            result = conn.execute(
                images_table.insert().values(
                    product_id=product_id,
                    image_relpath=image_relpath,
                    status='unlabeled'
                )
            )
            return result.inserted_primary_key[0]
    except SQLAlchemyError as e:
        logger.error(f"Failed to upsert image {image_relpath}: {e}")
        raise


def ingest_dataset(root_dir: str) -> Dict[str, int]:
    """
    Scan root_dir for product subfolders and ingest all images.
    
    Structure expected:
    root_dir/
        product_folder_1/
            image1.jpg
            image2.jpg
        product_folder_2/
            ...
    
    Returns: {'products': count, 'images': count}
    """
    root_path = Path(root_dir)
    if not root_path.exists():
        raise ValueError(f"Root directory does not exist: {root_dir}")
    
    products_count = 0
    images_count = 0
    supported_exts = {'.jpg', '.jpeg', '.png'}
    
    logger.info(f"Starting dataset ingestion from: {root_dir}")
    
    for product_folder in root_path.iterdir():
        if not product_folder.is_dir():
            continue
        
        folder_relpath = product_folder.relative_to(root_path).as_posix()
        product_name = product_folder.name
        
        try:
            product_id = upsert_product(folder_relpath, product_name)
            products_count += 1
            
            # Ingest images in this folder
            for image_file in product_folder.iterdir():
                if image_file.suffix.lower() in supported_exts:
                    image_relpath = image_file.relative_to(root_path).as_posix()
                    upsert_image(product_id, image_relpath)
                    images_count += 1
            
            logger.info(f"Ingested product: {product_name} ({folder_relpath})")
        except Exception as e:
            logger.error(f"Failed to ingest product {product_name}: {e}")
            continue
    
    logger.info(f"Ingestion complete: {products_count} products, {images_count} images")
    return {'products': products_count, 'images': images_count}


def ingest_product_folder(root_dir: str, product_subfolder: str) -> Dict[str, int]:
    """
    Ingest a single product folder (used after upload).
    
    Args:
        root_dir: Root directory path
        product_subfolder: Subfolder name (relative to root_dir)
    
    Returns: {'products': count, 'images': count}
    """
    root_path = Path(root_dir)
    product_folder = root_path / product_subfolder
    
    if not product_folder.exists():
        raise ValueError(f"Product folder does not exist: {product_folder}")
    
    folder_relpath = product_folder.relative_to(root_path).as_posix()
    product_name = product_folder.name
    supported_exts = {'.jpg', '.jpeg', '.png'}
    
    product_id = upsert_product(folder_relpath, product_name)
    images_count = 0
    
    for image_file in product_folder.iterdir():
        if image_file.suffix.lower() in supported_exts:
            image_relpath = image_file.relative_to(root_path).as_posix()
            upsert_image(product_id, image_relpath)
            images_count += 1
    
    logger.info(f"Ingested product folder: {product_name} with {images_count} images")
    return {'products': 1, 'images': images_count}


def get_next_unlabeled_image(
    assigned_to: str, 
    lock_minutes: int = 30
) -> Optional[Tuple[int, str, int]]:
    """
    Get next unlabeled image and lock it.
    
    Returns: (image_id, image_relpath, product_id) or None if no images available
    """
    engine = get_engine()
    lock_timeout = datetime.utcnow() - timedelta(minutes=lock_minutes)
    
    try:
        with engine.begin() as conn:
            # Find unlabeled image that is not locked or lock expired
            query = select(
                images_table.c.id,
                images_table.c.image_relpath,
                images_table.c.product_id
            ).where(
                images_table.c.status == 'unlabeled'
            ).where(
                (images_table.c.locked_at.is_(None)) | 
                (images_table.c.locked_at < lock_timeout)
            ).order_by(
                images_table.c.id
            ).limit(1).with_for_update(skip_locked=True)
            
            result = conn.execute(query).fetchone()
            
            if not result:
                return None
            
            image_id, image_relpath, product_id = result
            
            # Lock the image
            conn.execute(
                images_table.update().where(
                    images_table.c.id == image_id
                ).values(
                    assigned_to=assigned_to,
                    locked_at=datetime.utcnow()
                )
            )
            
            logger.info(f"Locked image {image_id} for {assigned_to}")
            return (image_id, image_relpath, product_id)
            
    except SQLAlchemyError as e:
        logger.error(f"Failed to get next unlabeled image: {e}")
        raise


def save_label(
    image_id: int,
    packaging: str,
    product_name: str,
    mask_relpath: str,
    cutout_relpath: str,
    overlay_relpath: Optional[str] = None,
    similarity_score: Optional[float] = None,
    created_by: Optional[str] = None
) -> int:
    """
    Save label and mark image as labeled.
    
    Returns: label_id
    """
    engine = get_engine()
    try:
        with engine.begin() as conn:
            # Insert label
            result = conn.execute(
                labels_table.insert().values(
                    image_id=image_id,
                    packaging=packaging,
                    product_name=product_name,
                    mask_relpath=mask_relpath,
                    cutout_relpath=cutout_relpath,
                    overlay_relpath=overlay_relpath,
                    similarity_score=similarity_score,
                    created_by=created_by
                )
            )
            label_id = result.inserted_primary_key[0]
            
            # Update image status and clear lock
            conn.execute(
                images_table.update().where(
                    images_table.c.id == image_id
                ).values(
                    status='labeled',
                    assigned_to=None,
                    locked_at=None
                )
            )
            
            logger.info(f"Saved label {label_id} for image {image_id}")
            return label_id
            
    except SQLAlchemyError as e:
        logger.error(f"Failed to save label for image {image_id}: {e}")
        raise


def mark_image_unlabeled(image_id: int):
    """Mark an image as unlabeled and clear lock (helper for testing/reset)."""
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                images_table.update().where(
                    images_table.c.id == image_id
                ).values(
                    status='unlabeled',
                    assigned_to=None,
                    locked_at=None
                )
            )
            logger.info(f"Marked image {image_id} as unlabeled")
    except SQLAlchemyError as e:
        logger.error(f"Failed to mark image {image_id} as unlabeled: {e}")
        raise


def mark_image_skipped(
    image_id: int,
    skipped_by: Optional[str] = None,
    reason: str = "not_clear"
) -> None:
    """
    Mark an image as skipped and release lock.
    
    Args:
        image_id: Image ID to mark as skipped
        skipped_by: Identifier of person who skipped (optional)
        reason: Reason for skipping (default: "not_clear")
    """
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                images_table.update().where(
                    images_table.c.id == image_id
                ).values(
                    status='skipped',
                    assigned_to=skipped_by,  # Store who skipped it
                    locked_at=None  # Release lock
                )
            )
            logger.info(f"[DB] Marked image {image_id} as skipped (reason: {reason}, by: {skipped_by})")
    except SQLAlchemyError as e:
        logger.error(f"Failed to mark image {image_id} as skipped: {e}")
        raise


def get_stats() -> Dict[str, int]:
    """Get database statistics."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            total_products = conn.execute(
                select(text("COUNT(*)")).select_from(products_table)
            ).scalar()
            
            total_images = conn.execute(
                select(text("COUNT(*)")).select_from(images_table)
            ).scalar()
            
            unlabeled_images = conn.execute(
                select(text("COUNT(*)")).select_from(images_table).where(
                    images_table.c.status == 'unlabeled'
                )
            ).scalar()
            
            labeled_images = conn.execute(
                select(text("COUNT(*)")).select_from(images_table).where(
                    images_table.c.status == 'labeled'
                )
            ).scalar()
            
            return {
                'total_products': total_products,
                'total_images': total_images,
                'unlabeled_images': unlabeled_images,
                'labeled_images': labeled_images
            }
    except SQLAlchemyError as e:
        logger.error(f"Failed to get stats: {e}")
        raise
