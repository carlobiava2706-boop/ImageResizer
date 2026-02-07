# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['Resizer2.0.py'],  # Your script name
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinterdnd2',
        'numpy',
        'scipy',
        'pandas',
        'matplotlib',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ImageResizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,      # CRITICAL: Handles files dropped on app icon
    target_arch='arm64',      # 'arm64' for M1/M2 only, 'universal2' for Intel+M1
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ImageResizer'
)

app = BUNDLE(
    coll,
    name='ImageResizer.app',
    icon=None,  # Add 'icon.icns' here if you have one
    bundle_identifier='com.carlo.imageresizer',
    info_plist={
        'CFBundleShortVersionString': '2.0.0',
        'CFBundleVersion': '2.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Image File',
                'CFBundleTypeExtensions': ['png', 'jpg', 'jpeg', 'bmp', 'webp', 'tiff', 'tif', 'gif'],
                'CFBundleTypeRole': 'Editor',
            }
        ],
        'NSRequiresAquaSystemAppearance': False,
    },
)