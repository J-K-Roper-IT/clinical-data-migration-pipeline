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

* ## 📂 Project Scope & Structure
This repository contains the core logic and architectural components of the migration suite. 

*Note: To maintain a clean and focused presentation, auxiliary files such as local logs, temporary build artifacts, and sensitive configuration files (.env) have been excluded. The included files represent the primary engine and transformation logic.*

final_schema_corrected.sql: Included to demonstrate the complexity of the target schema, including Audit triggers, HSTORE extensions, and cross-schema foreign key constraints.
