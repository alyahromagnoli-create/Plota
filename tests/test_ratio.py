import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import dimensions_for_ratio, ratio_for_dimensions


@pytest.mark.parametrize('ratio,expected',[('16:9',90),('1:1',160),('4:3',120)])
def test_preset_dimensions(ratio,expected):
    assert dimensions_for_ratio(160,100,ratio)==(160,expected)


def test_custom_dimensions_and_legacy_inference():
    assert dimensions_for_ratio(190,145,'custom')==(190,145)
    assert ratio_for_dimensions(180,135)=='4:3'
    assert ratio_for_dimensions(190,145)=='custom'
    with pytest.raises(ValueError): dimensions_for_ratio(160,90,'bad')


def test_preset_can_recover_from_empty_custom_height():
    assert dimensions_for_ratio(160,'','16:9')==(160,90)


@pytest.mark.parametrize('ratio',['16:9','1:1','4:3'])
def test_exported_canvas_matches_ratio(tmp_path,ratio):
    import pandas as pd
    import xml.etree.ElementTree as ET
    from PIL import Image
    from dataio import Dataset
    from engine import new_project,new_layer
    from exporter import export_bundle
    p=new_project()
    w,h=dimensions_for_ratio(160,100,ratio)
    p.update(width_mm=w,height_mm=h,aspect_ratio=ratio,dpi=150)
    ds=Dataset('a','a',pd.DataFrame({'x':[0,1,2],'y':[1,3,2]}),'',{})
    p['panels'][0]['layers']=[new_layer('a','x','y')]
    target=export_bundle(p,{'a':ds},tmp_path/'bundle')
    image=Image.open(target/'figure.png')
    expected=float(ratio.split(':')[0])/float(ratio.split(':')[1])
    assert abs(image.width-image.height*expected)<=expected+1
    viewbox=[float(v) for v in ET.parse(target/'figure.svg').getroot().attrib['viewBox'].split()]
    assert viewbox[2]/viewbox[3]==pytest.approx(expected)
