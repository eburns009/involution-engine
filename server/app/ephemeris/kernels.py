import json
import os
import hashlib
import logging
from typing import Dict, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


def sha256(path: str) -> str:
    """Calculate SHA256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):  # 1MB chunks
                h.update(chunk)
        return h.hexdigest()
    except (IOError, OSError) as e:
        logger.error(f"Failed to hash file {path}: {e}")
        raise


def verify_kernels(bundle_dir: str, checksums_file: str) -> bool:
    """
    Verify kernel files against their expected checksums.

    Args:
        bundle_dir: Directory containing kernel files
        checksums_file: JSON file with expected checksums

    Returns:
        True if all files pass verification, False otherwise
    """
    try:
        with open(checksums_file, "r") as f:
            manifest = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load checksums manifest {checksums_file}: {e}")
        return False

    files_to_check = manifest.get("files", {})
    if not files_to_check:
        logger.warning(f"No files listed in checksums manifest {checksums_file}")
        return False

    all_ok = True
    for rel_path, expected_hash in files_to_check.items():
        full_path = os.path.join(bundle_dir, rel_path)

        if not os.path.exists(full_path):
            logger.error(f"Kernel file missing: {full_path}")
            all_ok = False
            continue

        try:
            actual_hash = sha256(full_path)
            if actual_hash != expected_hash:
                logger.error(f"Checksum mismatch for {rel_path}: "
                           f"expected {expected_hash}, got {actual_hash}")
                all_ok = False
            else:
                logger.debug(f"Checksum verified for {rel_path}")
        except Exception as e:
            logger.error(f"Failed to verify {rel_path}: {e}")
            all_ok = False

    if all_ok:
        logger.info(f"All kernel files verified successfully in {bundle_dir}")
    else:
        logger.error(f"Kernel verification failed for bundle {bundle_dir}")

    return all_ok


def get_kernel_bundle_info(bundle_dir: str) -> Dict[str, any]:
    """
    Get information about a kernel bundle.

    Args:
        bundle_dir: Directory containing kernel bundle

    Returns:
        Dict with bundle information
    """
    info = {
        "path": bundle_dir,
        "exists": os.path.exists(bundle_dir),
        "files": [],
        "total_size": 0
    }

    if not info["exists"]:
        return info

    try:
        for root, dirs, files in os.walk(bundle_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, bundle_dir)
                try:
                    size = os.path.getsize(file_path)
                    info["files"].append({
                        "path": rel_path,
                        "size": size,
                        "type": get_kernel_type(file)
                    })
                    info["total_size"] += size
                except OSError as e:
                    logger.warning(f"Could not get size for {file_path}: {e}")

    except OSError as e:
        logger.error(f"Failed to scan bundle directory {bundle_dir}: {e}")

    return info


def get_kernel_type(filename: str) -> str:
    """
    Determine kernel type from filename extension.

    Args:
        filename: Kernel filename

    Returns:
        Kernel type string
    """
    ext = Path(filename).suffix.lower()
    type_map = {
        ".bsp": "ephemeris",
        ".tls": "leapseconds",
        ".tpc": "planetary_constants",
        ".bpc": "binary_pck",
        ".tf": "text_kernel",
        ".tm": "meta_kernel"
    }
    return type_map.get(ext, "unknown")


def create_checksums_manifest(bundle_dir: str, output_file: str) -> None:
    """
    Create a checksums manifest for a kernel bundle.

    Args:
        bundle_dir: Directory containing kernel files
        output_file: Output JSON file path
    """
    manifest = {
        "bundle": os.path.basename(bundle_dir),
        "created": "",  # Would add timestamp in real implementation
        "files": {}
    }

    if not os.path.exists(bundle_dir):
        raise ValueError(f"Bundle directory does not exist: {bundle_dir}")

    for root, dirs, files in os.walk(bundle_dir):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, bundle_dir)

            # Skip non-kernel files
            if get_kernel_type(file) == "unknown":
                continue

            try:
                file_hash = sha256(file_path)
                manifest["files"][rel_path] = file_hash
                logger.debug(f"Added to manifest: {rel_path} -> {file_hash}")
            except Exception as e:
                logger.error(f"Failed to hash {file_path}: {e}")
                raise

    with open(output_file, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    logger.info(f"Created checksums manifest with {len(manifest['files'])} files: {output_file}")


def validate_bundle_structure(bundle_dir: str, bundle_type: str) -> List[str]:
    """
    Validate that a bundle contains expected kernel types.

    Args:
        bundle_dir: Directory containing kernel bundle
        bundle_type: Bundle type (de440-full, de440-1900, de440-modern)

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not os.path.exists(bundle_dir):
        errors.append(f"Bundle directory does not exist: {bundle_dir}")
        return errors

    # Required kernel types for any bundle
    required_types = {
        "ephemeris": "*.bsp files for planetary positions",
        "leapseconds": "*.tls files for time conversions",
        "planetary_constants": "*.tpc files for planetary data"
    }

    found_types = set()
    for root, dirs, files in os.walk(bundle_dir):
        for file in files:
            kernel_type = get_kernel_type(file)
            if kernel_type != "unknown":
                found_types.add(kernel_type)

    for req_type, description in required_types.items():
        if req_type not in found_types:
            errors.append(f"Missing required kernel type '{req_type}': {description}")

    # Bundle-specific validations
    if bundle_type == "de440-full":
        # Should have comprehensive ephemeris coverage
        pass
    elif bundle_type == "de440-1900":
        # Should have 1900-2100 coverage optimized
        pass
    elif bundle_type == "de440-modern":
        # Should have modern era optimization
        pass

    return errors


class KernelBundle:
    """Class to manage a specific kernel bundle."""

    def __init__(self, bundle_dir: str, bundle_type: str, checksums_file: Optional[str] = None):
        self.bundle_dir = bundle_dir
        self.bundle_type = bundle_type
        self.checksums_file = checksums_file or os.path.join(bundle_dir, "checksums.json")
        self._verified = False
        self._info = None

    @property
    def is_verified(self) -> bool:
        """Check if bundle has been verified."""
        return self._verified

    def verify(self) -> bool:
        """Verify the bundle against checksums."""
        if not os.path.exists(self.checksums_file):
            logger.error(f"Checksums file not found: {self.checksums_file}")
            return False

        self._verified = verify_kernels(self.bundle_dir, self.checksums_file)
        return self._verified

    def get_info(self) -> Dict[str, any]:
        """Get bundle information."""
        if self._info is None:
            self._info = get_kernel_bundle_info(self.bundle_dir)
            self._info["type"] = self.bundle_type
            self._info["verified"] = self._verified

        return self._info

    def validate_structure(self) -> List[str]:
        """Validate bundle structure."""
        return validate_bundle_structure(self.bundle_dir, self.bundle_type)

    def list_kernels(self) -> List[str]:
        """List all kernel files in the bundle."""
        kernels = []
        if os.path.exists(self.bundle_dir):
            for root, dirs, files in os.walk(self.bundle_dir):
                for file in files:
                    if get_kernel_type(file) != "unknown":
                        rel_path = os.path.relpath(os.path.join(root, file), self.bundle_dir)
                        kernels.append(rel_path)
        return sorted(kernels)