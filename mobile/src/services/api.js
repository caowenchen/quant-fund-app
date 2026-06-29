import axios from "axios";

const BASE_URL = "http://192.168.1.100:5000";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

export function setBaseUrl(url) {
  api.defaults.baseURL = url;
}

export async function getHoldings() {
  const res = await api.get("/api/holdings");
  return res.data;
}

export async function addHolding(data) {
  const res = await api.post("/api/holdings", data);
  return res.data;
}

export async function updateHolding(fundCode, data) {
  const res = await api.put(`/api/holdings/${fundCode}`, data);
  return res.data;
}

export async function deleteHolding(fundCode) {
  const res = await api.delete(`/api/holdings/${fundCode}`);
  return res.data;
}

export async function refreshHoldings() {
  const res = await api.post("/api/holdings/refresh");
  return res.data;
}

export async function evaluateStrategy() {
  const res = await api.post("/api/evaluate");
  return res.data;
}

export async function getDecisions(limit = 50) {
  const res = await api.get("/api/decisions", { params: { limit } });
  return res.data;
}

export async function getSectorData(fundCode) {
  const res = await api.get(`/api/sector/${fundCode}`);
  return res.data;
}

export async function checkTradingDay() {
  const res = await api.get("/api/market/trading_day");
  return res.data;
}

export async function getStrategyConfig() {
  const res = await api.get("/api/config/strategy");
  return res.data;
}

export async function healthCheck() {
  const res = await api.get("/api/health");
  return res.data;
}
