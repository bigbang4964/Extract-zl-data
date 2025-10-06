import * as SQLite from "expo-sqlite";
import * as FileSystem from "expo-file-system";

// mở database từ thư mục Download
export async function openDb(fileName: string) {
  const dbPath = `${FileSystem.Paths.document}${fileName}`;
  return SQLite.openDatabaseSync(dbPath);
}

// đọc toàn bộ info-cache
type InfoCacheRow = {
  key: string;
  val: string;
};

export async function getContacts(
  db: SQLite.SQLiteDatabase
): Promise<any[]> {
  try {
    // getAllAsync trả về unknown[] nên cần ép kiểu
    const rows = (await db.getAllAsync(
      "SELECT key, val FROM 'info-cache'"
    )) as InfoCacheRow[];

    const results: any[] = [];

    for (const row of rows) {
      try {
        const obj = JSON.parse(row.val);
        results.push({
          key: row.key,
          name: obj.zName ?? "",
          avatar: obj.avatar ?? "",
          raw: row.val,
        });
      } catch {
        results.push({
          key: row.key,
          name: "",
          avatar: "",
          raw: "",
        });
      }
    }

    return results;
  } catch (err) {
    console.error("Lỗi getContacts:", err);
    return [];
  }
}