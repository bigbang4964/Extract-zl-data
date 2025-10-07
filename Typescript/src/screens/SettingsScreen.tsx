import React from "react";
import { View, Text, Button, StyleSheet } from "react-native";

// Màn hình Cài đặt (Settings)
export default function SettingsScreen() {
  return (
    <View style={styles.container}>
      {/* Tiêu đề màn hình */}
      <Text style={styles.title}>⚙️ Settings</Text>

      {/* Nội dung mô tả ngắn */}
      <Text>Theme, app info, etc.</Text>

      {/* Nút đổi giao diện (theme) – tạm thời chỉ hiển thị thông báo */}
      <Button
        title="Switch Theme"
        onPress={() => alert("Chức năng đổi theme")} // Khi bấm sẽ hiển thị thông báo
      />
    </View>
  );
}

// Style cho giao diện
const styles = StyleSheet.create({
  container: {
    flex: 1,                      // Chiếm toàn bộ màn hình
    justifyContent: "center",     // Căn giữa theo chiều dọc
    alignItems: "center",         // Căn giữa theo chiều ngang
    padding: 16,                  // Khoảng cách lề
  },
  title: {
    fontSize: 20,                 // Cỡ chữ lớn
    fontWeight: "bold",           // Chữ đậm
    marginBottom: 16,             // Cách phần dưới 16px
  },
});