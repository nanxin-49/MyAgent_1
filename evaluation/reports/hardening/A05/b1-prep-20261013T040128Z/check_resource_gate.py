"""Read-only B1-PREP resource gate; no downloads, installation or model access.
Run with the existing Python 3.12 interpreter. Exit 2 means resource-blocked.
This does not authorize or start subsequent preparation stages.
"""
import ctypes
from datetime import datetime, timezone
import json
import os
import shutil
import sys


class MemoryStatus(ctypes.Structure):
    _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]


def main():
    state = MemoryStatus()
    state.dwLength = ctypes.sizeof(state)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        raise ctypes.WinError()
    free = shutil.disk_usage('E:\\').free
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'python_executable': sys.executable, 'python_version': sys.version.split()[0],
              'logical_cpus': os.cpu_count(), 'total_ram_bytes': state.ullTotalPhys,
              'available_ram_bytes': state.ullAvailPhys,
              'available_ram_GiB': state.ullAvailPhys / 2**30,
              'memory_load_percent': state.dwMemoryLoad, 'E_free_bytes': free,
              'E_free_GiB': free / 2**30, 'required_available_ram_GiB': 4,
              'required_E_free_GiB': 6,
              'installation_resource_gate_passed': state.ullAvailPhys >= 4 * 2**30 and free >= 6 * 2**30}
    print(json.dumps(result, indent=2))
    return 0 if result['installation_resource_gate_passed'] else 2


if __name__ == '__main__':
    sys.exit(main())
