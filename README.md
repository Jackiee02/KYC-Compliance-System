Overview
This Jupyter Notebook (KYC_project.ipynb) implements a prototype KYC (Know Your Customer) compliance system in Python. It automates the processing of customer data for financial institutions, focusing on data generation, cleaning, enrichment, sanctions screening, risk assessment, deduplication, and reporting. The system helps identify risks such as sanctions violations, high-risk jurisdictions, and overdue KYC reviews, ensuring compliance with regulations like anti-money laundering (AML) and counter-terrorism financing (CTF).
Key features:

Generates realistic test data using Faker.
Integrates external APIs (GLEIF for LEI enrichment) and resources (OFAC SDN list for sanctions screening).
Performs fuzzy matching for deduplication using MinHash and LSH.
Calculates risk scores and categorizes entities (low, medium, high, extreme risk).
Outputs reports in CSV, Excel, PDF, and JSON formats.

This is a testing-oriented prototype; in production, replace generated data with real datasets.
Dependencies

Python 3.12+ (tested in Google Colab).
Required libraries (install via pip if not in Colab):textpip install pandas requests faker tqdm datasketch reportlab openpyxl
Environment: Uses Google Drive for output storage (mount via drive.mount('/content/drive')).
No additional installations needed for core functionality, but ensure internet access for APIs.

Setup and Usage

Clone the Repository:textgit clone https://github.com/yourusername/kyc-compliance-system.git
cd kyc-compliance-system
Run in Jupyter/Colab:
Open KYC_project.ipynb in Jupyter Notebook or Google Colab.
Mount Google Drive if using Colab:Pythonfrom google.colab import drive
drive.mount('/content/drive')
Execute cells sequentially. The script will:
Generate ~15,670 test records.
Process data through 8 steps.
Output files to /content/drive/MyDrive/Colab Notebooks/KYC/ (configurable).


Configuration:
Edit the Config class for custom settings (e.g., TOTAL_RECORDS, risk weights, output paths).
For real data: Replace generate_realistic_dataset() with pd.read_csv('your_data.csv').

Execution Time:
GLEIF queries: ~4 hours (due to API delays).
OFAC screening: ~2.5 hours.
Total: 6-7 hours for full run on test data.


System Workflow
The pipeline consists of 8 steps:

Data Generation: Creates fake KYC records (company names, registration numbers, countries, etc.).
Cleaning & Standardization: Normalizes names, splits bilingual entries, calculates initial risk tiers.
LEI Enrichment: Queries GLEIF API to fetch/validate Legal Entity Identifiers (LEIs).
OFAC Screening: Checks against US Treasury's SDN list for sanctions hits using fuzzy matching.
Risk Assessment: Computes composite risk scores (0-100) based on factors like jurisdiction, sanctions, and KYC status.
Deduplication: Removes exact and fuzzy duplicates with dynamic weights (using MinHash LSH).
Reporting: Generates Excel (overview, high-risk, sanctions), PDF (English summary), and verification guide.
Validation: Lists output files and prints summary stats (e.g., LEI coverage, OFAC hits).

Output Files:

kyc_raw_data.csv: Generated raw data.
kyc_cleaned_data.csv: Cleaned dataset.
kyc_lei_enhanced_data.csv: With enriched LEIs.
kyc_deduplicated_data.csv: Deduplicated final data.
KYC合規報告_詳細版.xlsx: Detailed Excel report.
KYC_Compliance_Summary_Report.pdf: English PDF summary.
manual_review_notes.json: Duplicates for manual review.
test_environment_duplicates.csv: Test dedup logs.
verification_guide.txt: Validation checklist.
sdn.csv: Cached OFAC list (if downloaded).

Example Output Summary
After running:

Processed records: ~13,928 (after dedup).
LEI coverage: ~8.62% validated.
OFAC hits: ~0.625%.
KYC overdue: ~10.5%.

Limitations

Test data is synthetic; adapt for production.
API rate limits may cause delays/errors (handled with retries).
No machine learning models; risk scoring is rule-based.
Compliance: Ensure legal review for real-world use (e.g., GDPR compliance).

Contributing
Fork the repo, make changes, and submit a pull request. Issues and suggestions welcome!
License
MIT License. See LICENSE for details.
