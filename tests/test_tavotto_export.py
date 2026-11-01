import ast
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dataio import Dataset
from engine import new_project,new_layer
from exporter import export_bundle


def bundle_at(tmp_path,kind='line'):
    p=new_project()
    if kind.startswith('matrix'):
        frame=pd.DataFrame(np.arange(16,dtype=float).reshape(4,4),columns=list('abcd'))
        layer=new_layer('a','a','b')
    else:
        frame=pd.DataFrame({'x':[0.,1.,2.,3.], 'y':[1.,np.nan,2.3,4.1]})
        layer=new_layer('a','x','y')
    layer['kind']=kind
    p['panels'][0]['layers']=[layer]
    ds=Dataset('a','a',frame,'',{})
    return export_bundle(p,{'a':ds},tmp_path/'bundle')


def test_top_level_main_and_static_names(tmp_path):
    target=bundle_at(tmp_path)
    code=(target/'plot.py').read_text(encoding='utf-8')
    tree=ast.parse(code)
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    assert 'main' in functions
    main=functions['main']
    assert not main.args.args and not main.args.kwonlyargs
    calls=[n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='savefig']
    assert len(calls)==3
    filenames=[]
    for call in calls:
        value=call.args[0]
        assert isinstance(value,ast.BinOp) and isinstance(value.op,ast.Div)
        assert isinstance(value.right,ast.Constant)
        filenames.append(value.right.value)
    assert set(filenames)=={'figure.pdf','figure.png','figure.svg'}
    assert not any(isinstance(n,(ast.Import,ast.ImportFrom)) and (getattr(n,'module','') or '').startswith('pandas') for n in ast.walk(tree))
    assert 'pandas' not in (target/'requirements.txt').read_text(encoding='utf-8')


def test_import_does_not_draw_or_write(tmp_path,monkeypatch):
    target=bundle_at(tmp_path)
    from matplotlib.figure import Figure
    def forbidden(*args,**kwargs):
        raise AssertionError('Import must not construct Figure')
    monkeypatch.setattr(Figure,'__init__',forbidden)
    before={p.relative_to(target):p.stat().st_mtime_ns for p in target.rglob('*') if p.is_file()}
    spec=importlib.util.spec_from_file_location('plota_generated',target/'plot.py')
    module=importlib.util.module_from_spec(spec)
    old=sys.dont_write_bytecode
    sys.dont_write_bytecode=True
    try: spec.loader.exec_module(module)
    finally: sys.dont_write_bytecode=old
    assert callable(getattr(module,'main',None))
    assert before=={p.relative_to(target):p.stat().st_mtime_ns for p in target.rglob('*') if p.is_file()}


@pytest.mark.parametrize('kind',['line','scatter','matrix_heatmap','matrix_contour'])
def test_runtime_without_pandas_reproduces_export(tmp_path,kind):
    target=bundle_at(tmp_path,kind)
    before=hashlib.sha256((target/'figure.png').read_bytes()).hexdigest()
    runner=tmp_path/'no_pandas.py'
    runner.write_text('''import importlib.abc, importlib.util, sys
class BlockPandas(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pandas' or fullname.startswith('pandas.'):
            raise ImportError('pandas intentionally unavailable')
sys.meta_path.insert(0,BlockPandas())
spec=importlib.util.spec_from_file_location('plota_figure',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.main()
assert 'pandas' not in sys.modules
''',encoding='utf-8')
    process=subprocess.run([sys.executable,str(runner),str(target/'plot.py')],cwd=tmp_path,capture_output=True,text=True,encoding='utf-8',timeout=45)
    assert process.returncode==0,process.stderr
    assert before==hashlib.sha256((target/'figure.png').read_bytes()).hexdigest()
    assert (target/'figure.pdf').stat().st_size>500
    assert (target/'Tavotto_使用说明.txt').exists()
