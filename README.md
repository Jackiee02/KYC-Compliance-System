# KYC Compliance System (Hong Kong Edition) | KYC 合規系統（香港版）

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen)

## Overview | 概述

A comprehensive **KYC (Know Your Customer) compliance system** designed for Hong Kong financial institutions, automating the complete customer due diligence workflow from data generation to report output. This system simulates real-world compliance processes while incorporating advanced features like fuzzy matching, risk assessment, and duplicate detection.

專為香港金融機構設計的完整**KYC (Know Your Customer) 合規系統**，自動化客戶盡職調查流程，從資料生成到報告輸出的完整工作流程。系統模擬真實合規流程，並整合模糊匹配、風險評估和重複檢測等先進功能。

---

## Key Features | 主要功能

### 1. Data Generation Module | 資料生成模組
- Generate simulated customer data (configurable size, default: 15,000 records)
- Include real-world companies (HSBC, Standard Chartered, Tencent, etc.)
- Automatic injection of OFAC sanctions test cases
- Create 2-5% approximate duplicate records for deduplication testing
- 生成模擬客戶資料（可配置規模，默認：15,000筆記錄）
- 包含真實公司（匯豐、渣打、騰訊等）
- 自動注入OFAC制裁測試案例
- 創建2-5%近似重複記錄用於去重測試

### 2. Data Cleaning & Standardization | 資料清洗與標準化
- Automatic company name cleaning (special characters, suffix standardization)
- Chinese/English name splitting and normalization
- Registration number format standardization
- Risk tiering based on jurisdiction
- 自動公司名稱清洗（特殊字符、後綴標準化）
- 中英文名稱拆分與正規化
- 註冊號碼格式標準化
- 基於司法管轄區的風險分級

### 3. LEI Enhancement Service | LEI增強服務
- Integration with GLEIF Global Legal Entity Identifier API
- Automatic query and supplementation of missing LEIs
- ISO 17442 format validation
- Cache mechanism for improved query efficiency
- 整合GLEIF全球法人識別碼API
- 自動查詢並補充缺失的LEI
- ISO 17442格式驗證
- 緩存機制提升查詢效率

### 4. Sanctions List Screening | 制裁名單篩查
- Automatic download of OFAC SDN sanctions list
- Fuzzy matching algorithms (Jaro-Winkler + Token Sort)
- Similarity threshold and confidence calculation
- Chinese/English name conversion and matching
- 自動下載OFAC SDN制裁名單
- 模糊匹配算法（Jaro-Winkler + Token Sort）
- 相似度閾值與置信度計算
- 中英文名稱轉換與匹配

### 5. Intelligent Risk Assessment | 智能風險評估
- Multi-factor risk scoring system
- Risk classification: 🔴 Extreme High, 🟠 High, 🟡 Medium, 🟢 Low
- Customizable risk weight configuration
- 多因子風險評分系統
- 風險等級分類：🔴極高風險、🟠高風險、🟡中風險、🟢低風險
- 可自定義風險權重配置

### 6. Advanced Deduplication System | 先進去重系統
- MinHash LSH for approximate duplicate detection
- Dynamic weight adjustment (based on risk profile)
- High-risk record retention strategy
- Test duplicate list output
- MinHash LSH近似重複檢測
- 動態權重調整（基於風險狀況）
- 高風險記錄保留策略
- 測試重複清單輸出

### 7. Multi-format Report Generation | 多格式報告生成
- **Excel Detailed Report**: Customer risk overview, high-risk lists, sanctions hits
- **PDF Management Summary**: English paragraph format for executive review
- **Verification Guide**: System checklist
- **Manual Review Notes**: JSON format review recommendations
- **Excel詳細報告**：客戶風險概覽、高風險清單、制裁命中
- **PDF管理摘要**：英文段落格式，適合管理層審閱
- **驗證指南**：系統檢查清單
- **手動審查筆記**：JSON格式審查建議

---

## Installation Guide | 安裝指南

### Running in Google Colab | 在Google Colab中運行

The simplest way is to open and run `kyc_project.py` directly in Google Colab:

最簡單的方式是直接在Google Colab中打開並執行`kyc_project.py`：

```bash
# Execute in Colab cell | 在Colab單元格中執行
!git clone https://github.com/yourusername/kyc-compliance-system.git
%cd kyc-compliance-system
!python kyc_project.py
