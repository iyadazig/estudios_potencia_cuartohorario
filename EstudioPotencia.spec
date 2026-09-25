# -*- mode: python ; coding: utf-8 -*-
# No lanzar directamente: usar construir_exe.py, que incluye las credenciales de Gemweb sin pasar por git,
# copia config/precios.json y el LEEME junto al .exe y comprueba el resultado.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('config/precios.json', 'config'), ('assets/logo_geype.png', 'assets')],
    hiddenimports=['matplotlib.backends.backend_tkagg', 'matplotlib.backends.backend_agg', 'xlrd', 'openpyxl',
                   'potencia._credenciales_incluidas'],     # lo genera construir_exe.py (no está en git)
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide6', 'PySide2', 'PyQt6', 'scipy', 'IPython', 'jupyter', 'notebook', 'sphinx',
              'dask', 'jedi', 'docutils', 'babel', 'black', 'pytest', 'sqlalchemy', 'numba', 'llvmlite',
              'tensorflow', 'torch', 'sklearn', 'statsmodels', 'bokeh', 'panel', 'holoviews', 'distributed',
              'pyarrow', 'tables', 'h5py', 'zmq', 'tornado', 'nbformat', 'win32com', 'pythoncom',
              'lxml', 'botocore', 'boto3', 'pygments', 'cryptography', 'sympy', 'numexpr', 'bottleneck',
              'fitz', 'pymupdf', 'pypdf'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EstudioPotencia',
    icon='assets/icono.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
