"""
Data Backup/Restore
서버 이전용 데이터 백업 및 복원
Backup and restore data for server migration
"""
import os
import shutil
import tarfile
from datetime import datetime
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings


def create_backup(output_path: Optional[str] = None) -> str:
    """
    데이터 백업 생성
    Create data backup archive

    Returns:
        백업 파일 경로
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"memory_backup_{timestamp}.tar.gz"
    output_path = output_path or backup_name

    data_dir = settings.DATA_DIR
    json_file = "agent_memory.json"

    print(f"[BACKUP] Creating backup: {output_path}")

    with tarfile.open(output_path, "w:gz") as tar:
        # SQLite DB
        db_path = settings.MEMORY_DB_PATH
        if os.path.exists(db_path):
            tar.add(db_path, arcname=os.path.basename(db_path))
            print(f"  + {db_path}")

        # Chroma directory
        chroma_path = settings.CHROMA_PATH
        if os.path.exists(chroma_path):
            tar.add(chroma_path, arcname="chroma")
            print(f"  + {chroma_path}/")

        # Legacy JSON
        if os.path.exists(json_file):
            tar.add(json_file, arcname=json_file)
            print(f"  + {json_file}")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[BACKUP] Complete: {output_path} ({size_mb:.2f} MB)")

    return output_path


def restore_backup(backup_path: str, target_dir: Optional[str] = None) -> bool:
    """
    백업에서 데이터 복원
    Restore data from backup archive

    Args:
        backup_path: 백업 파일 경로
        target_dir: 복원 대상 디렉토리 (기본: DATA_DIR)

    Returns:
        성공 여부
    """
    if not os.path.exists(backup_path):
        print(f"[RESTORE] Backup not found: {backup_path}")
        return False

    target_dir = target_dir or settings.DATA_DIR
    os.makedirs(target_dir, exist_ok=True)

    print(f"[RESTORE] Restoring from: {backup_path}")
    print(f"[RESTORE] Target directory: {target_dir}")

    with tarfile.open(backup_path, "r:gz") as tar:
        # 파일 목록 확인
        members = tar.getnames()
        print(f"[RESTORE] Archive contents: {members}")

        # 복원
        for member in tar.getmembers():
            if member.name == "memory.db":
                # DB 파일은 DATA_DIR에
                tar.extract(member, target_dir)
                print(f"  + {member.name} -> {target_dir}/")
            elif member.name.startswith("chroma"):
                # Chroma는 DATA_DIR에
                tar.extract(member, target_dir)
                print(f"  + {member.name} -> {target_dir}/")
            elif member.name == "agent_memory.json":
                # JSON은 프로젝트 루트에
                tar.extract(member, ".")
                print(f"  + {member.name} -> ./")
            else:
                tar.extract(member, target_dir)
                print(f"  + {member.name} -> {target_dir}/")

    print("[RESTORE] Complete!")
    return True


def list_backup_contents(backup_path: str):
    """백업 내용물 확인"""
    if not os.path.exists(backup_path):
        print(f"[LIST] Backup not found: {backup_path}")
        return

    print(f"[LIST] Contents of {backup_path}:")
    with tarfile.open(backup_path, "r:gz") as tar:
        for member in tar.getmembers():
            size_kb = member.size / 1024
            print(f"  {member.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backup/Restore memory data")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # backup
    backup_parser = subparsers.add_parser("backup", help="Create backup")
    backup_parser.add_argument("-o", "--output", help="Output file path")

    # restore
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("backup_file", help="Backup file to restore")
    restore_parser.add_argument("-d", "--target-dir", help="Target directory")

    # list
    list_parser = subparsers.add_parser("list", help="List backup contents")
    list_parser.add_argument("backup_file", help="Backup file to inspect")

    args = parser.parse_args()

    if args.command == "backup":
        create_backup(args.output)
    elif args.command == "restore":
        restore_backup(args.backup_file, args.target_dir)
    elif args.command == "list":
        list_backup_contents(args.backup_file)
    else:
        parser.print_help()
