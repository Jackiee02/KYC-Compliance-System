# KYC Compliance Platform 路线图

更新日期：2026-08-09

## 当前版本：0.3 中文业务工作台（已完成）

- `src` 模块化包，Notebook 不再承担生产逻辑。
- FastAPI、CLI、SQLite/PostgreSQL、SQLAlchemy 和 Alembic。
- 中英文名称、注册号和 ISO 17442 LEI 标准化/验证。
- OFAC/GLEIF 连接器、离线 fixture、制裁数据版本与原始快照机制。
- 多算法制裁匹配、版本化风险策略、解释因子与建议复核日期。
- 保留源记录的实体解析，不再自动删除“重复”客户。
- CSV/JSONL/Excel/PDF 报告与 SHA-256 运行 manifest。
- 审计事件、Docker Compose、CI、结构化日志和分层测试。
- 响应式中文工作台：总览、客户台账、案件复核和批次报告。
- 客户登记后自动筛查与风险评分，候选命中持久化为复核案件。
- 人工决定支持排除误报、确认命中和升级调查，并记录操作者与备注。
- 报告历史和 Excel、PDF、CSV、JSONL 证据包下载。
- 合成黄金评估集、筛查 Precision/Recall/F1、实体 Recall@K、风险分类和去重指标。
- 阈值扫描、逐条预测、错误案例CSV和评估数据集SHA-256指纹。

该版本是可扩展的平台基础，不等于生产合规系统。当前 API 的 `X-Actor-ID` 只是审计占位符，
离线制裁名单只是测试 fixture，风险策略只是演示配置。

## 0.4：客户关系、身份权限与完整案件工作流

- Party 模型：自然人、法人、信托、董事、授权人、股东、UBO、亲属及密切关系人。
- 所有权/控制关系图谱，支持多层穿透和历史有效期。
- CDD/EDD 清单：身份、地址、业务目的、资金/财富来源、文件、有效期和补件。
- Screening Case：分派、评论、证据、SLA、四眼覆核、决定理由、重开和申诉。
- OIDC 登录、RBAC、机构/租户隔离及敏感字段遮罩。

验收重点：每个客户决定都能追溯至资料、来源、规则版本、操作人和覆核人。

## 0.5：持续监控与数据源治理

- 持久化任务队列，将批量重筛和报告从同步 API 迁移到 worker。
- 名单全量/增量更新、失败告警、版本回放和自动触发客户重筛。
- PEP/RCA、香港/联合国及机构适用的其他合法授权来源。
- 客户资料变更、公司状态、LEI 关系数据与事件驱动重审。
- 交易监控、警报聚合和 STR 协作；系统不得自动作出 STR 决定。

验收重点：来源失败显式可见；旧名单可回放；所有受影响客户的重筛有完成率和延迟 SLO。

## 0.6：匹配质量、模型治理与规模

- 建立经过标注的多语言 sanctions/entity-resolution golden dataset。
- 分离候选召回与精排，加入别名、地址、日期、证件、国籍和实体类型特征。
- 按名单、语言和实体类型报告 precision、recall、警报量及人工处理时间。
- 阈值审批、champion/challenger、漂移监控、回溯测试、模型卡与变更记录。
- OpenTelemetry、集中式日志指标、容量测试、备份恢复与运行 SLO。

AI/LLM 仅用于证据摘要、调查辅助和规则建议；输出必须引用来源并保留人工责任。

## 建议生产门槛

- 100% 决策带输入快照、数据源版本、风险策略/模型版本和审计主体。
- 制裁漏报作为一级指标，不能只报告 accuracy。
- 重复客户只能建议 merge；必须支持人工确认和 unmerge。
- 外部来源超时、解析异常或数据为空时显式失败，禁止转换成“无命中”。
- 敏感字段传输/静态加密，查看、下载、导出和决定修改全部审计。
- 真实数据上线前完成威胁建模、私隐影响评估、渗透测试、恢复演练和合规验收。

## 官方基准

- [HKMA AML-2：认可机构 AML/CFT 指引](https://brdr.hkma.gov.hk/eng/doc-ldg/current/20230525-4-EN)
- [HKMA：有效执行风险为本的客户尽职审查](https://brdr.hkma.gov.hk/eng/doc-ldg/docId/20240208-3-EN)
- [HKMA：2026 年金融犯罪 AI 应用](https://brdr.hkma.gov.hk/eng/doc-ldg/docId/20260622-1-EN)
- [HKMA：2026 年制裁筛查系统专题检视](https://brdr.hkma.gov.hk/eng/doc-ldg/docId/20260316-1-EN)
- [FATF Recommendations（2025-02）](https://www.fatf-gafi.org/content/dam/fatf-gafi/recommendations/Feburary%202025%20FATF%20Recommendations.pdf)
- [香港私隐专员：身份识别符实务守则](https://www.pcpd.org.hk/english/data_privacy_law/code_of_practices/code_id_32.html)
- [GLEIF API](https://www.gleif.org/en/lei-data/gleif-api/)
- [OFAC Sanctions List Service](https://ofac.treasury.gov/sanctions-list-service)
