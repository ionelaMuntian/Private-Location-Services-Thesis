import gc

from openfhe import ReleaseAllContexts

from .openfhe_ss_runtime import OpenFHESSClientRuntime

_MAX_CACHED_RUNTIMES = 1
_instances: dict[int, OpenFHESSClientRuntime] = {}


def get_openfhe_ss_runtime(n: int) -> OpenFHESSClientRuntime:
    runtime = _instances.get(n)
    if runtime is None:
        if _instances:
            _instances.clear()
            ReleaseAllContexts()
            gc.collect()

        runtime = OpenFHESSClientRuntime(n)
        _instances[n] = runtime
    return runtime
