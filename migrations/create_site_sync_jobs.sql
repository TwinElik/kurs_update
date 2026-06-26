CREATE TABLE IF NOT EXISTS `site_sync_jobs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `brand` VARCHAR(64) NOT NULL,
    `endpoint_url` TEXT NOT NULL,
    `source_price_id` INT NOT NULL,
    `payload_json` LONGTEXT NOT NULL,
    `status` VARCHAR(32) NOT NULL DEFAULT 'pending',
    `attempts` INT NOT NULL DEFAULT 0,
    `last_error` TEXT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    `synced_at` DATETIME NULL,
    UNIQUE KEY `uq_brand_source_price` (`brand`, `source_price_id`),
    INDEX `idx_status_updated_at` (`status`, `updated_at`),
    INDEX `idx_source_price_id` (`source_price_id`)
) DEFAULT CHARSET=utf8mb4;
