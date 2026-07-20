-- Ceche Web Platform — Database Schema
-- MySQL 8+

CREATE DATABASE IF NOT EXISTS ceche CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ceche;

-- All domains ever appraised through any interface (web, CLI, API, TUI)
CREATE TABLE IF NOT EXISTS appraisals (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    domain      VARCHAR(255) NOT NULL,
    value       DECIMAL(12,2),
    confidence  VARCHAR(20),
    range_low   DECIMAL(12,2),
    range_high  DECIMAL(12,2),
    tld_score   DECIMAL(5,2),
    weight_profile VARCHAR(20),
    modules_json JSON,
    source      VARCHAR(20) COMMENT 'api, web, cli, tui',
    ip_address  VARCHAR(45),
    api_key_id  INT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_domain (domain),
    INDEX idx_created (created_at),
    INDEX idx_source (source)
) ENGINE=InnoDB;

-- Blog posts (editable from admin panel)
CREATE TABLE IF NOT EXISTS blog_posts (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    slug        VARCHAR(255) UNIQUE NOT NULL,
    content     LONGTEXT NOT NULL COMMENT 'Markdown content',
    excerpt     TEXT,
    featured_image VARCHAR(500),
    author_id   INT,
    status      ENUM('draft','published') DEFAULT 'draft',
    published_at TIMESTAMP NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_published (published_at),
    INDEX idx_slug (slug)
) ENGINE=InnoDB;

-- Documentation pages (editable from admin panel)
CREATE TABLE IF NOT EXISTS documentation_pages (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    slug        VARCHAR(255) UNIQUE NOT NULL COMMENT 'e.g. api/endpoints, cli/installation',
    content     LONGTEXT NOT NULL COMMENT 'Markdown content',
    category    VARCHAR(100) COMMENT 'getting-started, api, cli, tui, guides',
    sort_order  INT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_sort (sort_order)
) ENGINE=InnoDB;

-- System settings (key-value, editable from admin)
CREATE TABLE IF NOT EXISTS settings (
    key_name    VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    description VARCHAR(500),
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- API keys for external access
CREATE TABLE IF NOT EXISTS api_keys (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    key_hash    VARCHAR(255) NOT NULL,
    tier        ENUM('free','pro','enterprise') DEFAULT 'free',
    rate_limit  INT DEFAULT 60 COMMENT 'Requests per minute',
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used   TIMESTAMP NULL,
    INDEX idx_active (active)
) ENGINE=InnoDB;

-- Admin user accounts
CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name        VARCHAR(100),
    role        ENUM('admin','editor') DEFAULT 'editor',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email)
) ENGINE=InnoDB;

-- Rate limit tracking
CREATE TABLE IF NOT EXISTS rate_limit_logs (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    identifier  VARCHAR(255) NOT NULL COMMENT 'IP address or API key ID',
    tier        VARCHAR(20),
    endpoint    VARCHAR(100),
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_identifier (identifier, timestamp),
    INDEX idx_time (timestamp)
) ENGINE=InnoDB;

-- Default settings (admin user created on first login via CECHE_ADMIN_PASSWORD env var)
INSERT IGNORE INTO settings (key_name, value, description) VALUES
('site_name', 'Ceche', 'Public site name'),
('meta_description', 'Domain Appraisal Engine — evaluate any domain across 16 dimensions', 'Default meta description'),
('maintenance_mode', 'false', 'Enable maintenance mode for the public site'),
('rate_limit_default', '60', 'Default API rate limit (requests per minute)'),
('pricing_cli', 'Free', 'CLI pricing tier label'),
('pricing_api', '$49/mo', 'API pricing tier label'),
('pricing_enterprise', 'Custom', 'Enterprise pricing tier label')
ON DUPLICATE KEY UPDATE key_name = key_name;
