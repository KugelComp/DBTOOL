"""
create_test_db.py
=================
Creates a test database called `db_tool_test` on localhost with all the tables
that are referenced by obscure.sql and service_off.sql, populated with
realistic fake data.

Run once:
    python create_test_db.py

Then use 'db_tool_test' as the source database in DB Tool to test:
  - Obscure    : client names, emails, phone numbers get randomized
  - Service Off: external service config is wiped / reset to demo values
  - Tenant Change: export with a new tenant database name

Drop + recreate (if re-running):
    python create_test_db.py --reset
"""

import sys
import mysql.connector
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

DB_HOST = os.environ.get("DEFAULT_TARGET_HOST", "localhost")
DB_PORT = int(os.environ.get("DEFAULT_TARGET_PORT", 3306))
DB_USER = os.environ.get("DEFAULT_TARGET_USER", "root")
DB_PASS = os.environ.get("DEFAULT_TARGET_PASSWORD", "")
DB_NAME = "db_tool_test"

RESET = "--reset" in sys.argv

DDL = """
-- ─────────────────────────────────────────────────
--  CLIENT TABLES  (targeted by obscure.sql)
-- ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS m_client (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    firstname       VARCHAR(100),
    middlename      VARCHAR(100),
    lastname        VARCHAR(100),
    display_name    VARCHAR(255),
    mobile_no       VARCHAR(20),
    email_address   VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS m_appuser (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(100) NOT NULL,
    email       VARCHAR(255),
    mobile_no   VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS m_enquiry (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    fullname    VARCHAR(255),
    mobile_no   VARCHAR(20),
    email       VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS m_family_members (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    client_id       INT,
    firstname       VARCHAR(100),
    middlename      VARCHAR(100),
    lastname        VARCHAR(100),
    mobile_number   VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS m_client_identifier (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    client_id       INT,
    document_type   VARCHAR(50),
    document_key    VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS m_enquiry_identifier (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    enquiry_id      INT,
    document_type   VARCHAR(50),
    document_key    VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS m_kyc_entity (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    entity_id       INT,
    document_type   VARCHAR(50),
    document_key    VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS g_sales_officer (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    firstname       VARCHAR(100),
    lastname        VARCHAR(100),
    display_name    VARCHAR(255),
    mobile_no       VARCHAR(20),
    email           VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS m_address (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    client_id       INT,
    owner_number    VARCHAR(20),
    address_line_1  VARCHAR(255),
    address_line_2  VARCHAR(255),
    city            VARCHAR(100),
    state           VARCHAR(100),
    pincode         VARCHAR(10)
);

-- ─────────────────────────────────────────────────
--  SERVICE / CONFIG TABLES  (targeted by service_off.sql + obscure.sql)
-- ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS c_configuration (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    enabled     TINYINT(1) DEFAULT 1,
    value       VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS c_external_service_properties (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    value       VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS external_services_config (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    service     VARCHAR(100),
    config_key  VARCHAR(100),
    config_val  TEXT
);

CREATE TABLE IF NOT EXISTS communication_sms_job_mapping (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    job_name    VARCHAR(100),
    is_active   TINYINT(1) DEFAULT 1
);

CREATE TABLE IF NOT EXISTS communication_sms_event_mapping (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    event_name  VARCHAR(100),
    template    VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS communication_channel (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100),
    type        VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS communication_configuration (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    channel_id  INT,
    activate    TINYINT(1) DEFAULT 1,
    config_data TEXT
);

-- ─────────────────────────────────────────────────
--  HOOK / PAYMENT / MISC TABLES  (truncated by obscure.sql)
-- ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS m_hook_configuration (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100),
    url         VARCHAR(500),
    is_active   TINYINT(1) DEFAULT 1
);

CREATE TABLE IF NOT EXISTS m_hook_schema (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    hook_id     INT,
    field_name  VARCHAR(100),
    field_type  VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS m_organisation_details (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(255),
    short_name  VARCHAR(50),
    address     TEXT,
    phone       VARCHAR(20),
    email       VARCHAR(255),
    website     VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS m_e_nach_external_service (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    provider    VARCHAR(100),
    config      TEXT,
    is_active   TINYINT(1) DEFAULT 1
);

CREATE TABLE IF NOT EXISTS m_payment_gateway_vendors (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    vendor_name VARCHAR(100),
    config      TEXT,
    is_active   TINYINT(1) DEFAULT 1
);

CREATE TABLE IF NOT EXISTS job (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100),
    is_active   TINYINT(1) DEFAULT 1,
    cron_expr   VARCHAR(50)
);
"""

SEED = """
-- ─────────────────────────────────────────────────
--  SEED: Clients (real-looking PII — will be masked by obscure)
-- ─────────────────────────────────────────────────
INSERT INTO m_client (firstname, middlename, lastname, display_name, mobile_no, email_address) VALUES
('Ramesh',   'Kumar',  'Sharma',  'Ramesh Kumar Sharma',  '9876543210', 'ramesh.sharma@realmail.com'),
('Priya',    'Devi',   'Patel',   'Priya Devi Patel',     '9845012345', 'priya.patel@realmail.com'),
('Suresh',   'Singh',  'Yadav',   'Suresh Singh Yadav',   '9812345678', 'suresh.yadav@realmail.com'),
('Anjali',   'Raj',    'Gupta',   'Anjali Raj Gupta',     '9801234567', 'anjali.gupta@realmail.com'),
('Vikram',   'Patel',  'Joshi',   'Vikram Patel Joshi',   '9876012345', 'vikram.joshi@realmail.com');

INSERT INTO m_appuser (username, email, mobile_no) VALUES
('admin_user',   'admin@company.com',   '9900001111'),
('branch_mgr',   'branch@company.com',  '9900002222'),
('field_agent',  'field@company.com',   '9900003333');

INSERT INTO m_enquiry (fullname, mobile_no, email) VALUES
('Arun Kumar Mishra',  '9871234560', 'arun.mishra@personal.com'),
('Sunita Devi Roy',    '9861234560', 'sunita.roy@personal.com');

INSERT INTO m_family_members (client_id, firstname, middlename, lastname, mobile_number) VALUES
(1, 'Sita',  'Devi', 'Sharma', '9812340001'),
(2, 'Raj',   'Kumar', 'Patel', '9812340002');

INSERT INTO m_client_identifier (client_id, document_type, document_key) VALUES
(1, 'AADHAAR', 'ABCD1234EFGH'),
(2, 'PAN',     'BNJPS1234K'),
(3, 'VOTER',   'GHK1234567');

INSERT INTO m_enquiry_identifier (enquiry_id, document_type, document_key) VALUES
(1, 'AADHAAR', 'XYZW9876ABCD'),
(2, 'PAN',     'MNOPS9876Q');

INSERT INTO m_kyc_entity (entity_id, document_type, document_key) VALUES
(1, 'AADHAAR', 'QRST5678UVWX'),
(2, 'DL',      'MH01-2023-1234567');

INSERT INTO g_sales_officer (firstname, lastname, display_name, mobile_no, email) VALUES
('Kiran',   'Mehta',  'Kiran Mehta',    '9700011001', 'kiran.mehta@company.com'),
('Deepak',  'Verma',  'Deepak Verma',   '9700011002', 'deepak.verma@company.com');

INSERT INTO m_address (client_id, owner_number, address_line_1, address_line_2, city, state, pincode) VALUES
(1, '9876543210', '21 Chaura Rasta',    'M I Road',           'Jaipur',  'Rajasthan', '302001'),
(2, '9845012345', 'D-96 Bapu Nagar',    'Vaishali Nagar',     'Jaipur',  'Rajasthan', '302021'),
(3, '9812345678', 'Plot 18 UIT Road',   'Pratap Nagar',       'Jodhpur', 'Rajasthan', '342001');

-- ─────────────────────────────────────────────────
--  SEED: External Services / Config (will be wiped/reset by service_off + obscure)
-- ─────────────────────────────────────────────────
INSERT INTO c_configuration (name, enabled, value) VALUES
('amazon-S3',   1, 'enabled'),
('smtp-email',  1, 'enabled'),
('sms-gateway', 1, 'enabled'),
('push-notify', 1, 'enabled');

INSERT INTO c_external_service_properties (name, value) VALUES
('s3_access_key',        'AKIAIOSFODNN7REALKEY'),
('s3_secret_key',        'wJalrXUtnFEMI/K7MDENG/realSecretKey'),
('s3_bucket_name',       'my-production-bucket'),
('username',             'prod_service_user'),
('password',             'Super$ecretPr0dPass!'),
('states_url',           'https://prod-api.internal/states'),
('address_by_pincode_url', 'https://prod-api.internal/pincode');

INSERT INTO external_services_config (service, config_key, config_val) VALUES
('s3',    'endpoint',  'https://s3.amazonaws.com'),
('smtp',  'host',      'smtp.sendgrid.net'),
('smtp',  'api_key',   'SG.realApiKey123456'),
('sms',   'provider',  'Kaleyra'),
('sms',   'api_key',   'kaleyra_real_api_key_789');

INSERT INTO communication_configuration (channel_id, activate, config_data) VALUES
(1, 1, '{"host":"smtp.prod.com","port":587}'),
(2, 1, '{"apiKey":"kaleyra_prod_key"}');

INSERT INTO communication_channel (name, type) VALUES
('Email', 'SMTP'),
('SMS',   'API');

INSERT INTO communication_sms_job_mapping (job_name, is_active) VALUES
('loan_due_reminder', 1),
('emi_confirmation',  1);

INSERT INTO communication_sms_event_mapping (event_name, template) VALUES
('LOAN_DISBURSED', 'Dear {name}, your loan of {amount} is disbursed.'),
('EMI_DUE',        'Dear {name}, EMI of {amount} is due on {date}.');

INSERT INTO m_hook_configuration (name, url, is_active) VALUES
('payment-webhook',  'https://prod.internal/hooks/payment',  1),
('kyc-webhook',      'https://prod.internal/hooks/kyc',      1);

INSERT INTO m_hook_schema (hook_id, field_name, field_type) VALUES
(1, 'amount',     'decimal'),
(1, 'client_id',  'integer'),
(2, 'kyc_status', 'string');

INSERT INTO m_organisation_details (name, short_name, address, phone, email, website) VALUES
('Graviton Finance Pvt Ltd', 'GFPL', '5th Floor, Tower B, Cyber City', '0141-4001234', 'info@graviton.com', 'https://graviton.com');

INSERT INTO m_e_nach_external_service (provider, config, is_active) VALUES
('NACH_PRO', '{"merchant_id":"MP123","secret":"nach_real_secret"}', 1);

INSERT INTO m_payment_gateway_vendors (vendor_name, config, is_active) VALUES
('Razorpay', '{"key_id":"rzp_live_realkey","key_secret":"rzp_live_realsecret"}', 1),
('Paytm',    '{"merchant_key":"paytm_live_realkey","mid":"PY12345678"}',         1);

INSERT INTO job (name, is_active, cron_expr) VALUES
('enach presentation', 1, '0 9 * * *'),
('emi_reminder',       1, '0 8 * * *'),
('daily_report',       1, '0 7 * * *');
"""


def run(conn, sql_block, label=""):
    cursor = conn.cursor()
    # Strip comment-only lines before splitting on semicolons
    clean_lines = [
        line for line in sql_block.splitlines()
        if not line.strip().startswith('--')
    ]
    clean_sql = "\n".join(clean_lines)
    statements = [s.strip() for s in clean_sql.split(';') if s.strip()]
    ok = 0
    for stmt in statements:
        try:
            cursor.execute(stmt)
            conn.commit()
            ok += 1
        except mysql.connector.Error as e:
            print(f"  [WARN] {e}")
    cursor.close()
    print(f"  {label}: {ok}/{len(statements)} statements OK")


def main():
    print(f"\n{'='*55}")
    print(f"  DB Tool — Test Database Setup")
    print(f"  Target : {DB_USER}@{DB_HOST}:{DB_PORT}")
    print(f"  DB Name: {DB_NAME}")
    print(f"{'='*55}\n")

    try:
        conn = mysql.connector.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS)
    except mysql.connector.Error as e:
        print(f"[ERROR] Cannot connect to MySQL: {e}")
        print(f"  Check DEFAULT_TARGET_HOST / USER / PASSWORD in .env")
        sys.exit(1)

    cursor = conn.cursor()

    if RESET:
        print(f"[RESET] Dropping database '{DB_NAME}'...")
        cursor.execute(f"DROP DATABASE IF EXISTS `{DB_NAME}`")
        conn.commit()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.commit()
    cursor.close()
    conn.close()

    # Reconnect to the new DB
    conn = mysql.connector.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME)

    print("[1/2] Creating tables...")
    run(conn, DDL, "DDL")

    print("[2/2] Inserting seed data...")
    run(conn, SEED, "Seed")

    conn.close()

    print(f"\n{'='*55}")
    print(f"  [OK] Database '{DB_NAME}' ready!")
    print(f"  Use it in DB Tool to test:")
    print(f"    • Obscure     — client names / contact / addresses get masked")
    print(f"    • Service Off — S3 keys, SMS config, hooks get wiped")
    print(f"    • Tenant Change — export with a new DB name")
    print(f"\n  Re-run with --reset to drop and recreate from scratch.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
