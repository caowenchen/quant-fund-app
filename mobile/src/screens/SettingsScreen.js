import React, { useState, useEffect } from "react";
import {
  View, Text, StyleSheet, TextInput, TouchableOpacity,
  ScrollView, Alert, Switch, ActivityIndicator,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Ionicons } from "@expo/vector-icons";
import { addHolding, getStrategyConfig, healthCheck } from "../services/api";

const STORAGE_KEYS = {
  SERVER_URL: "server_url",
  ALIPAY_ACCOUNT: "alipay_account",
  ALIPAY_PASSWORD: "alipay_password",
  QQ_EMAIL: "qq_email",
  QQ_AUTH_CODE: "qq_auth_code",
};

export default function SettingsScreen() {
  const [serverUrl, setServerUrl] = useState("http://192.168.1.100:5000");
  const [connected, setConnected] = useState(false);
  const [checking, setChecking] = useState(false);

  const [strategy, setStrategy] = useState(null);

  const [newFund, setNewFund] = useState({
    fund_code: "", fund_name: "", shares: "", cost_amount: "", avg_cost: "",
  });
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    loadSettings();
    checkHealth();
  }, []);

  const loadSettings = async () => {
    try {
      const url = await AsyncStorage.getItem(STORAGE_KEYS.SERVER_URL);
      if (url) setServerUrl(url);
    } catch (e) {}
  };

  const saveSetting = async (key, value) => {
    try {
      await AsyncStorage.setItem(key, value);
      if (key === STORAGE_KEYS.SERVER_URL) {
        const { setBaseUrl } = require("../services/api");
        setBaseUrl(value);
      }
    } catch (e) {}
  };

  const checkHealth = async () => {
    setChecking(true);
    try {
      const res = await healthCheck();
      if (res.status === "ok") setConnected(true);
    } catch (e) {
      setConnected(false);
    } finally {
      setChecking(false);
    }
  };

  const loadStrategy = async () => {
    try {
      const res = await getStrategyConfig();
      if (res.code === 0) setStrategy(res.data);
    } catch (e) {}
  };

  const handleAddFund = async () => {
    if (!newFund.fund_code || !newFund.fund_name) {
      Alert.alert("提示", "请输入基金代码和名称");
      return;
    }
    const shares = parseFloat(newFund.shares);
    const cost = parseFloat(newFund.cost_amount);
    if (isNaN(shares) || shares <= 0 || isNaN(cost) || cost <= 0) {
      Alert.alert("提示", "请输入有效的份额和本金");
      return;
    }
    const avgCost = newFund.avg_cost ? parseFloat(newFund.avg_cost) : (cost / shares);

    setAdding(true);
    try {
      const res = await addHolding({
        fund_code: newFund.fund_code,
        fund_name: newFund.fund_name,
        shares,
        cost_amount: cost,
        avg_cost: avgCost,
      });
      if (res.code === 0) {
        Alert.alert("成功", "基金添加成功");
        setNewFund({ fund_code: "", fund_name: "", shares: "", cost_amount: "", avg_cost: "" });
      } else {
        Alert.alert("失败", res.msg);
      }
    } catch (e) {
      Alert.alert("错误", "添加失败, 请检查服务器连接");
    } finally {
      setAdding(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* 服务器连接 */}
      <Text style={styles.sectionTitle}>服务器配置</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.label}>服务器地址</Text>
          <View style={[styles.status, { backgroundColor: connected ? "#3fb95033" : "#f8514933" }]}>
            <View style={[styles.dot, { backgroundColor: connected ? "#3fb950" : "#f85149" }]} />
            <Text style={[styles.statusText, { color: connected ? "#3fb950" : "#f85149" }]}>
              {connected ? "已连接" : "未连接"}
            </Text>
          </View>
        </View>
        <TextInput
          style={styles.input}
          value={serverUrl}
          onChangeText={(v) => { setServerUrl(v); saveSetting(STORAGE_KEYS.SERVER_URL, v); }}
          placeholder="http://192.168.1.100:5000"
          placeholderTextColor="#484f58"
          autoCapitalize="none"
        />
        <TouchableOpacity style={styles.btn} onPress={checkHealth} disabled={checking}>
          {checking ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.btnText}>测试连接</Text>}
        </TouchableOpacity>
      </View>

      {/* 策略参数 */}
      <Text style={styles.sectionTitle}>策略参数</Text>
      <View style={styles.card}>
        <TouchableOpacity style={styles.btn} onPress={loadStrategy}>
          <Text style={styles.btnText}>加载策略配置</Text>
        </TouchableOpacity>
        {strategy && (
          <View style={{ marginTop: 12 }}>
            <InfoRow label="亏损观察线" value={`${(strategy.stop_add_loss_rate * 100).toFixed(1)}%`} />
            <InfoRow label="止损线" value={`${(strategy.stop_loss_rate * 100).toFixed(1)}%`} color="#f85149" />
            <InfoRow label="移动止盈触发" value={`${(strategy.trailing_stop_trigger * 100).toFixed(0)}%`} color="#3fb950" />
            <InfoRow label="回撤卖一半" value={`${(strategy.trailing_drawdown_half * 100).toFixed(0)}%`} color="#f0883e" />
            <InfoRow label="回撤卖完" value={`${(strategy.trailing_drawdown_all * 100).toFixed(0)}%`} color="#f85149" />
          </View>
        )}
      </View>

      {/* 手动添加基金 */}
      <Text style={styles.sectionTitle}>手动添加基金</Text>
      <View style={styles.card}>
        <TextInput
          style={styles.input} placeholder="基金代码 (6位)" placeholderTextColor="#484f58"
          value={newFund.fund_code} onChangeText={(v) => setNewFund({ ...newFund, fund_code: v })}
          keyboardType="numeric" maxLength={6}
        />
        <TextInput
          style={styles.input} placeholder="基金名称" placeholderTextColor="#484f58"
          value={newFund.fund_name} onChangeText={(v) => setNewFund({ ...newFund, fund_name: v })}
        />
        <TextInput
          style={styles.input} placeholder="持有份额" placeholderTextColor="#484f58"
          value={newFund.shares} onChangeText={(v) => setNewFund({ ...newFund, shares: v })}
          keyboardType="decimal-pad"
        />
        <TextInput
          style={styles.input} placeholder="投入本金 (元)" placeholderTextColor="#484f58"
          value={newFund.cost_amount} onChangeText={(v) => setNewFund({ ...newFund, cost_amount: v })}
          keyboardType="decimal-pad"
        />
        <TextInput
          style={styles.input} placeholder="成本净值 (可选, 自动计算)" placeholderTextColor="#484f58"
          value={newFund.avg_cost} onChangeText={(v) => setNewFund({ ...newFund, avg_cost: v })}
          keyboardType="decimal-pad"
        />
        <TouchableOpacity
          style={[styles.btn, styles.addBtn]} onPress={handleAddFund} disabled={adding}
        >
          {adding ? (
            <ActivityIndicator color="#fff" size="small" />
          ) : (
            <>
              <Ionicons name="add-circle-outline" size={20} color="#fff" />
              <Text style={styles.btnText}> 添加持仓</Text>
            </>
          )}
        </TouchableOpacity>
      </View>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

function InfoRow({ label, value, color = "#e6edf3" }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={[styles.infoValue, { color }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0d1117" },
  content: { padding: 16 },
  sectionTitle: {
    color: "#58a6ff", fontSize: 14, fontWeight: "700",
    marginTop: 20, marginBottom: 8, textTransform: "uppercase",
  },
  card: {
    backgroundColor: "#161b22", borderRadius: 10, padding: 14,
    marginBottom: 8, borderWidth: 1, borderColor: "#30363d",
  },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  label: { color: "#e6edf3", fontSize: 14 },
  status: { flexDirection: "row", alignItems: "center", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12 },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 4 },
  statusText: { fontSize: 12, fontWeight: "600" },
  input: {
    backgroundColor: "#0d1117", color: "#e6edf3", fontSize: 14,
    borderWidth: 1, borderColor: "#30363d", borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10, marginBottom: 8,
  },
  btn: {
    backgroundColor: "#21262d", paddingVertical: 10, borderRadius: 8,
    alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: "#30363d",
  },
  addBtn: {
    backgroundColor: "#238636", borderColor: "#2ea043", flexDirection: "row",
  },
  btnText: { color: "#e6edf3", fontSize: 14, fontWeight: "600" },
  infoRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 },
  infoLabel: { color: "#8b949e", fontSize: 13 },
  infoValue: { fontSize: 13, fontWeight: "600" },
});
