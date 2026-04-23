"""Adapter-specific errors."""


class PyRITAdapterError(RuntimeError):
    """Base adapter error."""


class PyRITUnavailableError(PyRITAdapterError):
    """Raised when PyRIT cannot be imported or discovered."""


class UnsupportedPyRITFeatureError(PyRITAdapterError):
    """Raised when a requested PyRIT feature is not productized in SpriCO."""
