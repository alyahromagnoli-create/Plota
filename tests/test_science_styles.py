import copy
import hashlib
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
import engine
from dataio import Dataset
from exporter import export_bundle, save_project, load_project


def fixture_project(style):
    p = engine.new_project()
    p.update(style=style, width_mm=160, height_mm=90, aspect_ratio='16:9')
    layer = engine.new_layer('a', 'x', 'y')
    layer.update(engine.layer_style(p, 0))
    p['panels'][0].update(layers=[layer], xlabel='Time (ps)', ylabel='Energy')
    ds = Dataset('a', 'test', pd.DataFrame({'x': np.arange(10.), 'y': np.sin(np.arange(10.))}), '', {})
    return p, {'a': ds}


def test_style_default_and_legacy_fallback():
    assert engine.new_project()['style'] == 'science'
    assert engine.style_rc({'fontsize': 10, 'font': 'DejaVu Sans'})['axes.linewidth'] == .8
    assert engine.style_rc(engine.new_project())['text.usetex'] is False


@pytest.mark.parametrize('style', ['classic', 'science', 'ieee', 'nature', 'bright'])
def test_presets_render_and_reproduce_without_extra_dependencies(tmp_path, style):
    p, ds = fixture_project(style)
    before = copy.deepcopy(p)
    prior = matplotlib.rcParams.copy()
    fig = engine.render_project(p, ds)
    assert p == before
    assert matplotlib.rcParams == prior
    assert fig.axes[0].lines[0].get_color() == p['panels'][0]['layers'][0]['color']
    assert fig.axes[0].spines['left'].get_linewidth() == (.8 if style == 'classic' else .5)
    target = export_bundle(p, ds, tmp_path / style)
    digest = hashlib.sha256((target / 'figure.png').read_bytes()).hexdigest()
    result = subprocess.run([sys.executable, str(target / 'plot.py')], capture_output=True, timeout=45)
    assert result.returncode == 0, result.stderr
    assert digest == hashlib.sha256((target / 'figure.png').read_bytes()).hexdigest()
    from PIL import Image
    w, h = Image.open(target / 'figure.png').size
    assert w / h == pytest.approx(16 / 9, abs=.002)
    assert (target / 'SciencePlots_LICENSE.txt').exists()
    assert 'scienceplots' not in (target / 'requirements.txt').read_text().lower()


def test_ieee_line_cycle_and_manual_overrides():
    p, ds = fixture_project('ieee')
    assert engine.layer_style(p, 1)['linestyle'] == '--'
    assert engine.layer_style(p, 2)['linestyle'] == ':'
    p['panels'][0]['layers'][0].update(color='#ff00ff', linewidth=2.7, linestyle='-.')
    p.update(font='DejaVu Sans', fontsize=12)
    ax = engine.render_project(p, ds).axes[0]
    assert ax.lines[0].get_color() == '#ff00ff'
    assert ax.lines[0].get_linewidth() == 2.7
    assert ax.xaxis.label.get_fontsize() == 12


def test_project_roundtrip_and_unknown_style(tmp_path):
    p, ds = fixture_project('nature')
    save_project(p, ds, tmp_path / 'project.json')
    restored, _ = load_project(tmp_path / 'project.json')
    assert restored == p
    p['style'] = 'missing'
    with pytest.raises(ValueError, match='风格'):
        engine.render_project(p, ds)
