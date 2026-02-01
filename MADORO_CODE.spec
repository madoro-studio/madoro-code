# -*- mode: python ; coding: utf-8 -*-

# MADORO CODE - PyInstaller build spec
# Lightweight build excluding unnecessary ML libraries

hidden_imports = [
    # Internal modules
    'ui',
    'ui.chat_window',
    'ui.project_dialog',
    'ui.settings_dialog',
    'ui.handover_dialog',
    'agent',
    'llm',
    'memory',
    'context',
    'tools',
    'project_manager',
    # PyQt6
    'PyQt6',
    'PyQt6.QtWidgets',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    # Core dependencies
    'yaml',
    'sqlite3',
    'requests',
    # API clients
    'anthropic',
    'openai',
    'google.generativeai',
    # HTTP dependencies
    'httpx',
    'httpcore',
    'anyio',
    'sniffio',
    'certifi',
    'idna',
    'charset_normalizer',
]

# Exclude large libraries not needed
excludes = [
    'torch',
    'torchvision',
    'torchaudio',
    'tensorflow',
    'keras',
    'numpy',
    'pandas',
    'scipy',
    'sklearn',
    'matplotlib',
    'PIL',
    'cv2',
    'transformers',
    'huggingface_hub',
    'datasets',
    'tokenizers',
    'numba',
    'llvmlite',
    'pyarrow',
    'onnxruntime',
    'triton',
    'bitsandbytes',
    'accelerate',
    'safetensors',
    'sentencepiece',
    'librosa',
    'soundfile',
    'tkinter',
    '_tkinter',
]

a = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src', 'src'),
        ('config', 'config'),
        ('assets', 'assets'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name='MADORO_CODE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False for release (no terminal window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
