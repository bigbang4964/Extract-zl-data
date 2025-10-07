import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  Button,
  StyleSheet,
  Alert,
  Image,
  ScrollView,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { File, Paths  } from "expo-file-system";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SQLite from "expo-sqlite";

type UserInfo = {
  uid: string;
  zName: string;
  avatar: string;
};

/**
 * Copy file SQLite từ URI (content URI hoặc file URI) sang cache để SQLite mở được.
 * @param uri URI của file gốc
 * @param filename Tên file muốn lưu trong cache (mặc định giữ nguyên tên file)
 * @returns string đường dẫn đầy đủ tới file cache
 */
export async function copyToCacheForSQLite(
  uri: string,
  filename?: string
): Promise<string> {
  try {
    // Lấy tên file từ filename hoặc URI
    const name = filename ?? uri.split("/").pop() ?? "temp.db";
    const cachePath = Paths.cache.uri + name; // string path cho SQLite

    const sourceFile = new File(uri); // file gốc (có thể là content URI)
    const cacheFile = new File(cachePath); // file trong cache

    // Nếu file cache đã tồn tại thì xóa
    if (await cacheFile.exists) {
      await cacheFile.delete();
    }

    // Đọc nội dung file gốc dưới dạng Base64
    const contentBase64 = await sourceFile.base64Sync();

    // Ghi Base64 vào cacheFile (chỉ 2 tham số: string, options)
    await cacheFile.write(contentBase64, { encoding: "base64" });

    // Trả về đường dẫn string để dùng cho SQLite
    return cachePath;
  } catch (e) {
    console.error("Lỗi copy file sang cache:", e);
    throw e;
  }
}

export default function HomeScreen() {
  const [configPath, setConfigPath] = useState<string | null>(null);
  const [storagePath, setStoragePath] = useState<string | null>(null);
  const [uid, setUid] = useState<string | null>(null);
  const [info, setInfo] = useState<UserInfo | null>(null);

  useEffect(() => {
    (async () => {
      // Load các đường dẫn và UID đã lưu trước đó
      const savedConfig = await AsyncStorage.getItem("configPath");
      const savedStorage = await AsyncStorage.getItem("storagePath");
      const savedUid = await AsyncStorage.getItem("uid");
      if (savedConfig) setConfigPath(savedConfig);
      if (savedStorage) setStoragePath(savedStorage);
      if (savedUid) setUid(savedUid);
    })();
  }, []);

  /**
   * Chọn file database-config.json và lấy UID
   */
  const pickConfigFile = async () => {
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: "application/json",
        copyToCacheDirectory: false,
      });
      if (res.canceled) return;

      const uri = res.assets?.[0]?.uri;
      if (!uri) return;

      const file = new File(uri);
      const content = await file.text();
      const json = JSON.parse(content);

      let extractedUid = "";
      if (json["sh_sqlite_m_d"]) {
        const parsed = JSON.parse(json["sh_sqlite_m_d"]);
        extractedUid = Object.keys(parsed)[0];
      }

      if (!extractedUid) {
        Alert.alert("❌ Không tìm thấy UID trong file config");
        return;
      }

      await AsyncStorage.setItem("configPath", uri);
      await AsyncStorage.setItem("uid", extractedUid);
      setConfigPath(uri);
      setUid(extractedUid);

      Alert.alert("✅ Đã đọc UID", `UID: ${extractedUid}`);
    } catch (e) {
      console.error("Lỗi đọc config:", e);
      Alert.alert("Lỗi đọc file config", String(e));
    }
  };

  /**
   * Chọn file Storage.db và đọc dữ liệu từ bảng info-cache
   */
  const pickStorageFile = async () => {
    if (!uid) {
      Alert.alert("⚠️ Chưa có UID, vui lòng chọn file database-config.json trước");
      return;
    }

    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: "application/octet-stream",
        copyToCacheDirectory: false,
      });
      if (res.canceled) return;

      const uri = res.assets?.[0]?.uri;
      if (!uri) return;

      // Copy file Storage.db sang cache để SQLite mở được
      const cachePath = await copyToCacheForSQLite(uri, "Storage.db");

      // Mở SQLite từ file cache
      const db = await SQLite.openDatabaseAsync(cachePath);

      // Lấy thông tin user từ bảng info-cache
      const rows = await db.getAllAsync<{ key: string; val: string }>(
        "SELECT key, val FROM 'info-cache' WHERE key = ? LIMIT 1",
        [uid]
      );

      if (rows.length === 0) {
        Alert.alert("Không tìm thấy info-cache cho UID này");
        return;
      }

      const data = JSON.parse(rows[0].val);
      const user: UserInfo = {
        uid,
        zName: data.zName ?? "Không rõ",
        avatar: data.avatar ?? "",
      };

      setInfo(user);
      await AsyncStorage.setItem("storagePath", uri);
      setStoragePath(uri);

      Alert.alert("✅ Đã đọc dữ liệu từ Storage.db", `Tên: ${user.zName}`);
    } catch (e) {
      console.error("Lỗi đọc Storage.db:", e);
      Alert.alert("Lỗi xử lý", String(e));
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>📂 Zalo Data Extractor</Text>

      <Text style={styles.text}>
        {configPath
          ? `Config file: ${configPath}`
          : "Chưa chọn file database-config.json"}
      </Text>
      <Button title="Chọn database-config.json" onPress={pickConfigFile} />

      {uid && (
        <>
          <View style={{ marginVertical: 12 }} />
          <Text style={styles.text}>UID hiện tại: {uid}</Text>
          <Button title="Chọn Storage.db" onPress={pickStorageFile} />
        </>
      )}

      {info && (
        <View style={styles.result}>
          <Text>UID: {info.uid}</Text>
          <Text>Tên: {info.zName}</Text>
          {info.avatar ? (
            <Image source={{ uri: info.avatar }} style={styles.avatar} />
          ) : (
            <Text>Không có ảnh đại diện</Text>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, justifyContent: "center", alignItems: "center", padding: 16 },
  title: { fontSize: 20, fontWeight: "bold", marginBottom: 16 },
  text: { fontSize: 16, marginVertical: 8, textAlign: "center" },
  result: { marginTop: 20, alignItems: "center" },
  avatar: { width: 100, height: 100, borderRadius: 50, marginTop: 8 },
});
