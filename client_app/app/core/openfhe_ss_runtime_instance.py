from .openfhe_ss_runtime import OpenFHESSClientRuntime

_instance: OpenFHESSClientRuntime | None = None


def get_openfhe_ss_runtime() -> OpenFHESSClientRuntime:
    """Lazy singleton — initialized on first openfhe_ss query."""
    global _instance
    if _instance is None:
        print("[OpenFHE SS] Initializing CKKS+FHEW runtime...", flush=True)
        _instance = OpenFHESSClientRuntime()
        print("[OpenFHE SS] Runtime ready.", flush=True)
    return _instance
