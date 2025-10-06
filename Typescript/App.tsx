import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { NavigationContainer } from "@react-navigation/native";
import { Provider as PaperProvider } from "react-native-paper";
import { MaterialIcons } from "@expo/vector-icons";

import HomeScreen from "./src/screens/HomeScreen";
import ContactsScreen from "./src/screens/ContactsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import MessagesScreen from "./src/screens/MessagesScreen"; 
import GroupsScreen from "./src/screens/GroupsScreen"; // import GroupsScreen

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <PaperProvider>
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={({ route }) => ({
            headerShown: true,
            tabBarIcon: ({ color, size }) => {
              let iconName: keyof typeof MaterialIcons.glyphMap = "home";

              if (route.name === "Home") iconName = "home";
              else if (route.name === "Contacts") iconName = "contacts";
              else if (route.name === "Settings") iconName = "settings";

              return <MaterialIcons name={iconName} size={size} color={color} />;
            },
            tabBarActiveTintColor: "#2196f3",
            tabBarInactiveTintColor: "gray",
          })}
        >
          <Tab.Screen name="Home" component={HomeScreen} />
          <Tab.Screen name="Contacts" component={ContactsScreen} />
          <Tab.Screen name="Settings" component={SettingsScreen} />
          <Tab.Screen name="Messages" component={MessagesScreen} />
          <Tab.Screen name="Groups" component={GroupsScreen} />
        </Tab.Navigator>
      </NavigationContainer>
    </PaperProvider>
  );
}
