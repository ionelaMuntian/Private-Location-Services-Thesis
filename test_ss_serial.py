import sys, tempfile
from pathlib import Path
sys.path.insert(0, '/app')
from app.core.openfhe_ss_runtime_instance import get_openfhe_ss_runtime
import openfhe
from openfhe import BINARY, SerializeToFile, DeserializeCryptoContext

rt = get_openfhe_ss_runtime()
cc = rt.cc
pk = rt.keys.publicKey

p_cc = tempfile.mktemp(); p_em = tempfile.mktemp(); p_ea = tempfile.mktemp()
SerializeToFile(p_cc, cc, BINARY)
cc.SerializeEvalMultKey(p_em, BINARY)
cc.SerializeEvalAutomorphismKey(p_ea, BINARY)
print('Sizes: cc=%d em=%d ea=%d' % (Path(p_cc).stat().st_size, Path(p_em).stat().st_size, Path(p_ea).stat().st_size))

cc2, ok = DeserializeCryptoContext(p_cc, BINARY)
print('cc2 ok:', ok)
try:
    cc2.DeserializeEvalMultKey(p_em, BINARY)
    print('em ok')
except Exception as e:
    print('em skip:', type(e).__name__)
try:
    cc2.DeserializeEvalAutomorphismKey(p_ea, BINARY)
    print('ea ok')
except Exception as e:
    print('ea error:', str(e)[:120])

n = 128
pt = cc2.MakeCKKSPackedPlaintext([0.1*(i%10+1) for i in range(n)])
ct = cc2.Encrypt(pk, pt)
try:
    res = cc2.EvalMinSchemeSwitching(ct, pk, n, n)
    print('EvalMin SUCCESS - BinFHE embedded!')
except Exception as e:
    print('EvalMin FAILED:', str(e)[:200])

for p in [p_cc, p_em, p_ea]:
    Path(p).unlink(missing_ok=True)
