import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { NavigationContainer } from "@react-navigation/native";
import { Provider as PaperProvider } from "react-native-paper";
import { MaterialIcons } from "@expo/vector-icons";

// Import các màn hình chính
import HomeScreen from "./src/screens/HomeScreen";
import ContactsScreen from "./src/screens/ContactsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import MessagesScreen from "./src/screens/MessagesScreen";
import GroupsScreen from "./src/screens/GroupsScreen"; // Màn hình nhóm

// Khởi tạo Bottom Tab Navigator
const Tab = createBottomTabNavigator();

export default function App() {
  return (
    // PaperProvider: Cung cấp context cho các component của react-native-paper (theme, màu sắc,...)
    <PaperProvider>
      {/* NavigationContainer: Bao bọc toàn bộ hệ thống điều hướng */}
      <NavigationContainer>
        {/* Cấu hình thanh điều hướng dưới (Bottom Tabs) */}
        <Tab.Navigator
          screenOptions={({ route }) => ({
            headerShown: true, // Hiển thị thanh tiêu đề trên cùng
            tabBarIcon: ({ color, size }) => {
              // Xác định icon tương ứng với từng màn hình
              let iconName: keyof typeof MaterialIcons.glyphMap = "home";

              if (route.name === "Home") iconName = "home";
              else if (route.name === "Contacts") iconName = "contacts";
              else if (route.name === "Settings") iconName = "settings";
              else if (route.name === "Messages") iconName = "message";
              else if (route.name === "Groups") iconName = "group";

              // Trả về icon hiển thị trong thanh tab
              return <MaterialIcons name={iconName} size={size} color={color} />;
            },
            tabBarActiveTintColor: "#2196f3", // Màu khi tab được chọn
            tabBarInactiveTintColor: "gray",  // Màu khi tab chưa được chọn
          })}
        >
          {/* Định nghĩa các màn hình/tab */}
          <Tab.Screen name="Home" component={HomeScreen} />
          <Tab.Screen name="Contacts" component={ContactsScreen} />
          <Tab.Screen name="Messages" component={MessagesScreen} />
          <Tab.Screen name="Groups" component={GroupsScreen} />
          <Tab.Screen name="Settings" component={SettingsScreen} />
        </Tab.Navigator>
      </NavigationContainer>
    </PaperProvider>
  );
}