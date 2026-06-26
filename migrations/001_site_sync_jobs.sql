CREATE TABLE IF NOT EXISTS site_sync_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    brand VARCHAR(64) NOT NULL,
    source_table VARCHAR(128) NOT NULL,
    source_price_id INT NOT NULL,
    target_site VARCHAR(255) NOT NULL,
    target_table VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    last_error TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_brand_source_price (brand, source_price_id),
    INDEX idx_status_created_at (status, created_at),
    INDEX idx_brand_status (brand, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

