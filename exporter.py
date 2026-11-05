"""Portable project snapshots and independent Python reproduction bundles."""
from __future__ import annotations
import copy
import json
import shutil
import uuid
from pathlib import Path

import pandas as pd
import engine
from dataio import Dataset


def _write_snapshot(project,datasets,path,include_all=False):
    path=Path(path)
    data_dir=path.parent/(path.stem+'_data_'+uuid.uuid4().hex[:8])
    data_dir.mkdir(parents=True,exist_ok=False)
    sources=[]
    used=set(datasets) if include_all else {layer['dataset'] for p in project['panels'] for layer in p['layers']}
    try:
        for i,key in enumerate(sorted(used)):
            ds=datasets[key]
            target=data_dir/f'dataset_{i+1}.csv'
            ds.frame.to_csv(target,index=False,encoding='utf-8',float_format='%.17g')
            dtypes={str(col):'number' if pd.api.types.is_numeric_dtype(ds.frame[col]) else 'text' for col in ds.frame.columns}
            sources.append(dict(id=key,name=ds.name,file=target.relative_to(path.parent).as_posix(),source=ds.source,meta=ds.meta,dtypes=dtypes))
        payload=dict(format='ScientificPlotStudio',version=1,project=copy.deepcopy(project),datasets=sources)
        text=json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)
        path.write_text(text,encoding='utf-8')
    except Exception:
        shutil.rmtree(data_dir)
        raise
    return path


def save_project(project,datasets,path):
    """Save beside an immutable data snapshot. Existing project JSON must be versioned."""
    path=Path(path)
    if path.exists():
        raise FileExistsError('项目文件已存在，请使用新的版本名。')
    path.parent.mkdir(parents=True,exist_ok=True)
    return _write_snapshot(project,datasets,path,include_all=True)


def load_project(path):
    path=Path(path)
    payload=json.loads(path.read_text(encoding='utf-8-sig'))
    if payload.get('format')!='ScientificPlotStudio' or payload.get('version')!=1:
        raise ValueError('不是受支持的Scientific Plot Studio项目。')
    datasets={}
    base=path.parent.resolve()
    for item in payload['datasets']:
        target=(base/item['file']).resolve()
        if not target.is_relative_to(base):
            raise ValueError('项目数据路径超出项目目录。')
        converters={col:str for col,kind in item.get('dtypes',{}).items() if kind=='text'}
        f=pd.read_csv(target,float_precision='round_trip',converters=converters)
        datasets[item['id']]=Dataset(item['id'],item['name'],f,item.get('source',''),item.get('meta',{}))
    return payload['project'],datasets


def export_bundle(project,datasets,destination):
    """Validate first, then atomically publish a new version directory."""
    dest=Path(destination)
    if dest.exists():
        raise FileExistsError('导出目录已存在，请使用新的版本名。')
    figure=engine.render_project(project,datasets)
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=dest.parent/('.'+dest.name+'_'+uuid.uuid4().hex[:8])
    stage.mkdir()
    try:
        _write_snapshot(project,datasets,stage/'project.json')
        (stage/'SciencePlots_LICENSE.txt').write_text(engine.SCIENCEPLOTS_LICENSE,encoding='utf-8')
        palette_source=project.get('palette_sources') or project.get('palette_source')
        if palette_source:
            (stage/'配色来源.txt').write_text(json.dumps(palette_source,ensure_ascii=False,indent=2)+'\n取样色为近似值；配色参考不代表复现原论文的数据或分析。\n',encoding='utf-8')
            licenses=Path(__file__).with_name('assets')/'gallery'
            if licenses.is_dir():
                for notice in licenses.iterdir():
                    if notice.is_file() and notice.name!='palettes.json':shutil.copy2(notice,stage/notice.name)
        source=Path(engine.__file__)
        if not source.is_file() or source.suffix!='.py':
            source=Path(__file__).with_name('engine_source.txt')
        code=source.read_text(encoding='utf-8')
        runner='''

# ===== Tavotto入口：不弹窗、不等待输入；导入时不读数据或绘图 =====
import csv
import json
from pathlib import Path
from types import SimpleNamespace
from matplotlib.backends.backend_agg import FigureCanvasAgg

OUT = Path(__file__).resolve().parent


class _NumericArray:
    def __init__(self, values):
        self.values = values

    def to_numpy(self, dtype=float):
        return np.asarray(self.values, dtype=dtype)


class _NumericILoc:
    def __init__(self, values):
        self.values = values

    def __getitem__(self, item):
        return _NumericArray(self.values[item])


class _NumericFrame:
    def __init__(self, columns, values):
        self.columns = tuple(columns)
        self.values = values
        self.iloc = _NumericILoc(values)

    def __contains__(self, key):
        return key in self.columns

    def __getitem__(self, key):
        return _NumericArray(self.values[:, self.columns.index(key)])


def _read_numeric_csv(path, dtypes=None):
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.reader(handle)
        columns = next(reader)
        dtypes = dtypes or {}
        rows = [[value if dtypes.get(columns[i]) == 'text' else (float(value) if value.strip() else float('nan')) for i,value in enumerate(row)] for row in reader]
    mixed = any(dtypes.get(col) == 'text' for col in columns)
    return _NumericFrame(columns, np.asarray(rows, dtype=object if mixed else float))


def main():
    """Rebuild the editable Matplotlib Figure; callable directly by Tavotto."""
    payload = json.loads((OUT / 'project.json').read_text(encoding='utf-8'))
    datasets = {}
    for item in payload['datasets']:
        datafile = (OUT / item['file']).resolve()
        if not datafile.is_relative_to(OUT):
            raise ValueError('Data path must stay inside bundle')
        datasets[item['id']] = SimpleNamespace(frame=_read_numeric_csv(datafile,item.get('dtypes')))
    project = payload['project']
    fig = render_project(project, datasets)
    FigureCanvasAgg(fig)
    # Literal filenames let Tavotto map this script to its output deterministically.
    with rc_context(style_rc(project)):
        fig.savefig(OUT / 'figure.png', dpi=project['dpi'], facecolor='white')
        fig.savefig(OUT / 'figure.pdf', dpi=project['dpi'], facecolor='white')
        fig.savefig(OUT / 'figure.svg', dpi=project['dpi'], facecolor='white')
    return fig


if __name__ == '__main__':
    main()
'''
        (stage/'plot.py').write_text('# -*- coding: utf-8 -*-\n# 科研绘图复现脚本；数据和样式可分别编辑。\n'+code+runner,encoding='utf-8')
        (stage/'requirements.txt').write_text('numpy>=1.24,<3\nmatplotlib>=3.8,<3.12\n',encoding='utf-8')
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        FigureCanvasAgg(figure)
        from matplotlib import rc_context
        with rc_context(engine.style_rc(project)):
            for ext in ('png','pdf','svg'):
                figure.savefig(stage/f'figure.{ext}',dpi=project['dpi'],facecolor='white')
        (stage/'使用说明.txt').write_text('运行：python plot.py\n缺少依赖时：python -m pip install -r requirements.txt\n图层、配色、坐标、拟合及布局在project.json中修改；原始数值快照在project_data_*目录。\n移动时请复制整个文件夹。PNG按设置的dpi导出；PDF/SVG保留矢量内容。\n拟合为普通最小二乘多项式，未包含误差权重和置信区间。\n',encoding='utf-8')
        (stage/'Tavotto_使用说明.txt').write_text('在Tavotto中拖入plot.py，并按提示选择此导出文件夹。\n请保留同目录的figure.pdf、project.json及project_data_*数据文件夹。\n脚本提供无参数main()，导入时不读数据、不绘图，不弹窗、不调用show()。\n输出文件名固定为figure.pdf/png/svg，脚本与产物同目录。\n只需要NumPy和Matplotlib，无需pandas或Plota源码。\nPDF使用TrueType字体，SVG保留文字。图元保持Matplotlib对象，可在Tavotto中选择和编辑。\n热力图的像素数据不等于可编辑的数值格点；配色和显示属性以Tavotto实际元素面板为准。\n输入兼容不代表通过期刊预检：小字号、低dpi、最终缩放和期刊栏宽仍需在Tavotto里核对。\n官方输入契约：https://github.com/Tavotto/Tavotto/blob/main/codex-plugin/skills/tavotto-figure/references/figure-contract.md\n',encoding='utf-8')
        from matplotlib.text import Text
        fonts=[float(t.get_fontsize()) for t in figure.findobj(Text) if t.get_visible() and t.get_text().strip()]
        advisory=[]
        if fonts and min(fonts)<=8:
            advisory.append('存在8pt附近或更小文字；若在Tavotto中缩小面板，请重新检查最终字号，阈值以所选出版规范为准。')
        if int(project['dpi'])<300:
            advisory.append('当前PNG分辨率低于300dpi；投稿或含栅格热力图时请核查目标规范。')
        if not any(abs(float(project['width_mm'])-w)<.1 for w in (80,150)):
            advisory.append('当前宽度不是Tavotto默认规范中的80/150mm栏宽；请按目标期刊选择规范或调整尺寸，不影响导入编辑。')
        checks=dict(contract='Tavotto main/static-output/matplotlib',script='plot.py',entry='main',output_stem='figure',
                    plot_style=project.get('style','classic'),
                    required_packages=['numpy','matplotlib'],minimum_text_pt=min(fonts) if fonts else None,
                    dpi=project['dpi'],width_mm=project['width_mm'],height_mm=project['height_mm'],publication_advisories=advisory,
                    note='Static contract checks only; live Tavotto acceptance depends on installed version and selected profile.')
        (stage/'Tavotto_检查.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
        stage.rename(dest)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return dest
