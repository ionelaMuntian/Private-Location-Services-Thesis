import gc

from openfhe import ReleaseAllContexts

from .openfhe_ss_runtime import OpenFHESSClientRuntime

_MAX_CACHED_RUNTIMES = 1
_instances: dict[int, OpenFHESSClientRuntime] = {}


def get_openfhe_ss_runtime(n: int) -> OpenFHESSClientRuntime:
    runtime = _instances.get(n)
    if runtime is None:
        if _instances:
            evicted_ns = list(_instances.keys())
            _instances.clear()
            ReleaseAllContexts()
            gc.collect()
            print(f"[OpenFHE SS] Released cached runtimes (n={evicted_ns})", flush=True)

        print(f"[OpenFHE SS] Initializing CKKS+FHEW runtime (n={n})", flush=True)
        runtime = OpenFHESSClientRuntime(n)
        _instances[n] = runtime
        print("[OpenFHE SS] Runtime ready", flush=True)
    return runtime
