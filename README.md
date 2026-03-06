# clinical-data-migration-pipeline

A Python-powered ETL (Extract, Transform, Load) framework designed for migrating complex clinical datasets from PostgreSQL to SQL Server.

## 🛠 Key Capabilities
* **Schema Transformation:** Automated conversion of PostgreSQL schema definitions to T-SQL.
* **Logic Migration:** Regex-based transformation of database views and function syntax.
* **Integrity Validation:** Automated row-count auditing to ensure 100% data fidelity during migration.
* **Performance Optimization:** Index migration and batch processing for high-volume clinical records.

## 🔒 Security & Compliance
* Credential isolation via environment variables (`python-dotenv`).
* Designed with HIPAA-compliant data handling workflows in mind.

## 📂 Repository Structure
This repository is curated to showcase the core engineering logic of the migration suite. 

* **copy_data.py**: The primary migration engine (PostgreSQL ➡️ SQL Server).
* **migrate_indexes.py**: Automated translation of B-Tree/Hash indexes.
* **compare_table_rowcounts.py**: A data-fidelity audit tool for post-migration QA.
* **dbconfig.py**: Centralized, secure credential management.
* **final_schema_corrected.sql**: A sample of the high-complexity clinical target schema.

*Note: Auxiliary files (local logs, specific patient-data mapping tables, and the .env file) are excluded to maintain security and project clarity.*
