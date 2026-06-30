from .openfhe_ss_runtime import OpenFHESSClientRuntime

_instance: OpenFHESSClientRuntime | None = None


def get_openfhe_ss_runtime() -> OpenFHESSClientRuntime:
    global _instance
    if _instance is None:
        print("[OpenFHE SS] Initializing CKKS+FHEW runtime", flush=True)
        _instance = OpenFHESSClientRuntime()
        print("[OpenFHE SS] Runtime ready", flush=True)
    return _instance
