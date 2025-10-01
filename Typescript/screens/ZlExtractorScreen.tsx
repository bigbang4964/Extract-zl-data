import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  Alert,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
// LƯU Ý: Ở một số phiên bản Expo, expo-file-system không export trực tiếp "File" và "Paths".
// Đây là import mà bạn đang dùng trong file gốc. Tuỳ SDK bạn dùng, các API này có thể không tồn tại
// (trong trường hợp đó bạn sẽ cần dùng FileSystem.copyAsync / writeAsStringAsync hoặc API mới File.copy / File.write).
import { Directory, File, Paths } from 'expo-file-system';
import * as SQLite from "expo-sqlite";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import { Picker } from "@react-native-picker/picker";
import { Button } from "react-native-paper";
import { Buffer } from "buffer"; // dùng để convert ArrayBuffer -> base64
import * as ExcelJS from "exceljs"; // ExcelJS (không phải default export)

const PAGE_SIZE = 200; // Số hàng tải mỗi lần (pagination)

export default function ZlExtractorScreen() {
  // --- State của component ---
  const [db, setDb] = useState<SQLite.SQLiteDatabase | null>(null); // đối tượng DB (expo-sqlite)
  const [tables, setTables] = useState<string[]>([]); // danh sách tên bảng có trong DB
  const [selectedTable, setSelectedTable] = useState<string>(""); // bảng đang được chọn
  const [data, setData] = useState<any[]>([]); // dữ liệu của trang hiện tại
  const [page, setPage] = useState(0); // số trang hiện tại (0-based)
  const [totalRows, setTotalRows] = useState(0); // tổng số dòng trong bảng

  // =========================
  // Hàm: pickDatabase
  // Chức năng:
  // 1. Mở DocumentPicker để người dùng chọn file .db
  // 2. Copy (đặt) file vào sandbox app (đường dẫn do Paths hoặc FileSystem cung cấp)
  // 3. Mở database bằng expo-sqlite
  // 4. Lấy danh sách bảng và lưu vào state
  // LƯU Ý: API File/Paths ở đây có thể khác giữa các SDK; nếu runtime báo lỗi liên quan đến File/Paths,
  // thì cần thay bằng FileSystem.copyAsync(...) và mở DB đúng cách theo version của expo-sqlite.
  // =========================
  const pickDatabase = async () => {
    try {
      // Mở picker
      const result = await DocumentPicker.getDocumentAsync({
        type: "*/*",
        copyToCacheDirectory: true,
      });

      // Nếu người dùng huỷ, result.canceled = true (trong API mới) -> thoát
      if (result.canceled) return;

      try{
        // NOTE: bạn đang dùng File API (File, Paths) — tuỳ SDK, đoạn này có thể hoạt động hoặc throw.
        // Tạo đối tượng File từ URI nguồn (file được chọn)
        const file = new File(result.assets[0].uri);
        // Tạo file đích trong thư mục document app
        const dest = new File(Paths.document, "zltmp.db");

        // Nếu đã tồn tại file đích thì xoá để tránh ghi đè lạ
        if(dest.exists){
            dest.delete();
        }
        // Copy file vào sandbox của app
        // NOTE: phương thức copy ở đây là API của File class (tuỳ SDK)
        file.copy(dest);
        console.log("Copied to", dest.uri);
      } catch (e) {
        // Nếu phần File/Paths không hoạt động trên SDK của bạn, sẽ rơi vào đây.
        // Hãy kiểm tra error log để biết nên dùng FileSystem.copyAsync hay File.copy (file API mới).
        console.error("Error copying file:", e);
      }

      // Mở database — ở code gốc bạn dùng openDatabaseSync("zltmp.db").
      // Nếu bạn đã copy file vào document-directory với tên zltmp.db, openDatabaseSync("zltmp.db")
      // sẽ tìm file dựa trên tên; tuy nhiên tuỳ platform bạn có thể cần mở bằng đường dẫn đầy đủ.
      const dbConn = SQLite.openDatabaseSync("zltmp.db");
      setDb(dbConn);

      // Lấy danh sách bảng bằng getAllAsync (nếu triển khai) — đây là API của 'next' expo-sqlite.
      const rows = await dbConn.getAllAsync<{ name: string }>(
        "SELECT name FROM sqlite_master WHERE type='table'"
      );
      setTables(rows.map((r) => r.name));

      Alert.alert("OK", "Đã mở database");
    } catch (e: any) {
      // Hiển thị lỗi nếu có
      Alert.alert("Error", e.message);
    }
  };

  // =========================
  // Hàm: loadTable
  // Chức năng: tải dữ liệu của bảng theo trang (pageNum), cập nhật totalRows và data
  // - Nếu db hỗ trợ getFirstAsync/getAllAsync (API mới) thì dùng trực tiếp
  // - Nếu không (hoặc bạn dùng API cũ) cần viết fallback dùng transaction/executeSql
  // Lưu ý: hàm không set selectedTable để tránh vòng lặp setState khi Picker cũng gọi setSelectedTable
  // =========================
  const loadTable = useCallback(
  async (table: string, pageNum = 0) => {
    if (!db) return;
    try {
      // Cập nhật page trước, sau đó query
      setPage(pageNum);

      // Lấy tổng số dòng của bảng
      const cntRow = await db.getFirstAsync<{ cnt: number }>(
        `SELECT COUNT(*) as cnt FROM ${table}`
      );
      setTotalRows(cntRow?.cnt ?? 0);

      // Lấy dữ liệu phân trang
      const rows = await db.getAllAsync<any>(
        `SELECT * FROM ${table} LIMIT ${PAGE_SIZE} OFFSET ${
          pageNum * PAGE_SIZE
        }`
      );
      // Lưu mảng object trả về vào state (1 lần setData) — tránh setState trong vòng lặp
      setData(rows);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    }
  },
  [db]
);

  // Điều hướng trang Next / Prev
  const nextPage = () => {
    if ((page + 1) * PAGE_SIZE >= totalRows) return; // nếu đã hết thì không next
    loadTable(selectedTable, page + 1);
  };

  const prevPage = () => {
    if (page === 0) return; // trang đầu
    loadTable(selectedTable, page - 1);
  };

  // =========================
  // Hàm: exportExcel
  // - Tạo workbook bằng ExcelJS
  // - Ghi dữ liệu của trang hiện tại vào file .xlsx
  // - Lưu file bằng API File (ở code gốc dùng File(Paths.document,...))
  // LƯU Ý: ExcelJS.writeBuffer() trả về ArrayBuffer. Trong RN/Expo ta thường convert sang base64
  // và ghi file bằng API write với encoding base64. Tuỳ SDK bạn có thể cần chuyển sang FileSystem.writeAsStringAsync.
  // =========================
  const exportExcel = async () => {
    if (data.length === 0) {
      Alert.alert("Chưa có dữ liệu");
      return;
    }
    try {
      const wb = new ExcelJS.Workbook();
      const ws = wb.addWorksheet("Zalo Data");

      // Tạo header/cột từ keys của object đầu tiên
      ws.columns = Object.keys(data[0]).map((key) => ({
        header: key,
        key,
        width: 20,
      }));

      // Thêm từng row (lưu ý: không dùng nhiều setState ở đây)
      data.forEach((row) => ws.addRow(row));

      // ExcelJS trả về ArrayBuffer
      const buffer = await wb.xlsx.writeBuffer();

      // Việc lưu file tiếp theo dùng File API (File(Paths.document, ...))
      // LƯU Ý: API File/Paths có thể không có trong SDK của bạn. Nếu không có, dùng FileSystem.writeAsStringAsync.
      const fileXlsx = new File(Paths.document, "zalo_data.xlsx");
      try{
        // create() và write() là method trên File object trong một số phiên bản
        fileXlsx.create();
        // Ghi string base64 với tuỳ chọn encoding
        fileXlsx.write(Buffer.from(buffer).toString("base64"),{ encoding: 'base64' });
      } catch (e){
        // Nếu phần File API không hoạt động, sẽ rơi vào đây: log lỗi để debug
        console.error("Error writing file:", e);
      }

      // Nếu device hỗ trợ Sharing, mở dialog chia sẻ
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(fileXlsx.uri);
      } else {
        Alert.alert("Đã lưu", fileXlsx.uri);
      }
    } catch (e: any) {
      Alert.alert("Error", e.message);
    }
  };

  // =========================
  // Hàm: exportPdf
  // - Dùng Print.printToFileAsync để render HTML thành PDF tạm
  // - Sau đó gọi Sharing.shareAsync(uri) để share file
  // =========================
  const exportPdf = async () => {
    if (data.length === 0) {
      Alert.alert("Chưa có dữ liệu");
      return;
    }
    try {
      let html = `<h2>Zalo Data - ${selectedTable}</h2><table border="1" cellspacing="0" cellpadding="3">`;

      html += "<tr>";
      Object.keys(data[0]).forEach((k) => {
        html += `<th>${k}</th>`;
      });
      html += "</tr>";

      data.forEach((row) => {
        html += "<tr>";
        Object.values(row).forEach((v) => {
          html += `<td>${v ?? ""}</td>`;
        });
        html += "</tr>";
      });
      html += "</table>";

      const { uri } = await Print.printToFileAsync({ html });

      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri);
      } else {
        Alert.alert("Đã lưu", uri);
      }
    } catch (e: any) {
      Alert.alert("Error", e.message);
    }
  };

  // =========================
  // Render UI
  // - Button: chọn DB
  // - Picker: chọn bảng
  // - FlatList: hiển thị dữ liệu (page current)
  // - Prev/Next: phân trang
  // - Export Excel / PDF
  // =========================
  return (
    <View style={styles.container}>
      <Button mode="contained" onPress={pickDatabase} style={styles.button}>
        Chọn DB SQLite
      </Button>

      {tables.length > 0 && (
        <>
          <Text style={styles.label}>Chọn bảng:</Text>
          <Picker
            selectedValue={selectedTable}
            onValueChange={(v) => {
                // Khi user chọn bảng: set state rồi call loadTable
                // Tránh gọi setSelectedTable trong loadTable để tránh vòng lặp
                setSelectedTable(v);
                loadTable(v, 0);
            }}
            style={styles.picker}
            >
            {tables.map((t) => (
                <Picker.Item key={t} label={t} value={t} />
            ))}
            </Picker>
        </>
      )}

      <FlatList
        data={data}
        keyExtractor={(_, i) => i.toString()}
        renderItem={({ item }) => (
          <Text style={styles.row}>{JSON.stringify(item)}</Text>
        )}
      />

      {data.length > 0 && (
        <>
          <View style={styles.pagination}>
            <Button mode="outlined" onPress={prevPage} disabled={page === 0}>
              Prev
            </Button>
            <Text>
              Trang {page + 1} / {Math.ceil(totalRows / PAGE_SIZE)}
            </Text>
            <Button
              mode="outlined"
              onPress={nextPage}
              disabled={(page + 1) * PAGE_SIZE >= totalRows}
            >
              Next
            </Button>
          </View>

          <View style={styles.footer}>
            <Button mode="outlined" onPress={exportExcel} style={styles.button}>
              Export Excel
            </Button>
            <Button mode="outlined" onPress={exportPdf} style={styles.button}>
              Export PDF
            </Button>
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 10, marginTop: 40 },
  button: { marginVertical: 5 },
  label: { marginTop: 10, fontWeight: "bold" },
  picker: { backgroundColor: "#eee", marginVertical: 10 },
  row: {
    borderBottomWidth: 1,
    borderColor: "#ccc",
    padding: 5,
    fontSize: 12,
  },
  pagination: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginVertical: 10,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginTop: 10,
  },
});
