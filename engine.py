"""Deterministic figure rendering; embedded verbatim in exported plot.py."""
from __future__ import annotations
import math
import string

import numpy as np
from matplotlib.figure import Figure
from matplotlib import rc_context
from matplotlib import font_manager


# Vendored SciencePlots settings (MIT), pinned upstream provenance in assets/scienceplots.
# Dictionaries are embedded so exported scripts need no SciencePlots installation.
SCIENCEPLOTS_LICENSE = 'MIT License\n\nCopyright (c) 2018 John Garrett\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the "Software"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.'
_SCIENCEPLOTS = {'science': {'axes.linewidth': 0.5,
             'axes.prop_cycle': [{'color': '#0C5DA5'},
                                 {'color': '#00B945'},
                                 {'color': '#FF9500'},
                                 {'color': '#FF2C00'},
                                 {'color': '#845B97'},
                                 {'color': '#474747'},
                                 {'color': '#9e9e9e'}],
             'figure.figsize': [3.5, 2.625],
             'font.family': ['serif'],
             'grid.linewidth': 0.5,
             'legend.frameon': False,
             'lines.linewidth': 1.0,
             'mathtext.fontset': 'dejavuserif',
             'savefig.bbox': 'tight',
             'savefig.pad_inches': 0.05,
             'text.latex.preamble': '\\usepackage{amsmath} \\usepackage{amssymb}',
             'text.usetex': True,
             'xtick.direction': 'in',
             'xtick.major.size': 3.0,
             'xtick.major.width': 0.5,
             'xtick.minor.size': 1.5,
             'xtick.minor.visible': True,
             'xtick.minor.width': 0.5,
             'xtick.top': True,
             'ytick.direction': 'in',
             'ytick.major.size': 3.0,
             'ytick.major.width': 0.5,
             'ytick.minor.size': 1.5,
             'ytick.minor.visible': True,
             'ytick.minor.width': 0.5,
             'ytick.right': True},
 'ieee': {'axes.prop_cycle': [{'color': 'k', 'linestyle': '-'},
                              {'color': 'r', 'linestyle': '--'},
                              {'color': 'b', 'linestyle': ':'},
                              {'color': 'g', 'linestyle': '-.'}],
          'figure.dpi': 600.0,
          'figure.figsize': [3.3, 2.5],
          'font.family': ['serif'],
          'font.serif': ['Times'],
          'font.size': 8.0},
 'nature': {'axes.labelsize': 7.0,
            'axes.linewidth': 0.5,
            'figure.figsize': [3.3, 2.5],
            'font.family': ['sans-serif'],
            'font.sans-serif': ['DejaVu Sans',
                                'Arial',
                                'Helvetica',
                                'Lucida Grande',
                                'Verdana',
                                'Geneva',
                                'Lucid',
                                'Avant Garde',
                                'sans-serif'],
            'font.size': 7.0,
            'grid.linewidth': 0.5,
            'legend.fontsize': 7.0,
            'lines.linewidth': 1.0,
            'lines.markersize': 3.0,
            'mathtext.fontset': 'dejavusans',
            'text.latex.preamble': '\\usepackage{amsmath} \\usepackage{amssymb} \\usepackage{sfmath}',
            'xtick.labelsize': 7.0,
            'ytick.labelsize': 7.0},
 'bright': {'axes.prop_cycle': [{'color': '#4477AA'},
                                {'color': '#EE6677'},
                                {'color': '#228833'},
                                {'color': '#CCBB44'},
                                {'color': '#66CCEE'},
                                {'color': '#AA3377'},
                                {'color': '#BBBBBB'}]},
 'no-latex': {'axes.formatter.use_mathtext': True,
              'font.family': ['serif'],
              'font.serif': ['STIXGeneral'],
              'mathtext.fontset': 'cm',
              'text.usetex': False}}
STYLE_NAMES = {'Science': 'science', 'IEEE': 'ieee', 'Nature': 'nature', 'Bright': 'bright', '经典': 'classic'}


def style_rc(project):
    name = project.get('style', 'classic')
    if name not in STYLE_NAMES.values():
        raise ValueError('未知绘图风格，请重新选择。')
    params = {}
    if name != 'classic':
        params.update(_SCIENCEPLOTS['science'])
        if name != 'science':
            params.update(_SCIENCEPLOTS[name])
        # Portable MathText rendering; no external TeX installation required.
        params.update(_SCIENCEPLOTS['no-latex'])
        if name == 'nature':
            params.update({'font.family': ['sans-serif'], 'mathtext.fontset': 'dejavusans'})
        if 'axes.prop_cycle' in params:
            # Cycles are applied to layers explicitly, preserving manual edits.
            params.pop('axes.prop_cycle')
        base_size = float(params.get('font.size', 10))
        for key in ('axes.labelsize', 'xtick.labelsize', 'ytick.labelsize', 'legend.fontsize'):
            if isinstance(params.get(key), (float, int)):
                params[key] *= float(project['fontsize']) / base_size
    else:
        params['axes.linewidth'] = .8
    font = project.get('font', '自动')
    if font != '自动':
        params['font.family'] = [font, 'Microsoft YaHei', 'DejaVu Sans']
    elif name == 'classic':
        params['font.family'] = ['DejaVu Sans', 'Microsoft YaHei']
    else:
        family = params.get('font.family', ['serif'])
        family = family[0] if isinstance(family, list) else family
        candidates = params.get('font.' + family, [])
        available = {item.name.casefold() for item in font_manager.fontManager.ttflist}
        params['font.family'] = [name for name in list(candidates) + ['Microsoft YaHei', 'DejaVu Sans']
                                 if name.casefold() in available]
    params.update({'font.size': float(project['fontsize']), 'axes.unicode_minus': False,
                   'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
                   'text.usetex': False, 'savefig.bbox': None, 'savefig.pad_inches': 0})
    return params


def layer_style(project, index):
    name = project.get('style', 'classic')
    if name == 'classic':
        cycle = [{'color': c} for c in ['#2563eb', '#e67e22', '#0d9488', '#9333ea', '#dc2626', '#475569']]
    else:
        if name not in STYLE_NAMES.values():
            raise ValueError('未知绘图风格，请重新选择。')
        cycle = _SCIENCEPLOTS.get(name, {}).get('axes.prop_cycle', _SCIENCEPLOTS['science']['axes.prop_cycle'])
    item = cycle[index % len(cycle)]
    return dict(color=item['color'], linestyle=item.get('linestyle', '-'), linewidth=1.5 if name == 'classic' else 1.)


def new_layer(dataset_id, x, y):
    return dict(dataset=dataset_id,x=x,y=y,label=y,kind='line',color='#2563eb',linewidth=1.5,
                marker='',markersize=4,linestyle='-',cmap='viridis',bins=40,fit='none')


def new_panel():
    return dict(row=0,col=0,rowspan=1,colspan=1,title='',xlabel='',ylabel='',xlim='',ylim='',
                xlog=False,ylog=False,grid=False,legend=True,letter=True,sharex=False,sharey=False,clim='',layers=[])


def new_project():
    return dict(version=1,width_mm=180,height_mm=135,aspect_ratio='4:3',dpi=300,font='自动',fontsize=10,style='science',
                rows=1,cols=1,panels=[new_panel()])


def dimensions_for_ratio(width,height,ratio):
    width=float(width)
    if ratio=='custom':
        return width,float(height)
    values={'16:9':16/9,'1:1':1.,'4:3':4/3}
    if ratio not in values:
        raise ValueError('请选择16:9、1:1、4:3或自定义比例。')
    return width,width/values[ratio]


def ratio_for_dimensions(width,height):
    width,height=float(width),float(height)
    for name,ratio in [('16:9',16/9),('1:1',1.),('4:3',4/3)]:
        if math.isclose(width/height,ratio,rel_tol=1e-7):
            return name
    return 'custom'


def _bounds(value, name):
    if value in ('',None):
        return None
    try:
        nums = [float(t.strip()) for t in str(value).replace('，',',').split(',')]
        if len(nums) != 2 or not all(math.isfinite(n) for n in nums) or nums[0] >= nums[1]:
            raise ValueError()
    except (ValueError,TypeError):
        raise ValueError(f'{name}必须为递增的两个有限数，例如 0,100。')
    return nums


def _validate_layout(project):
    rows,cols = int(project['rows']),int(project['cols'])
    if not (1 <= rows <= 10 and 1 <= cols <= 10):
        raise ValueError('子图行列数须为1到10。')
    if len(project['panels']) > 26 or not project['panels']:
        raise ValueError('子图数量须为1到26。')
    occupied = set()
    for p in project['panels']:
        r,c,rs,cs = [int(p[k]) for k in ('row','col','rowspan','colspan')]
        if r < 0 or c < 0 or rs < 1 or cs < 1 or r+rs > rows or c+cs > cols:
            raise ValueError('子图位置或跨度超出布局范围。位置从0开始。')
        cells={(i,j) for i in range(r,r+rs) for j in range(c,c+cs)}
        if occupied & cells:
            raise ValueError('子图布局重叠，请修改行列位置或跨度。')
        occupied |= cells
    for name in ('x','y'):
        group=[project['panels'][0]]+[p for p in project['panels'][1:] if p.get('share'+name)]
        if len(group)>1:
            if len({bool(p[name+'log']) for p in group})>1:
                raise ValueError(f'共享{name.upper()}轴的子图必须使用一致的对数坐标设置。')
            bounds=[_bounds(p[name+'lim'],name.upper()+'轴范围') for p in group]
            explicit={tuple(b) for b in bounds if b is not None}
            if len(explicit)>1:
                raise ValueError(f'共享{name.upper()}轴的子图范围冲突，请统一范围。')
    return rows,cols


def _curve(ax, layer, dataset, panel):
    f = dataset.frame
    x,y = layer['x'],layer['y']
    if x not in f or y not in f:
        raise ValueError(f'数据列不存在：{x} / {y}')
    xv,yv = f[x].to_numpy(dtype=float),f[y].to_numpy(dtype=float)
    finite=np.isfinite(xv)&np.isfinite(yv)
    if not finite.any():
        raise ValueError('所选曲线没有有限数值点。')
    if (panel['xlog'] and np.any(xv[finite]<=0)) or (panel['ylog'] and np.any(yv[finite]<=0)):
        raise ValueError('对数坐标的数据必须大于0；请先清理数据或关闭对数坐标。')
    style=dict(color=layer['color'],label=layer['label'])
    ms=float(layer['markersize'])
    lw=float(layer['linewidth'])
    if ms<=0 or lw<=0:
        raise ValueError('线宽与标记大小须大于0。')
    # Keep NaN gaps in line plots; do not connect across missing points.
    if layer['kind']=='scatter':
        ax.scatter(xv[finite],yv[finite],s=ms**2,marker=layer['marker'] or 'o',**style)
    elif layer['kind']=='line':
        xv=xv.copy(); yv=yv.copy()
        xv[~finite]=np.nan; yv[~finite]=np.nan
        ax.plot(xv,yv,linewidth=lw,linestyle=layer['linestyle'],marker=layer['marker'] or None,markersize=ms,**style)
    else:
        raise ValueError('未知曲线类型。')
    fit=layer.get('fit','none')
    if fit != 'none':
        degree={'linear':1,'quadratic':2}.get(fit)
        if degree is None:
            raise ValueError('拟合仅支持线性或二次多项式。')
        xf,yf=xv[finite],yv[finite]
        if len(xf)<degree+1 or len(np.unique(xf))<degree+1:
            raise ValueError('拟合所需的不同X值不足。')
        coeff=np.polyfit(xf,yf,degree)
        residual=((yf-np.polyval(coeff,xf))**2).sum()
        total=((yf-yf.mean())**2).sum()
        score=1-residual/total if total>0 else float('nan')
        xx=np.linspace(xf.min(),xf.max(),250)
        eq='; '.join(f'a{degree-i}={v:.4g}' for i,v in enumerate(coeff))
        predicted=np.polyval(coeff,xx)
        if panel['ylog'] and (predicted<=0).any():
            raise ValueError('拟合曲线包含非正值，无法完整显示在对数Y轴；请选择其他模型或线性坐标。')
        ax.plot(xx,predicted,'--',color=layer['color'],linewidth=lw,
                label=f'{layer["label"]} fit: {eq}; R²={score:.4f}')
    return x,y


def _matrix(ax,layer,dataset,panel,fig):
    f=dataset.frame
    # Optional ranges are zero-based Python half-open intervals.
    def endpoint(key):
        value=layer.get(key,'')
        return None if value in ('',None) else int(value)
    z=f.iloc[slice(endpoint('row_start'),endpoint('row_end')),slice(endpoint('col_start'),endpoint('col_end'))].to_numpy(dtype=float)
    if z.ndim!=2 or min(z.shape)<2 or not np.isfinite(z).any():
        raise ValueError('二维图至少需要2×2的数值矩阵，请选择正确的数据区域。')
    limits=_bounds(panel.get('clim',''),'颜色范围')
    opts=dict(cmap=layer['cmap'])
    if limits:
        opts.update(vmin=limits[0],vmax=limits[1])
    if layer['kind']=='matrix_heatmap':
        artist=ax.imshow(np.ma.masked_invalid(z),origin='lower',aspect='auto',interpolation='nearest',**opts)
    else:
        levels=int(layer.get('bins',40))
        if not 2<=levels<=200:
            raise ValueError('等高线级数须为2到200。')
        if limits:
            levels=np.linspace(*limits,levels)
        artist=ax.contourf(np.ma.masked_invalid(z),levels=levels,**opts)
    cb=fig.colorbar(artist,ax=ax,pad=.025)
    cb.set_label(layer.get('label','') or 'Value')
    return 'Column index','Row index'


def render_project(project,datasets,figure=None):
    rows,cols=_validate_layout(project)
    width,height=float(project['width_mm']),float(project['height_mm'])
    fs=float(project['fontsize']); dpi=int(project['dpi'])
    if not (30<=width<=1000 and 30<=height<=1000 and 4<=fs<=72 and 72<=dpi<=1200):
        raise ValueError('尺寸30–1000 mm，字号4–72 pt，分辨率72–1200 dpi。')
    with rc_context(style_rc(project)):
        fig=figure if figure is not None else Figure()
        fig.clear()
        fig.set_size_inches(width/25.4,height/25.4,forward=False)
        fig.set_dpi(min(dpi,150))  # export dpi is passed explicitly to savefig
        fig.set_layout_engine('constrained')
        gs=fig.add_gridspec(rows,cols)
        first=None
        for i,p in enumerate(project['panels']):
            r,c,rs,cs=[int(p[k]) for k in ('row','col','rowspan','colspan')]
            ax=fig.add_subplot(gs[r:r+rs,c:c+cs],sharex=first if p.get('sharex') else None,sharey=first if p.get('sharey') else None)
            if first is None: first=ax
            xname,yname='',''
            for layer in p['layers']:
                if layer['dataset'] not in datasets:
                    raise ValueError('图层引用的数据源不存在，请重新选择。')
                dataset=datasets[layer['dataset']]
                if layer['kind'] in ('matrix_heatmap','matrix_contour'):
                    xname,yname=_matrix(ax,layer,dataset,p,fig)
                else:
                    xname,yname=_curve(ax,layer,dataset,p)
            if p['letter']:
                ax.set_title(f'({string.ascii_lowercase[i]})  {p["title"]}',loc='left',fontweight='bold')
            else:
                ax.set_title(p['title'])
            ax.set_xlabel(p['xlabel'] or xname)
            ax.set_ylabel(p['ylabel'] or yname)
            if p['xlog']: ax.set_xscale('log')
            if p['ylog']: ax.set_yscale('log')
            for name in ('x','y'):
                limits=_bounds(p[name+'lim'],name.upper()+'轴范围')
                if limits:
                    if p[name+'log'] and limits[0]<=0:
                        raise ValueError('对数轴范围须大于0。')
                    getattr(ax,'set_'+name+'lim')(*limits)
            if p['grid']:
                ax.grid(True,alpha=.2)
            else:
                ax.grid(False)
            if project.get('style', 'classic') == 'classic':
                ax.tick_params(direction='in',top=True,right=True)
            if p['legend'] and ax.get_legend_handles_labels()[0]:
                ax.legend(frameon=False,fontsize=style_rc(project).get('legend.fontsize',max(5,fs-2)),loc='best')
        return fig
