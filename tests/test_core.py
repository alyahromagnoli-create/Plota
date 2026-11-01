import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dataio import load_file, Dataset
from engine import new_project, new_panel, new_layer, render_project
from exporter import export_bundle, save_project, load_project


def test_actual_out():
    ds, = load_file(ROOT / 'assets/demo_thermo.out')
    assert len(ds.frame) == 401
    assert len(ds.frame.columns) == 10  # 9 original + explicit Time_ps
    assert ds.frame['Step'].iloc[-1] == 2000000
    assert ds.frame['Time_ps'].iloc[-1] == 200
    assert ds.frame['c_hydrate_com[3]'].iloc[-1] == pytest.approx(60.5)
    assert ds.frame['c_mobile_temp'].iloc[0] == pytest.approx(278.0)
    assert ds.meta['units'] == 'real'


def test_multiple_thermo_blocks_warning_and_time_context(tmp_path):
    f = tmp_path / 'a.out'
    f.write_text('LAMMPS\nUnit style : real\nTime step : 0.1\nStep Temp\n0 270\nWARNING: test\n10 280\nLoop time of 1\n999 888\nTime step : 0.2\nStep Temp\n0 275\n10 285\n', encoding='utf-8')
    a, b = load_file(f)
    assert list(a.frame.Temp) == [270, 280]
    assert b.frame.Time_ps.iloc[-1] == pytest.approx(.002)
    assert len(a.meta['warnings']) >= 1


def test_no_invented_time_and_bad_rows(tmp_path):
    f = tmp_path / 'a.out'
    f.write_text('Step Temp\n0 270\n1 280\n', encoding='utf-8')
    assert 'Time_ps' not in load_file(f)[0].frame
    f.write_text('Step Temp\n0 270\n1 280 99\n', encoding='utf-8')
    with pytest.raises(ValueError, match='行|列'):
        load_file(f)


def test_reject_data_and_no_thermo(tmp_path):
    f = tmp_path / 'a.data'
    f.write_text('1 2\n3 4', encoding='utf-8')
    with pytest.raises(ValueError): load_file(f)
    f = tmp_path / 'a.out'
    f.write_text('not a thermo table', encoding='utf-8')
    with pytest.raises(ValueError): load_file(f)


@pytest.mark.parametrize('text,first', [('1,2\n3,4\n', 1), ('Time,Temperature\n1,2\n3,4\n', 1), ('1 2\n3 4\n', 1), ('# comment\nTime;Temperature\n1;2\n3;4\n', 1)])
def test_table_header_and_delimiters(tmp_path, text, first):
    f = tmp_path / 'table.csv'
    f.write_text(text, encoding='utf-8')
    d, = load_file(f)
    assert len(d.frame) == 2
    assert d.frame.iloc[0, 0] == first


def test_excel_sheets_and_gbk(tmp_path):
    f = tmp_path / 'table.xlsx'
    with pd.ExcelWriter(f) as w:
        pd.DataFrame({'x':[1,2], 'y':[2,4]}).to_excel(w, sheet_name='实验一', index=False)
        pd.DataFrame({'x':[3,4], 'y':[6,8]}).to_excel(w, sheet_name='实验二', index=False)
    assert len(load_file(f)) == 2
    f = tmp_path / 'table.txt'
    f.write_text('时间,温度\n1,278\n2,279', encoding='gb18030')
    assert list(load_file(f)[0].frame) == ['时间','温度']


def sample():
    d = Dataset('test','test',pd.DataFrame({'x':[1.,2.,3.,4.], 'y':[3.,5.,7.,9.]}),'',{})
    p = new_project()
    p['panels'][0]['layers'] = [new_layer(d.id,'x','y')]
    return p, {d.id:d}


def test_fit_and_dimensions():
    p, d = sample()
    p['panels'][0]['layers'][0]['fit'] = 'linear'
    fig = render_project(p,d)
    assert fig.get_size_inches()[0] * 25.4 == pytest.approx(180)
    assert len(fig.axes[0].lines) == 2
    y = fig.axes[0].lines[1].get_ydata()
    assert y[0] == pytest.approx(3)
    assert y[-1] == pytest.approx(9)


def test_layout_overlap_and_invalid_log():
    p,d = sample()
    p['panels'].append(new_panel())
    with pytest.raises(ValueError, match='重叠'): render_project(p,d)
    p['panels'].pop()
    p['panels'][0]['xlim'] = '3,1'
    with pytest.raises(ValueError): render_project(p,d)
    p['panels'][0]['xlim'] = ''
    p['panels'][0]['ylog'] = True
    d['test'].frame.loc[0,'y'] = -2
    with pytest.raises(ValueError): render_project(p,d)


def test_heatmap_contour_and_spans():
    d = Dataset('m','matrix',pd.DataFrame(np.arange(16).reshape(4,4)), '',{})
    p = new_project()
    p.update(rows=2,cols=2)
    p['panels'][0].update(rowspan=2,colspan=2)
    l = new_layer('m','','')
    l['kind'] = 'matrix_heatmap'
    p['panels'][0]['layers']=[l]
    fig = render_project(p,{'m':d})
    assert len(fig.axes[0].images) == 1
    assert len(fig.axes) == 2  # colorbar
    l['kind'] = 'matrix_contour'
    fig = render_project(p,{'m':d})
    assert len(fig.axes) == 2


def test_portable_export_and_roundtrip(tmp_path):
    p,d = sample()
    dst = tmp_path/'bundle'
    export_bundle(p,d,dst)
    assert (dst/'figure.svg').exists()
    proc = subprocess.run([sys.executable,str(dst/'plot.py')],cwd=tmp_path,capture_output=True,text=True,encoding='utf-8')
    assert proc.returncode == 0,proc.stderr
    assert (dst/'figure.pdf').stat().st_size > 500
    loaded, data = load_project(dst/'project.json')
    assert loaded == p
    np.testing.assert_allclose(data['test'].frame.to_numpy(),d['test'].frame.to_numpy())
    with pytest.raises(FileExistsError): export_bundle(p,d,dst)


def test_invalid_export_is_transactional(tmp_path):
    p,d = sample()
    p['panels'][0]['layers'][0]['x']='missing'
    dst=tmp_path/'failed'
    with pytest.raises(ValueError): export_bundle(p,d,dst)
    assert not dst.exists()


def test_ragged_header_does_not_turn_first_column_into_index(tmp_path):
    f=tmp_path/'ragged.csv'
    f.write_text('x,y\n0,1,2\n1,3,4\n',encoding='utf-8')
    with pytest.raises(ValueError,match='列'):
        load_file(f,delimiter=',')


def test_saved_project_keeps_unplotted_datasets(tmp_path):
    p,d=sample()
    extra=Dataset('unused','unused',pd.DataFrame({'x':[1], 'y':[2]}),'',{})
    d['unused']=extra
    save_project(p,d,tmp_path/'all.json')
    _,loaded=load_project(tmp_path/'all.json')
    assert 'unused' in loaded


def test_shared_log_axes_cannot_disagree():
    p,d=sample()
    p.update(cols=2)
    second=new_panel()
    second.update(col=1,sharey=True,ylog=True,layers=[new_layer('test','x','y')])
    p['panels'].append(second)
    with pytest.raises(ValueError,match='共享'):
        render_project(p,d)


def test_grid_disabled_stays_disabled():
    p,d=sample()
    fig=render_project(p,d)
    assert not any(line.get_visible() for line in fig.axes[0].get_xgridlines())


def test_bad_step_cannot_silently_end_thermo(tmp_path):
    f=tmp_path/'broken.out'
    f.write_text('Step Temp\n0 1\ninvalid 2\n2 3\n',encoding='utf-8')
    with pytest.raises(ValueError,match='行'):
        load_file(f)


def test_fit_cannot_silently_cross_zero_on_log_axis():
    p,d=sample()
    d['test'].frame=pd.DataFrame({'x':[1,2,3],'y':[1,1,100]})
    p['panels'][0]['ylog']=True
    p['panels'][0]['layers'][0]['fit']='quadratic'
    with pytest.raises(ValueError,match='拟合'):
        render_project(p,d)
