import os
import sqlite3
import pandas as pd

def find_sqlite_files(workspace_path: str):
    """
    Quét workspace tìm tất cả file sqlite
    """
    sqlite_files = []
    for root, _, files in os.walk(workspace_path):
        for f in files:
            if f.endswith((".db", ".sqlite", ".sqlite3")):
                sqlite_files.append(os.path.join(root, f))
    return sqlite_files

def export_messages_to_csv(sqlite_file: str, output_dir: str):
    """
    Xuất bảng messages từ sqlite ra CSV
    """
    try:
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()

        # Kiểm tra bảng messages có tồn tại không
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='messages';
        """)
        if not cursor.fetchone():
            print(f"[SKIP] {sqlite_file} không có bảng messages")
            return

        # Đọc dữ liệu
        df = pd.read_sql_query("SELECT * FROM messages", conn)
        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(sqlite_file))[0]
        out_csv = os.path.join(output_dir, f"{base_name}_messages.csv")

        df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"[OK] Xuất messages từ {sqlite_file} → {out_csv}")

    except Exception as e:
        print(f"[ERROR] {sqlite_file}: {e}")
    finally:
        conn.close()

def run_parser(workspace_path: str, output_dir: str = "exports"):
    sqlite_files = find_sqlite_files(workspace_path)
    if not sqlite_files:
        print("❌ Không tìm thấy file sqlite nào.")
        return
    for db_file in sqlite_files:
        export_messages_to_csv(db_file, output_dir)

if __name__ == "__main__":
    # Ví dụ chạy parser trong thư mục hiện tại
    run_parser(".")
