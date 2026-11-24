"""cgralib.Mem port counts from env METAMAPPER_MEM_PORTS / METAMAPPER_MEM_OUT_PORTS
(irs/coreir/ir.py). Each case runs in its own interpreter: the peak node is built from the
environment at import time."""
import os
import subprocess
import sys

import pytest

PROBE = """
from metamapper.irs.coreir.ir import gen_peak_CoreIR
m = gen_peak_CoreIR(16).instructions['cgralib.Mem'].Py
print(' '.join(m.input_t.field_dict))
print(' '.join(m.output_t.field_dict))
"""


def probe(**env):
    e = {k: v for k, v in os.environ.items() if not k.startswith('METAMAPPER_MEM_')}
    e.update(env)
    return subprocess.run([sys.executable, '-c', PROBE], env=e, capture_output=True, text=True)


def ports(names, prefix):
    return [n for n in names.split() if n.startswith(prefix)]


@pytest.mark.parametrize('env, n_in, n_out', [
    ({}, 2, 2),
    ({'METAMAPPER_MEM_PORTS': '3'}, 3, 3),
    ({'METAMAPPER_MEM_OUT_PORTS': '4'}, 2, 4),
    ({'METAMAPPER_MEM_OUT_PORTS': '2'}, 2, 2),
])
def test_mem_ports(env, n_in, n_out):
    r = probe(**env)
    assert r.returncode == 0, r.stderr
    ins, outs = r.stdout.split('\n')[:2]
    assert ports(ins, 'data_in_') == [f'data_in_{i}' for i in range(n_in)]
    assert ports(ins, 'chain_data_in_') == [f'chain_data_in_{i}' for i in range(n_in)]
    assert ports(outs, 'data_out_') == [f'data_out_{i}' for i in range(n_out)]
    assert 'stencil_valid' in outs.split()


@pytest.mark.parametrize('env', [
    {'METAMAPPER_MEM_PORTS': '3', 'METAMAPPER_MEM_OUT_PORTS': '4'},
    {'METAMAPPER_MEM_OUT_PORTS': '3'},
])
def test_unsupported_mem_ports(env):
    r = probe(**env)
    assert r.returncode != 0
    assert 'METAMAPPER_MEM_OUT_PORTS' in r.stderr
