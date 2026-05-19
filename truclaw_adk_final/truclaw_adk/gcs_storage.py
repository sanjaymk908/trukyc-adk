import os
from pathlib import Path
from .logging import log

GCS_BUCKET = os.getenv("TRUCLAW_GCS_BUCKET", "")


def _client():
    from google.cloud import storage
    return storage.Client()


def gcs_download(local_path: Path, blob_name: str) -> bool:
    """Download from GCS to local path. Returns True if file was downloaded."""
    if not GCS_BUCKET:
        return False
    if local_path.exists():
        return False
    try:
        client = _client()
        blob = client.bucket(GCS_BUCKET).blob(blob_name)
        if blob.exists():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(local_path))
            log(f"[gcs] downloaded {blob_name} from gs://{GCS_BUCKET}")
            return True
        else:
            log(f"[gcs] {blob_name} not found in GCS — starting fresh")
            return False
    except Exception as e:
        log(f"[gcs] download error {blob_name}: {e}")
        return False


def gcs_upload(local_path: Path, blob_name: str) -> bool:
    """Upload local path to GCS. Returns True if successful."""
    if not GCS_BUCKET:
        return False
    if not local_path.exists():
        return False
    try:
        client = _client()
        blob = client.bucket(GCS_BUCKET).blob(blob_name)
        blob.upload_from_filename(str(local_path))
        log(f"[gcs] uploaded {blob_name} to gs://{GCS_BUCKET}")
        return True
    except Exception as e:
        log(f"[gcs] upload error {blob_name}: {e}")
        return False


def gcs_delete(blob_name: str) -> bool:
    """Delete a blob from GCS. Returns True if successful."""
    if not GCS_BUCKET:
        return False
    try:
        client = _client()
        blob = client.bucket(GCS_BUCKET).blob(blob_name)
        if blob.exists():
            blob.delete()
            log(f"[gcs] deleted {blob_name} from gs://{GCS_BUCKET}")
            return True
        return False
    except Exception as e:
        log(f"[gcs] delete error {blob_name}: {e}")
        return False
