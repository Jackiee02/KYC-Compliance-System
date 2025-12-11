# KYC 合規系統 (香港版) - KYC Compliance System (Hong Kong Edition)

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen)

## 專案概述 | Project Overview

這是一個完整的 **KYC (Know Your Customer) 合規系統**，專為香港金融機構設計，用於自動化客戶盡職調查流程。系統模擬了從資料生成、清洗、合規檢查到報告輸出的全流程，滿足監管合規要求。

This is a comprehensive **KYC (Know Your Customer) Compliance System** designed for Hong Kong financial institutions, automating the customer due diligence process. The system simulates the complete workflow from data generation, cleaning, compliance checks to report generation, meeting regulatory compliance requirements.

---

## 主要功能 | Key Features

### 1. **資料生成模組 | Data Generation Module**
- 生成模擬的客戶資料（可設定規模，預設15,000筆）
- 包含真實知名公司（匯豐、渣打、騰訊等）
- 自動注入OFAC制裁名單測試案例
- 製造2-5%近似重複記錄用於去重測試

### 2. **資料清洗與標準化 | Data Cleaning and Standardization**
- 自動清理公司名稱（特殊字元、標準化後綴）
- 中英文名稱拆分與正規化
- 註冊號碼格式標準化
- 基於司法管轄區的風險分級

### 3. **LEI 增強服務 | LEI Enhancement Service**
- 整合 GLEIF 全球法人識別碼 API
- 自動查詢並補充缺失的 LEI
- ISO 17442 標準格式驗證
- 快取機制提升查詢效率

### 4. **制裁名單篩查 | Sanctions List Screening**
- 自動下載 OFAC SDN 制裁名單
- 模糊比對演算法（Jaro-Winkler + Token Sort）
- 相似度門檻與置信度計算
- 中英文名稱轉換比對

### 5. **智能風險評估 | Intelligent Risk Assessment**
- 多因子風險評分系統
- 風險等級分類：🔴極高、🟠高、🟡中、🟢低
- 自定義風險權重配置

### 6. **先進去重系統 | Advanced Deduplication System**
- MinHash LSH 近似重複檢測
- 動態權重調整（基於風險狀況）
- 保留高風險記錄策略
- 輸出測試去重清單

### 7. **多格式報告輸出 | Multi-format Report Generation**
- **Excel 詳細報告**：客戶風險概覽、高風險清單、制裁命中
- **PDF 管理摘要**：純英文段落格式，適合管理層審閱
- **驗證指南**：系統檢查清單
- **手動審查筆記**：JSON格式的審查建議

---

## 安裝指南 | Installation Guide

### 在 Google Colab 中運行 | Running in Google Colab

打開並執行 `kyc_projecty`：

```bash
# 在 Jupyter notebook 單元格中執行
!python kyc_project.py
