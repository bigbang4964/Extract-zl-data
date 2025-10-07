import React, { useEffect, useState } from "react";
import { View, Text, FlatList, Button, Alert, StyleSheet } from "react-native";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import * as SQLite from "expo-sqlite";
import { exportGroupsToCSV, exportGroupsToExcel } from "../utils/exportUtils";

// Định nghĩa kiểu dữ liệu nhóm (Group)
type Group = {
  id: string;
  name: string;
  memberCount: number;
};

export default function GroupsScreen() {
  // Danh sách nhóm được lưu trong state
  const [groups, setGroups] = useState<Group[]>([]);

  useEffect(() => {
    // Hàm load() được gọi khi component mount
    async function load() {
      try {
        // 🟢 Mở database SQLite (file Storage.db đã được copy vào thư mục app)
        const db = await SQLite.openDatabaseAsync("Storage.db");

        // 🟢 Lấy 500 dòng đầu tiên trong bảng info-cache
        const rows = await db.getAllAsync<{ key: string; val: string }>(
          "SELECT key, val FROM 'info-cache' LIMIT 500"
        );

        const data: Group[] = [];
        // 🟢 Duyệt từng dòng trong bảng
        for (let r of rows) {
          try {
            const obj = JSON.parse(r.val); // parse JSON trong cột val
            // Nếu là nhóm (zType = "group") thì thêm vào danh sách
            if (obj.zType === "group") {
              data.push({
                id: r.key,
                name: obj.zName || "No name",
                memberCount: obj.memberCount || 0,
              });
            }
          } catch (e) {
            console.warn("Parse error", e);
          }
        }

        // Cập nhật danh sách nhóm vào state
        setGroups(data);
      } catch (e) {
        console.error("Load groups error", e);
      }
    }

    load();
  }, []);

  // 🟡 Xuất danh sách nhóm ra file CSV
  const handleExportCSV = async () => {
    try {
      // Tạo đường dẫn file CSV trong thư mục Documents
      const fileUri = FileSystem.Paths.document + "groups.csv";

      // Gọi hàm tiện ích xuất CSV
      await exportGroupsToCSV(groups, fileUri);

      // Mở menu chia sẻ file
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export CSV error", String(e));
    }
  };

  // 🟡 Xuất danh sách nhóm ra file Excel (.xlsx)
  const handleExportExcel = async () => {
    try {
      const fileUri = FileSystem.Paths.document + "groups.xlsx";
      await exportGroupsToExcel(groups, fileUri);
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export Excel error", String(e));
    }
  };

  // 🟣 Giao diện hiển thị danh sách nhóm và nút xuất file
  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 18, fontWeight: "bold" }}>Danh sách nhóm</Text>

      {/* Hiển thị danh sách nhóm bằng FlatList */}
      <FlatList
        data={groups}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.item}>
            <Text style={styles.name}>{item.name}</Text>
            <Text>ID: {item.id}</Text>
            <Text>Thành viên: {item.memberCount}</Text>
          </View>
        )}
      />

      {/* Hai nút xuất CSV / Excel */}
      <Button title="Export CSV" onPress={handleExportCSV} />
      <Button title="Export Excel" onPress={handleExportExcel} />
    </View>
  );
}

// 🧩 Styles cho giao diện
const styles = StyleSheet.create({
  item: { padding: 10, borderBottomWidth: 1, borderColor: "#ddd" },
  name: { fontWeight: "bold", fontSize: 15 },
});