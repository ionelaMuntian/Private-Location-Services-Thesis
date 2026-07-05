import gc

from openfhe import ReleaseAllContexts

from .openfhe_ss_runtime import OpenFHESSClientRuntime

# Only the most recently used batch size is kept alive. Each distinct N
# holds its own CKKS+FHEW crypto context and keys (tens to hundreds of MB),
# and a benchmark run visits many distinct N values in sequence, so caching
# more than the one currently in use would accumulate unbounded memory.
#
# OpenFHE also keeps its own process-wide crypto context registry (the same
# one that required ReleaseAllContexts() server-side to avoid stale-context
# reuse) - dropping our Python reference alone does not free a context's
# memory, since the registry still holds it. ReleaseAllContexts() must be
# called whenever we evict, or usage grows unbounded regardless of our cache.
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
