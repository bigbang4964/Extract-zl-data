import React, { useEffect, useState } from "react";
import { View, Text, FlatList, Button, Alert, StyleSheet } from "react-native";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import * as SQLite from "expo-sqlite";
import { exportGroupsToCSV, exportGroupsToExcel } from "../utils/exportUtils";

type Group = {
  id: string;
  name: string;
  memberCount: number;
};

export default function GroupsScreen() {
  const [groups, setGroups] = useState<Group[]>([]);

  useEffect(() => {
    async function load() {
      try {
        // mở DB (đã copy sẵn vào documentDirectory hoặc Download)
        const db = await SQLite.openDatabaseAsync("Storage.db");

        // Lấy dữ liệu
        const rows = await db.getAllAsync<{ key: string; val: string }>(
          "SELECT key, val FROM 'info-cache' LIMIT 500"
        );

        const data: Group[] = [];
        for (let r of rows) {
          try {
            const obj = JSON.parse(r.val);
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
        setGroups(data);
      } catch (e) {
        console.error("Load groups error", e);
      }
    }
    load();
  }, []);

  const handleExportCSV = async () => {
    try {
      const fileUri = FileSystem.Paths.document + "groups.csv";
      await exportGroupsToCSV(groups, fileUri);
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export CSV error", String(e));
    }
  };

  const handleExportExcel = async () => {
    try {
      const fileUri = FileSystem.Paths.document + "groups.xlsx";
      await exportGroupsToExcel(groups, fileUri);
      await Sharing.shareAsync(fileUri);
    } catch (e) {
      Alert.alert("Export Excel error", String(e));
    }
  };

  return (
    <View style={{ flex: 1, padding: 16 }}>
      <Text style={{ fontSize: 18, fontWeight: "bold" }}>Danh sách nhóm</Text>
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
      <Button title="Export CSV" onPress={handleExportCSV} />
      <Button title="Export Excel" onPress={handleExportExcel} />
    </View>
  );
}

const styles = StyleSheet.create({
  item: { padding: 10, borderBottomWidth: 1, borderColor: "#ddd" },
  name: { fontWeight: "bold", fontSize: 15 },
});
