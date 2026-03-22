import os
import zipfile


class UnsafeArchiveError(Exception):
    pass


def safe_extract_zip(zip_path: str, dest_dir: str, logger=None):
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            member_path = os.path.normpath(member.filename)
            if member_path.startswith("..") or os.path.isabs(member_path):
                raise UnsafeArchiveError(f"Blocked unsafe archive path: {member.filename}")

            target = os.path.abspath(os.path.join(dest_dir, member_path))
            dest_abs = os.path.abspath(dest_dir)
            if not target.startswith(dest_abs + os.sep) and target != dest_abs:
                raise UnsafeArchiveError(f"Blocked zip traversal: {member.filename}")

        zf.extractall(dest_dir)

    if logger:
        logger.info("Safely extracted archive %s to %s", zip_path, dest_dir)
