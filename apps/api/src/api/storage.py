"""Object storage adapter: R2 in production, Garage locally (S3 API).

Uploads go straight from the browser to storage with presigned URLs, so the
VPS never proxies audio bytes (PRD 4.6). Object keys never contain the
original filename: `uploads/{user_id}/{job_id}` (PRD 4.6).

`MemoryStorage` is an in-process double used by tests; it implements the same
surface so router logic is exercised without network or credentials.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from api.config import Settings


class StorageError(Exception):
    """Storage operation failed (R2/Garage down, bad credentials, ...)."""


@dataclass
class ObjectInfo:
    size: int
    content_type: str = ""
    etag: str = ""


@dataclass
class PartInfo:
    part_number: int
    etag: str
    size: int


class Storage(Protocol):
    def create_multipart(self, key: str, content_type: str) -> str: ...

    def sign_part(self, key: str, upload_id: str, part_number: int,
                  ttl_seconds: int) -> tuple[str, datetime]: ...

    def put_part(self, key: str, upload_id: str, part_number: int,
                 data: bytes) -> str:
        """Upload one part server-side (relay); return the ETag."""
        ...

    def list_parts(self, key: str, upload_id: str) -> list[PartInfo]: ...

    def complete_multipart(self, key: str, upload_id: str,
                           parts: list[PartInfo]) -> None: ...

    def abort_multipart(self, key: str, upload_id: str) -> None: ...

    def head(self, key: str) -> ObjectInfo | None: ...

    def read_prefix(self, key: str, length: int = 65536) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def sign_get(self, key: str, ttl_seconds: int,
                 filename: str | None = None) -> tuple[str, datetime]: ...

    def list_keys(self, prefix: str = "") -> list[tuple[str, int]]: ...

    def put_object(self, key: str, data: bytes,
                   content_type: str = "application/octet-stream") -> None: ...


def _iso_plus(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


class S3Storage:
    """S3-compatible client (Cloudflare R2 / Garage). Lazy boto3 import."""

    def __init__(self, settings: Settings) -> None:
        if not settings.s3_bucket:
            raise StorageError("bucket S3 belum dikonfigurasi")
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - boto3 is a dependency
            raise StorageError("boto3 tidak terpasang") from exc
        addressing = "path" if settings.s3_force_path_style else "virtual"
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_key_id,
            aws_secret_access_key=settings.s3_key_secret,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": addressing},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def create_multipart(self, key: str, content_type: str) -> str:
        try:
            resp = self.client.create_multipart_upload(
                Bucket=self.bucket, Key=key, ContentType=content_type
            )
            return resp["UploadId"]
        except Exception as exc:
            raise StorageError(str(exc)) from exc

    def sign_part(self, key: str, upload_id: str, part_number: int,
                  ttl_seconds: int) -> tuple[str, datetime]:
        try:
            url = self.client.generate_presigned_url(
                "upload_part",
                Params={"Bucket": self.bucket, "Key": key,
                        "UploadId": upload_id, "PartNumber": part_number},
                ExpiresIn=ttl_seconds,
            )
        except Exception as exc:
            raise StorageError(str(exc)) from exc
        return url, _iso_plus(ttl_seconds)

    def put_part(self, key: str, upload_id: str, part_number: int,
                 data: bytes) -> str:
        try:
            resp = self.client.upload_part(
                Bucket=self.bucket, Key=key, UploadId=upload_id,
                PartNumber=part_number, Body=data,
            )
        except Exception as exc:
            raise StorageError(str(exc)) from exc
        return str(resp.get("ETag", "")).strip('"')

    def list_parts(self, key: str, upload_id: str) -> list[PartInfo]:
        parts: list[PartInfo] = []
        marker: int | None = None
        try:
            while True:
                kwargs: dict[str, Any] = {
                    "Bucket": self.bucket,
                    "Key": key,
                    "UploadId": upload_id,
                }
                if marker is not None:
                    kwargs["PartNumberMarker"] = marker
                resp = self.client.list_parts(**kwargs)
                for p in resp.get("Parts", []):
                    parts.append(PartInfo(int(p["PartNumber"]), str(p["ETag"]),
                                          int(p.get("Size", 0))))
                if not resp.get("IsTruncated"):
                    break
                marker = int(resp.get("NextPartNumberMarker", 0))
        except Exception as exc:
            if _is_missing_upload(exc):
                return []
            raise StorageError(str(exc)) from exc
        return sorted(parts, key=lambda p: p.part_number)

    def complete_multipart(self, key: str, upload_id: str,
                           parts: list[PartInfo]) -> None:
        try:
            self.client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": [
                        {"PartNumber": p.part_number, "ETag": _quote(p.etag)}
                        for p in sorted(parts, key=lambda p: p.part_number)
                    ]
                },
            )
        except Exception as exc:
            raise StorageError(str(exc)) from exc

    def abort_multipart(self, key: str, upload_id: str) -> None:
        try:
            self.client.abort_multipart_upload(
                Bucket=self.bucket, Key=key, UploadId=upload_id
            )
        except Exception as exc:
            if _is_missing_upload(exc):
                return
            raise StorageError(str(exc)) from exc

    def head(self, key: str) -> ObjectInfo | None:
        try:
            resp = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            if _is_missing_object(exc):
                return None
            raise StorageError(str(exc)) from exc
        return ObjectInfo(int(resp.get("ContentLength", 0)),
                          str(resp.get("ContentType", "")),
                          str(resp.get("ETag", "")).strip('"'))

    def read_prefix(self, key: str, length: int = 65536) -> bytes:
        try:
            resp = self.client.get_object(
                Bucket=self.bucket, Key=key, Range=f"bytes=0-{max(length - 1, 0)}"
            )
            return resp["Body"].read()
        except Exception as exc:
            if _is_missing_object(exc):
                raise StorageError("objek tidak ditemukan") from exc
            raise StorageError(str(exc)) from exc

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            if _is_missing_object(exc):
                return
            raise StorageError(str(exc)) from exc

    def sign_get(self, key: str, ttl_seconds: int,
                 filename: str | None = None) -> tuple[str, datetime]:
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{filename}"'
            )
        try:
            url = self.client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=ttl_seconds
            )
        except Exception as exc:
            raise StorageError(str(exc)) from exc
        return url, _iso_plus(ttl_seconds)

    def list_keys(self, prefix: str = "") -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    out.append((str(obj["Key"]), int(obj.get("Size", 0))))
        except Exception as exc:
            raise StorageError(str(exc)) from exc
        return out

    def put_object(self, key: str, data: bytes,
                   content_type: str = "application/octet-stream") -> None:
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data,
                                   ContentType=content_type)
        except Exception as exc:
            raise StorageError(str(exc)) from exc


def _quote(etag: str) -> str:
    etag = etag.strip()
    return etag if etag.startswith('"') else f'"{etag}"'


def _is_missing_upload(exc: Exception) -> bool:
    text = str(exc)
    return "NoSuchUpload" in text or "404" in text


def _is_missing_object(exc: Exception) -> bool:
    text = str(exc)
    return "NoSuchKey" in text or "NotFound" in text or "404" in text


@dataclass
class _MemoryUpload:
    key: str
    content_type: str
    parts: dict[int, bytes] = field(default_factory=dict)


@dataclass
class _MemoryObject:
    data: bytes
    content_type: str


class MemoryStorage:
    """In-memory storage double (tests only). Same semantics as S3Storage."""

    def __init__(self) -> None:
        self._uploads: dict[str, _MemoryUpload] = {}
        self._objects: dict[str, _MemoryObject] = {}

    # -- helpers used by tests -------------------------------------------
    def key_for(self, upload_id: str) -> str:
        return self._uploads[upload_id].key

    def put_part(self, key: str, upload_id: str, part_number: int,
                 data: bytes) -> str:
        upload = self._uploads[upload_id]
        if upload.key != key:
            raise StorageError("NoSuchUpload")
        upload.parts[part_number] = data
        return _etag(data)

    def put_object(self, key: str, data: bytes,
                   content_type: str = "audio/mpeg") -> None:
        self._objects[key] = _MemoryObject(data, content_type)

    def upload_ids(self) -> list[str]:
        return list(self._uploads)

    # -- Storage protocol ------------------------------------------------
    def create_multipart(self, key: str, content_type: str) -> str:
        upload_id = uuid.uuid4().hex
        self._uploads[upload_id] = _MemoryUpload(key, content_type)
        return upload_id

    def sign_part(self, key: str, upload_id: str, part_number: int,
                  ttl_seconds: int) -> tuple[str, datetime]:
        if upload_id not in self._uploads:
            raise StorageError("NoSuchUpload")
        return (f"memory://upload/{upload_id}/{part_number}",
                _iso_plus(ttl_seconds))

    def list_parts(self, key: str, upload_id: str) -> list[PartInfo]:
        upload = self._uploads.get(upload_id)
        if upload is None or upload.key != key:
            return []
        return [PartInfo(n, _etag(data), len(data))
                for n, data in sorted(upload.parts.items())]

    def complete_multipart(self, key: str, upload_id: str,
                           parts: list[PartInfo]) -> None:
        upload = self._uploads.get(upload_id)
        if upload is None or upload.key != key:
            raise StorageError("NoSuchUpload")
        data = b"".join(upload.parts[p.part_number]
                        for p in sorted(parts, key=lambda p: p.part_number))
        self._objects[key] = _MemoryObject(data, upload.content_type)
        del self._uploads[upload_id]

    def abort_multipart(self, key: str, upload_id: str) -> None:
        self._uploads.pop(upload_id, None)

    def head(self, key: str) -> ObjectInfo | None:
        obj = self._objects.get(key)
        if obj is None:
            return None
        return ObjectInfo(len(obj.data), obj.content_type, _etag(obj.data))

    def read_prefix(self, key: str, length: int = 65536) -> bytes:
        obj = self._objects.get(key)
        if obj is None:
            raise StorageError("objek tidak ditemukan")
        return obj.data[:length]

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def sign_get(self, key: str, ttl_seconds: int,
                 filename: str | None = None) -> tuple[str, datetime]:
        if key not in self._objects:
            raise StorageError("objek tidak ditemukan")
        return f"memory://get/{key}", _iso_plus(ttl_seconds)

    def list_keys(self, prefix: str = "") -> list[tuple[str, int]]:
        return [(k, len(v.data)) for k, v in self._objects.items()
                if k.startswith(prefix)]


def _etag(data: bytes) -> str:
    import hashlib

    return hashlib.md5(data).hexdigest()


def build_storage(settings: Settings) -> Storage:
    """Build the real adapter; callers map StorageError to HTTP 503."""
    try:
        return S3Storage(settings)
    except StorageError:
        return NullStorage()


class NullStorage:
    """Placeholder when S3 is not configured: every operation fails cleanly."""

    def __init__(self) -> None:
        self.reason = "penyimpanan S3/R2 belum dikonfigurasi"

    def _fail(self, *_args, **_kwargs):
        raise StorageError(self.reason)

    create_multipart = _fail
    sign_part = _fail
    put_part = _fail
    list_parts = _fail
    complete_multipart = _fail
    abort_multipart = _fail
    head = _fail
    read_prefix = _fail
    delete = _fail
    sign_get = _fail
    list_keys = _fail
    put_object = _fail


# -- light media check (PRD 4.6 step 5) -------------------------------------

def extension_of(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def sniff_container(prefix: bytes) -> str | None:
    """Return container name from the first bytes, or None when unknown."""
    if not prefix:
        return None
    if prefix.startswith(b"ID3"):
        return "mp3"
    if prefix[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa"):
        return "mp3"
    if prefix[:4] == b"RIFF" and prefix[8:12] == b"WAVE":
        return "wav"
    if prefix.startswith(b"fLaC"):
        return "flac"
    if prefix.startswith(b"OggS"):
        return "ogg"
    if prefix[4:8] == b"ftyp":
        return "mp4"
    if prefix.startswith(b"\x1aE\xdf\xa3"):
        return "webm"
    return None
