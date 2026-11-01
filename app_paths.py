"""Separate bundled read-only resources from portable writable state."""
from pathlib import Path


def locations(module_file, executable=None, frozen=False, override=None):
    resource=Path(module_file).parent
    base=Path(executable).parent if frozen and executable else resource
    runtime=Path(override) if override else base/'Plota_files'
    return resource,base,runtime
