#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Скрипт для создания резервных копий БД и фото"""

import shutil
import json
from pathlib import Path
from datetime import datetime
from logging_config import setup_logging

logger = setup_logging("backup")

def create_backup():
    """Создает резервную копию БД и фото в /app/data/backups"""
    
    data_dir = Path("/app/data")
    backup_dir = data_dir / "backups"
    backup_dir.mkdir(exist_ok=True, parents=True)
    
    # Создаем папку с временной меткой
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = backup_dir / backup_name
    backup_path.mkdir(exist_ok=True)
    
    try:
        backed_up = []
        
        # Backup БД
        db_file = data_dir / "profiles.db"
        if db_file.exists():
            shutil.copy2(db_file, backup_path / "profiles.db")
            logger.info(f"Database backed up: {db_file}")
            backed_up.append("profiles.db")
        else:
            logger.warning(f"Database not found: {db_file}")
        
        # Backup фото
        images_dir = data_dir / "images"
        if images_dir.exists() and list(images_dir.glob("*")):
            backup_images = backup_path / "images"
            shutil.copytree(images_dir, backup_images)
            logger.info(f"Images backed up: {images_dir}")
            backed_up.append("images")
        elif not images_dir.exists():
            logger.warning(f"Images directory not found: {images_dir}")
        
        # Создаем metadata файл
        metadata = {
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "backed_up": backed_up,
            "db_exists": db_file.exists(),
            "images_count": len(list(images_dir.glob("*"))) if images_dir.exists() else 0
        }
        with open(backup_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Backup completed: {backup_name}")
        print(f"✅ Резервная копия создана: {backup_name}")
        print(f"   Содержимое: {', '.join(backed_up) if backed_up else 'ничего'}")
        
    except Exception as e:
        logger.error(f"Backup failed: {e}", exc_info=True)
        print(f"❌ Ошибка при создании резервной копии: {e}")
        raise

if __name__ == "__main__":
    create_backup()
