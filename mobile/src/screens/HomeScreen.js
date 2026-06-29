import React, { useState, useCallback } from "react";
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { getHoldings, refreshHoldings } from "../services/api";

const STATUS_MAP = {
  holding: { label: "持有", color: "#3fb950" },
  observing: { label: "观察", color: "#d29922" },
  stop_loss: { label: "止损", color: "#f85149" },
  sold_half: { label: "卖半仓", color: "#f0883e" },
  sold_all: { label: "已清仓", color: "#8b949e" },
};

export default function HomeScreen() {
  const [holdings, setHoldings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const totalMarketValue = holdings.reduce((s, h) => s + (h.market_value || 0), 0);
  const totalProfit = holdings.reduce((s, h) => s + (h.total_profit || 0), 0);
  const totalCost = holdings.reduce((s, h) => s + (h.cost_amount || 0), 0);
  const totalRate = totalCost > 0 ? totalProfit / totalCost : 0;

  const fetchData = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const res = await getHoldings();
      if (res.code === 0) setHoldings(res.data || []);
    } catch (e) {
      Alert.alert("错误", "无法连接服务器");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchData();
    }, [])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshHoldings();
      await fetchData(false);
    } catch (e) {
      setRefreshing(false);
    }
  };

  const renderItem = ({ item }) => {
    const status = STATUS_MAP[item.status] || STATUS_MAP.holding;
    const profitColor = (item.total_profit || 0) >= 0 ? "#3fb950" : "#f85149";

    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.fundName}>{item.fund_name}</Text>
          <View style={[styles.statusBadge, { backgroundColor: status.color + "22", borderColor: status.color }]}>
            <Text style={[styles.statusText, { color: status.color }]}>{status.label}</Text>
          </View>
        </View>
        <Text style={styles.fundCode}>{item.fund_code}</Text>
        <View style={styles.divider} />
        <View style={styles.row}>
          <View style={styles.col}>
            <Text style={styles.label}>市值</Text>
            <Text style={styles.value}>¥{((item.market_value || 0)).toFixed(2)}</Text>
          </View>
          <View style={styles.col}>
            <Text style={styles.label}>持仓盈亏</Text>
            <Text style={[styles.value, { color: profitColor }]}>
              {((item.total_profit || 0) >= 0 ? "+" : "")}{((item.total_profit || 0)).toFixed(2)}
            </Text>
          </View>
          <View style={styles.col}>
            <Text style={styles.label}>收益率</Text>
            <Text style={[styles.value, { color: profitColor }]}>
              {((item.total_profit_rate || 0) * 100).toFixed(2)}%
            </Text>
          </View>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>净值: {((item.current_nav || 0)).toFixed(4)}</Text>
          <Text style={styles.label}>成本: {((item.avg_cost || 0)).toFixed(4)}</Text>
          {item.sector_name ? (
            <Text style={[styles.label, { color: (item.sector_change_pct || 0) >= 0 ? "#f85149" : "#3fb950" }]}>
              {item.sector_name} {(item.sector_change_pct || 0) >= 0 ? "+" : ""}{(item.sector_change_pct || 0).toFixed(2)}%
            </Text>
          ) : null}
        </View>
      </View>
    );
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#58a6ff" />
        <Text style={styles.loadingText}>加载中...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.summary}>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryLabel}>总市值</Text>
          <Text style={styles.summaryValue}>¥{totalMarketValue.toFixed(2)}</Text>
        </View>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryLabel}>总盈亏</Text>
          <Text style={[styles.summaryValue, { color: totalProfit >= 0 ? "#3fb950" : "#f85149" }]}>
            {totalProfit >= 0 ? "+" : ""}{totalProfit.toFixed(2)}
          </Text>
        </View>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryLabel}>总收益率</Text>
          <Text style={[styles.summaryValue, { color: totalRate >= 0 ? "#3fb950" : "#f85149" }]}>
            {(totalRate * 100).toFixed(2)}%
          </Text>
        </View>
      </View>
      <FlatList
        data={holdings}
        keyExtractor={(item) => item.fund_code}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#58a6ff" />
        }
        ListEmptyComponent={
          <View style={styles.center}>
            <Ionicons name="wallet-outline" size={48} color="#484f58" />
            <Text style={styles.emptyText}>暂无持仓数据</Text>
            <Text style={styles.emptyHint}>请在设置中配置支付宝后刷新</Text>
          </View>
        }
      />
      <TouchableOpacity style={styles.fab} onPress={onRefresh}>
        <Ionicons name="refresh" size={24} color="#fff" />
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0d1117" },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#0d1117" },
  loadingText: { color: "#8b949e", marginTop: 12, fontSize: 14 },
  emptyText: { color: "#8b949e", marginTop: 12, fontSize: 16 },
  emptyHint: { color: "#484f58", marginTop: 4, fontSize: 13 },
  summary: {
    flexDirection: "row", padding: 16, backgroundColor: "#161b22",
    borderBottomWidth: 1, borderBottomColor: "#30363d",
  },
  summaryItem: { flex: 1, alignItems: "center" },
  summaryLabel: { color: "#8b949e", fontSize: 12 },
  summaryValue: { color: "#e6edf3", fontSize: 18, fontWeight: "bold", marginTop: 4 },
  list: { padding: 12 },
  card: {
    backgroundColor: "#161b22", borderRadius: 10, padding: 14,
    marginBottom: 10, borderWidth: 1, borderColor: "#30363d",
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  fundName: { color: "#e6edf3", fontSize: 16, fontWeight: "600", flex: 1 },
  fundCode: { color: "#8b949e", fontSize: 12, marginTop: 2 },
  statusBadge: {
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12, borderWidth: 1,
  },
  statusText: { fontSize: 11, fontWeight: "600" },
  divider: { height: 1, backgroundColor: "#21262d", marginVertical: 10 },
  row: { flexDirection: "row", justifyContent: "space-between", marginTop: 4 },
  col: { alignItems: "flex-start" },
  label: { color: "#8b949e", fontSize: 11 },
  value: { color: "#e6edf3", fontSize: 15, fontWeight: "500", marginTop: 2 },
  fab: {
    position: "absolute", right: 20, bottom: 20,
    width: 50, height: 50, borderRadius: 25,
    backgroundColor: "#238636", justifyContent: "center", alignItems: "center",
    elevation: 6, shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3, shadowRadius: 4,
  },
});
