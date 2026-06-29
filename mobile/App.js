import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Ionicons } from "@expo/vector-icons";
import { StatusBar } from "expo-status-bar";
import HomeScreen from "./src/screens/HomeScreen";
import DecisionsScreen from "./src/screens/DecisionsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ focused, color, size }) => {
            let iconName;
            if (route.name === "持仓") iconName = focused ? "wallet" : "wallet-outline";
            else if (route.name === "信号") iconName = focused ? "pulse" : "pulse-outline";
            else if (route.name === "设置") iconName = focused ? "settings" : "settings-outline";
            return <Ionicons name={iconName} size={size} color={color} />;
          },
          tabBarActiveTintColor: "#58a6ff",
          tabBarInactiveTintColor: "#8b949e",
          tabBarStyle: {
            backgroundColor: "#161b22",
            borderTopColor: "#30363d",
          },
          headerStyle: { backgroundColor: "#0d1117" },
          headerTintColor: "#e6edf3",
          headerTitleStyle: { fontWeight: "bold" },
        })}
      >
        <Tab.Screen name="持仓" component={HomeScreen} />
        <Tab.Screen name="信号" component={DecisionsScreen} />
        <Tab.Screen name="设置" component={SettingsScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
