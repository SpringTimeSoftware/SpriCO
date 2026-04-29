# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""SQLite-backed audit helpers for the white-label audit platform."""

from audit.database import AuditDatabase

__all__ = ["AuditDatabase", "AuditExecutor"]


def __getattr__(name: str):
    if name == "AuditExecutor":
        from audit.executor import AuditExecutor

        return AuditExecutor
    raise AttributeError(f"module 'audit' has no attribute {name!r}")
