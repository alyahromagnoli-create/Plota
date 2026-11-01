from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def test_singlefile_resources_are_separate_from_writable_files():
    from app_paths import locations
    resource,base,runtime=locations(Path('X:/Temp/_MEI123/app.py'),Path('E:/Tools/Plota.exe'),True)
    assert resource == Path('X:/Temp/_MEI123')
    assert base == Path('E:/Tools')
    assert runtime.is_relative_to(base)
    assert not runtime.is_relative_to(resource)


def test_export_location_is_not_bound_to_developer_drive():
    from app import App
    target=Path('E:/MyResearch/figure/project.json').resolve()
    assert App.check_output_path(target)==target
