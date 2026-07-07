import struct
import zlib
import base64
from pathlib import Path
from typing import Optional

def _extract_strings_from_bin(data: bytes, min_len: int = 4) -> str:
    """Extract printable ascii/utf-8 strings from binary blobs (mimicking 'strings' command)."""
    result = []
    current_string = []
    
    for byte in data:
        if 32 <= byte <= 126:  # Printable ASCII
            current_string.append(chr(byte))
        else:
            if len(current_string) >= min_len:
                result.append("".join(current_string))
            current_string = []
            
    if len(current_string) >= min_len:
        result.append("".join(current_string))
        
    return " | ".join(result)

def compress_bin_to_spec(bin_path: Path) -> str:
    """
    Reads a user bin memory file (e.g. from Alt1 or RSMV) and compresses
    its critical context into a text-based User Spec model for Megatron-LM.
    
    The output is a hyper-dense metadata embedding string.
    """
    if not bin_path.exists():
        return "[ERROR: SPEC BINARY NOT FOUND]"
        
    raw_data = bin_path.read_bytes()
    
    # Example heuristic parsing of the binary file:
    # 1. Size and checksum
    size_mb = len(raw_data) / (1024 * 1024)
    checksum = zlib.adler32(raw_data)
    
    # 2. Extract embedded string constraints (useful for game paths, window handles, memory addresses)
    extracted_context = _extract_strings_from_bin(raw_data)
    
    # 3. Create a highly compressed string representation of the spec
    # We take the first 1KB of binary and base64 it just to give the model a raw fingerprint
    fingerprint = base64.b64encode(raw_data[:1024]).decode("ascii")
    
    spec = (
        f"--- USER BINARY SPECIFICATION ---\n"
        f"SOURCE: {bin_path.name}\n"
        f"SIZE: {size_mb:.2f} MB\n"
        f"CHECKSUM: {checksum:x}\n"
        f"FINGERPRINT_B64: {fingerprint}\n"
        f"EXTRACTED_CONTEXT:\n{extracted_context[:2000]}... [TRUNCATED]\n"
        f"---------------------------------"
    )
    return spec
