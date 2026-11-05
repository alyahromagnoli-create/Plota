# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
root=Path(SPECPATH).parent
a=Analysis([str(root/'app.py')],pathex=[str(root)],binaries=[],
    datas=[(str(root/'assets/demo_thermo.out'),'assets'),
           (str(root/'assets/plota.ico'),'assets'),
           (str(root/'assets/scienceplots'),'assets/scienceplots'),
           (str(root/'assets/gallery'),'assets/gallery'),
           (str(root/'licenses'),'licenses'),
           (str(root/'engine_source.txt'),'.')]+collect_data_files('tkinterdnd2'),
    hiddenimports=['openpyxl','xlrd','odf','h5py','pyarrow.parquet','pyarrow.feather','matplotlib.backends.backend_tkagg','matplotlib.backends.backend_pdf','matplotlib.backends.backend_svg'],
    hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=['scipy','IPython','pytest','torch','tensorflow','notebook','sympy','cv2','PyQt5','PyQt6','PySide6','setuptools','numba','sphinx'],
    noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='Plota',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=False,
    disable_windowed_traceback=False,runtime_tmpdir=None,
    icon=str(root/'assets/plota.ico'),uac_admin=False)
