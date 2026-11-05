import hashlib
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine
from dataio import Dataset,load_file
from exporter import export_bundle,save_project,load_project

NEW_KINDS=['step','area','bar','barh','errorbar','band','bubble','hist','kde','ecdf','box','violin','forest','hexbin','correlation']

def project_for(kind):
    n=30
    f=pd.DataFrame({'x':np.arange(n,dtype=float)+1,'y':np.sin(np.arange(n)/5)+3,'err':np.full(n,.2),
                    'size':np.arange(n)+1.,'other':np.cos(np.arange(n)/8),'group':[f'G{i}' for i in range(n)]})
    p=engine.new_project();p.update(width_mm=160,height_mm=100,dpi=100)
    layer=engine.new_layer('a','x','y')
    layer.update(kind=kind,yerr='err',xerr='err',size='size',bins=10)
    if kind in ('bar','barh'):layer['x']='group'
    if kind=='forest':layer.update(x='y',y='group')
    p['panels'][0]['layers']=[layer]
    return p,{'a':Dataset('a','test',f,'',{})}

@pytest.mark.parametrize('kind',NEW_KINDS)
def test_new_graph_types_produce_artists(kind):
    p,ds=project_for(kind)
    fig=engine.render_project(p,ds)
    ax=fig.axes[0]
    assert len(ax.lines)+len(ax.collections)+len(ax.patches)+len(ax.images)>0
    if kind=='bar':assert ax.get_xticklabels()[0].get_text()=='G0'
    if kind=='ecdf':
        assert ax.lines[0].get_ydata()[-1]==1
        assert np.all(np.diff(ax.lines[0].get_xdata())>=0)
    if kind=='hist':assert sum(p.get_height() for p in ax.patches)==30
    if kind=='correlation':assert ax.images[0].get_array().shape==(5,5)

def test_named_categories_and_literal_na_survive_snapshot_and_script(tmp_path):
    f=tmp_path/'a.csv';f.write_text('group,value\n001,1\nNA,2\ncontrol,3\n',encoding='utf-8')
    ds,=load_file(f)
    assert list(ds.frame['group'])==['001','NA','control']
    p=engine.new_project();p['panels'][0]['layers']=[dict(engine.new_layer(ds.id,'group','value'),kind='bar')]
    save_project(p,{ds.id:ds},tmp_path/'p.json')
    loaded,data=load_project(tmp_path/'p.json')
    assert list(data[ds.id].frame['group'])==['001','NA','control']
    dest=export_bundle(p,{ds.id:ds},tmp_path/'bundle')
    old=hashlib.sha256((dest/'figure.png').read_bytes()).hexdigest()
    proc=subprocess.run([sys.executable,str(dest/'plot.py')],capture_output=True,timeout=45)
    assert proc.returncode==0,proc.stderr
    assert old==hashlib.sha256((dest/'figure.png').read_bytes()).hexdigest()

@pytest.mark.parametrize('extension',['json','jsonl','ndjson','npy','npz','parquet','feather','h5','ods','dat','asc','xy','xvg'])
def test_additional_file_formats(tmp_path,extension):
    frame=pd.DataFrame({'x':[1.,2.,3.],'y':[4.,5.,6.]})
    path=tmp_path/('data.'+extension)
    if extension=='json':path.write_text(frame.to_json(orient='records'),encoding='utf-8')
    elif extension in ('jsonl','ndjson'):path.write_text(frame.to_json(orient='records',lines=True),encoding='utf-8')
    elif extension=='npy':np.save(path,frame.to_numpy())
    elif extension=='npz':np.savez(path,a=frame.to_numpy(),b=np.arange(5.))
    elif extension=='parquet':frame.to_parquet(path,index=False)
    elif extension=='feather':frame.to_feather(path)
    elif extension=='h5':
        import h5py
        with h5py.File(path,'w') as h:h.create_dataset('a',data=frame.to_numpy())
    elif extension=='ods':frame.to_excel(path,index=False,engine='odf')
    elif extension=='xvg':path.write_text('@ title "Demo"\n# comment\n1 4\n2 5\n3 6\n',encoding='utf-8')
    else:frame.to_csv(path,index=False,sep=' ')
    result=load_file(path)
    assert len(result)==(2 if extension=='npz' else 1)
    assert result[0].frame.shape==(3,2)
    assert result[0].frame.iloc[-1,-1]==6

def test_npz_pickle_and_invalid_error_data_rejected(tmp_path):
    p=tmp_path/'unsafe.npy';np.save(p,np.array([{'run':'x'}],dtype=object))
    with pytest.raises(ValueError):load_file(p)
    p,ds=project_for('errorbar');ds['a'].frame.loc[0,'err']=-1
    with pytest.raises(ValueError,match='误差'):engine.render_project(p,ds)

def test_independent_palette_controls_colors_and_gradient():
    p,ds=project_for('line');p['palette_colors']=['#123456','#abcdef']
    assert engine.layer_style(p,1)['color']=='#abcdef'
    p['palette_colors']=['bad-color']
    with pytest.raises(ValueError,match='配色'):engine.render_project(p,ds)

def test_grouped_bars_align_category_names_across_files():
    a=Dataset('a','a',pd.DataFrame({'g':['A','B'],'y':[1.,2.]}),'',{})
    b=Dataset('b','b',pd.DataFrame({'g':['B','A'],'y':[5.,6.]}),'',{})
    p=engine.new_project()
    p['panels'][0]['layers']=[dict(engine.new_layer(k,'g','y'),kind='bar') for k in ('a','b')]
    ax=engine.render_project(p,{'a':a,'b':b}).axes[0]
    centers=[patch.get_x()+patch.get_width()/2 for patch in ax.patches]
    assert centers==pytest.approx([-.2,.8,1.2,.2])
    assert [t.get_text() for t in ax.get_xticklabels()]==['A','B']

def test_headerless_missing_first_row_and_text_at_sign(tmp_path):
    p=tmp_path/'a.csv';p.write_text('1,,3\n2,4,5\n',encoding='utf-8')
    result,=load_file(p);assert len(result.frame)==2
    p.write_text('group,value\n@control,1\n001,2\n',encoding='utf-8')
    result,=load_file(p);assert list(result.frame['group'])==['@control','001']

def test_legacy_xls(tmp_path):
    import xlwt
    p=tmp_path/'legacy.xls';book=xlwt.Workbook();sheet=book.add_sheet('Data')
    for row,values in enumerate([['x','y'],[1,2],[3,4]]):
        for col,value in enumerate(values):sheet.write(row,col,value)
    book.save(str(p))
    ds,=load_file(p);assert ds.frame.iloc[-1,-1]==4

def test_leading_zero_categories_remain_visible_and_na_measurements_are_missing(tmp_path):
    p=tmp_path/'codes.csv';p.write_text('code,y\n001,1\n002,NA\n003,3\n',encoding='utf-8')
    ds,=load_file(p)
    assert list(ds.frame.code)==['001','002','003']
    assert np.isnan(ds.frame.y.iloc[1])
    project=engine.new_project();project['panels'][0]['layers']=[dict(engine.new_layer(ds.id,'code','y'),kind='bar')]
    ax=engine.render_project(project,{ds.id:ds}).axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()]==['001','002','003']
    ds.frame['z']=[4.,5.,6.]
    project['panels'][0]['layers'][0]['kind']='correlation'
    ax=engine.render_project(project,{ds.id:ds}).axes[0]
    assert ax.images[0].get_array().shape==(2,2)
