"""
MADORO CODE - 메인 엔트리 포인트
"""

import sys
import os

# Windows 콘솔 UTF-8 강제 설정 (이모지 출력 문제 해결)
# PyInstaller --windowed 모드에서는 stdout/stderr가 None일 수 있음
if sys.platform == 'win32':
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def get_base_path():
    """PyInstaller EXE 또는 스크립트 실행 시 기본 경로 반환"""
    if getattr(sys, 'frozen', False):
        # PyInstaller EXE - 번들된 파일은 _MEIPASS에 있음
        return sys._MEIPASS
    else:
        # 스크립트 실행 시
        return os.path.dirname(os.path.abspath(__file__))


def get_exe_path():
    """EXE 파일이 있는 실제 디렉토리 (사용자 데이터용)"""
    if getattr(sys, 'frozen', False):
        # sys.executable gives the actual EXE path, not the shortcut location
        exe_path = os.path.dirname(os.path.abspath(sys.executable))
        print(f"[Main] sys.executable: {sys.executable}")
        return exe_path
    else:
        return os.path.dirname(os.path.abspath(__file__))

# 경로 설정
BASE_PATH = get_base_path()      # 번들된 파일 (config, assets 등)
EXE_PATH = get_exe_path()        # 사용자 데이터 (projects, db 등)

print(f"[Main] BASE_PATH (bundle): {BASE_PATH}")
print(f"[Main] EXE_PATH (user data): {EXE_PATH}")
print(f"[Main] frozen: {getattr(sys, 'frozen', False)}")

# src 폴더를 경로에 추가
src_path = os.path.join(BASE_PATH, "src")
sys.path.insert(0, src_path)

# 작업 디렉토리는 EXE 위치로 설정 (사용자 데이터 접근용)
os.chdir(EXE_PATH)
print(f"[Main] CWD: {os.getcwd()}")

# 환경변수로 경로 전달
os.environ['MADORO_CODE_BASE'] = EXE_PATH      # 사용자 데이터 경로
os.environ['MADORO_CODE_BUNDLE'] = BASE_PATH   # 번들된 리소스 경로

# config 파일 존재 확인 (번들에서)
config_path = os.path.join(BASE_PATH, "config", "models.yaml")
print(f"[Main] Config path: {config_path}")
print(f"[Main] Config exists: {os.path.exists(config_path)}")

from ui.chat_window import main

if __name__ == "__main__":
    main()
