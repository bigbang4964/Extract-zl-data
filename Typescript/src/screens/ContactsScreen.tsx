import React, { useEffect, useState } from "react";
import { View, Text, FlatList, Button, Alert, Image, StyleSheet } from "react-native";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import * as SQLite from "expo-sqlite";

import { exportContactsToCSV, exportContactsToExcel } from "../utils/exportUtils";

// Định nghĩa kiểu dữ liệu cho một contact (dòng dữ liệu trong bảng info-cache)
type Contact = {
  key: string;   // ID hoặc UID của người dùng
  name: string;  // Tên hiển thị (zName)
  avatar: string; // Ảnh đại diện
  raw: string;   // Dữ liệu JSON gốc
};

export default function ContactsScreen() {
  const [contacts, setContacts] = useState<Contact[]>([]); // State lưu danh sách contact

  // Hàm useEffect chạy khi component mount để load dữ liệu từ SQLite
  useEffect(() => {
    async function load() {
      try {
        // Mở database SQLite (Storage.db phải được copy sẵn vào documentDirectory hoặc Download)
        const db = SQLite.openDatabaseSync("Storage.db");

        // Truy vấn tất cả dữ liệu từ bảng 'info-cache'
        const rows = (await db.getAllAsync(
          "SELECT key, val FROM 'info-cache'"
        )) as { key: string; val: string }[];

        // Parse từng dòng JSON để lấy thông tin người dùng
        const data: Contact[] = rows.map((row) => {
          try {
            const obj = JSON.parse(row.val);
            return {
              key: row.key,
              name: obj.zName ?? "",      // Nếu không có zName thì để chuỗi rỗng
              avatar: obj.avatar ?? "",   // Nếu không có avatar thì để rỗng
              raw: row.val,               // Lưu dữ liệu JSON gốc (phòng khi cần xuất)
            };
          } catch {
            // Nếu parse lỗi JSON
            return { key: row.key, name: "", avatar: "", raw: "" };
          }
        });

        // Cập nhật state hiển thị danh sách contact
        setContacts(data);
      } catch (e) {
        console.error("DB load error:", e);
      }
    }

    load();
  }, []);

  // Hàm xuất danh bạ ra file CSV
  const handleExportCSV = async () => {
    try {
      // Tạo đường dẫn file CSV trong thư mục documentDirectory
      const fileUri = FileSystem.Paths.document + "contacts.csv";

      // Gọi hàm tiện ích xuất CSV
      await exportContactsToCSV(contacts, fileUri);

      // Chia sẻ file (qua ứng dụng khác như Zalo, Gmail, Drive, ...)
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export CSV error", String(e));
    }
  };

  // Hàm xuất danh bạ ra file Excel (.xlsx)
  const handleExportExcel = async () => {
    try {
      // Tạo đường dẫn file Excel trong thư mục documentDirectory
      const fileUri = FileSystem.Paths.document + "contacts.xlsx";

      // Gọi hàm tiện ích xuất Excel
      await exportContactsToExcel(contacts, fileUri);

      // Chia sẻ file
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export Excel error", String(e));
    }
  };

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 18, fontWeight: "bold" }}>Danh bạ Zalo</Text>

      {/* Hiển thị danh sách contact bằng FlatList */}
      <FlatList
        data={contacts}
        keyExtractor={(item) => item.key}
        renderItem={({ item }) => (
          <View style={styles.item}>
            {/* Nếu có ảnh đại diện thì hiển thị, nếu không thì placeholder */}
            {item.avatar ? (
              <Image source={{ uri: item.avatar }} style={styles.avatar} />
            ) : (
              <View style={styles.avatarPlaceholder} />
            )}
            <View>
              <Text style={styles.name}>{item.name}</Text>
              <Text style={styles.uid}>{item.key}</Text>
            </View>
          </View>
        )}
      />

      {/* Nút xuất CSV và Excel */}
      <Button title="Export CSV" onPress={handleExportCSV} />
      <Button title="Export Excel" onPress={handleExportExcel} />
    </View>
  );
}

// Style cho các phần tử hiển thị
const styles = StyleSheet.create({
  item: {
    flexDirection: "row",
    padding: 10,
    borderBottomWidth: 1,
    borderColor: "#ddd",
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    marginRight: 10,
  },
  avatarPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#ccc",
    marginRight: 10,
  },
  name: { fontSize: 16, fontWeight: "600" },
  uid: { fontSize: 12, color: "#666" },
});