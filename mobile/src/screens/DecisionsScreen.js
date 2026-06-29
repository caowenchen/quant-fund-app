import React, { useState, useCallback } from "react";
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { getDecisions, evaluateStrategy } from "../services/api";

const ACTION_ICONS = {
  stop_loss: { icon: "close-circle", color: "#f85149" },
  sell_all: { icon: "close-circle", color: "#f85149" },
  sell_half: { icon: "remove-circle", color: "#f0883e" },
  observe: { icon: "eye", color: "#d29922" },
  hold: { icon: "checkmark-circle", color: "#3fb950" },
  add: { icon: "add-circle", color: "#58a6ff" },
};

export default function DecisionsScreen() {
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await getDecisions(50);
      if (res.code === 0) setDecisions(res.data || []);
    } catch (e) {
      Alert.alert("错误", "无法连接服务器");
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchData();
    }, [])
  );

  const onEvaluate = async () => {
    setEvaluating(true);
    try {
      const res = await evaluateStrategy();
      if (res.code === 0) {
        Alert.alert("评估完成", `已为 ${res.data?.length || 0} 只基金生成决策`);
        fetchData();
      }
    } catch (e) {
      Alert.alert("错误", "策略评估失败");
    } finally {
      setEvaluating(false);
    }
  };

  const renderItem = ({ item }) => {
    const action = ACTION_ICONS[item.action] || ACTION_ICONS.hold;
    const profitColor = (item.current_return_rate || 0) >= 0 ? "#3fb950" : "#f85149";

    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Ionicons name={action.icon} size={28} color={action.color} />
          <View style={styles.headerText}>
            <Text style={styles.fundName}>{item.fund_name}</Text>
            <Text style={styles.fundCode}>{item.fund_code}</Text>
          </View>
          <View style={[styles.actionBadge, { backgroundColor: action.color + "22", borderColor: action.color }]}>
            <Text style={[styles.actionText, { color: action.color }]}>{item.decision}</Text>
          </View>
        </View>
        <View style={styles.divider} />
        <Text style={styles.reason}>{item.reason}</Text>
        <View style={styles.row}>
          <Text style={styles.label}>当前收益: </Text>
          <Text style={[styles.value, { color: profitColor }]}>
            {((item.current_return_rate || 0) * 100).toFixed(2)}%
          </Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>最高收益: </Text>
          <Text style={styles.value}>{((item.peak_return_rate || 0) * 100).toFixed(2)}%</Text>
        </View>
        {item.sector_change_pct !== undefined && (
          <View style={styles.row}>
            <Text style={styles.label}>板块: </Text>
            <Text style={[styles.value, { color: (item.sector_change_pct || 0) >= 0 ? "#f85149" : "#3fb950" }]}>
              {(item.sector_change_pct || 0) >= 0 ? "+" : ""}{(item.sector_change_pct || 0).toFixed(2)}%
            </Text>
          </View>
        )}
        <Text style={styles.time}>{item.created_at?.replace("T", " ").slice(0, 19)}</Text>
      </View>
    );
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#58a6ff" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={decisions}
        keyExtractor={(item) => `${item.fund_code}-${item.created_at}`}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={fetchData} tintColor="#58a6ff" />
        }
        ListEmptyComponent={
          <View style={styles.center}>
            <Ionicons name="pulse-outline" size={48} color="#484f58" />
            <Text style={styles.emptyText}>暂无交易信号</Text>
            <Text style={styles.emptyHint}>点击下方按钮执行策略评估</Text>
          </View>
        }
      />
      <TouchableOpacity style={styles.evaluateBtn} onPress={onEvaluate} disabled={evaluating}>
        {evaluating ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <>
            <Ionicons name="flash" size={20} color="#fff" />
            <Text style={styles.evaluateText}>执行策略评估</Text>
          </>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0d1117" },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#0d1117" },
  emptyText: { color: "#8b949e", marginTop: 12, fontSize: 16 },
  emptyHint: { color: "#484f58", marginTop: 4, fontSize: 13 },
  list: { padding: 12, paddingBottom: 80 },
  card: {
    backgroundColor: "#161b22", borderRadius: 10, padding: 14,
    marginBottom: 10, borderWidth: 1, borderColor: "#30363d",
  },
  cardHeader: { flexDirection: "row", alignItems: "center" },
  headerText: { flex: 1, marginLeft: 10 },
  fundName: { color: "#e6edf3", fontSize: 16, fontWeight: "600" },
  fundCode: { color: "#8b949e", fontSize: 12 },
  actionBadge: {
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, borderWidth: 1,
  },
  actionText: { fontSize: 13, fontWeight: "700" },
  divider: { height: 1, backgroundColor: "#21262d", marginVertical: 10 },
  reason: { color: "#c9d1d9", fontSize: 14, lineHeight: 20, marginBottom: 8 },
  row: { flexDirection: "row", marginTop: 2 },
  label: { color: "#8b949e", fontSize: 12 },
  value: { color: "#e6edf3", fontSize: 12, fontWeight: "500" },
  time: { color: "#484f58", fontSize: 11, marginTop: 6, textAlign: "right" },
  evaluateBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    marginHorizontal: 16, marginBottom: 16,
    backgroundColor: "#238636", paddingVertical: 14, borderRadius: 10,
    elevation: 4, shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 4,
  },
  evaluateText: { color: "#fff", fontSize: 16, fontWeight: "600", marginLeft: 8 },
});
