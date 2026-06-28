<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

$tableName = 'skupka_gold_prices';
$samples = array('375', '583', '585', '750', '850', '875', '916', '999');

function respond(int $statusCode, array $payload): void
{
    http_response_code($statusCode);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    exit;
}

$secretPath = __DIR__ . '/endpoint_token.php';
if (!is_file($secretPath)) {
    respond(500, array('ok' => false, 'error' => 'endpoint_token_not_found'));
}
$secret = (string)require $secretPath;
if ($secret === '') {
    respond(500, array('ok' => false, 'error' => 'endpoint_token_empty'));
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    respond(405, array('ok' => false, 'error' => 'method_not_allowed'));
}

$rawBody = file_get_contents('php://input');
$timestamp = isset($_SERVER['HTTP_X_GOLD_PRICE_TIMESTAMP'])
    ? (string)$_SERVER['HTTP_X_GOLD_PRICE_TIMESTAMP']
    : '';
$signature = isset($_SERVER['HTTP_X_GOLD_PRICE_SIGNATURE'])
    ? strtolower((string)$_SERVER['HTTP_X_GOLD_PRICE_SIGNATURE'])
    : '';

if ($timestamp === '' || $signature === '') {
    respond(401, array('ok' => false, 'error' => 'missing_signature'));
}
if (!ctype_digit($timestamp)) {
    respond(401, array('ok' => false, 'error' => 'invalid_timestamp'));
}
if (abs(time() - (int)$timestamp) > 300) {
    respond(401, array('ok' => false, 'error' => 'expired_request'));
}

$expectedSignature = hash_hmac('sha256', $timestamp . '.' . $rawBody, $secret);
if (!hash_equals($expectedSignature, $signature)) {
    respond(403, array('ok' => false, 'error' => 'invalid_signature'));
}

$data = json_decode($rawBody, true);
if (!is_array($data)) {
    respond(400, array('ok' => false, 'error' => 'invalid_json'));
}
if (($data['event'] ?? '') !== 'gold_price_updated') {
    respond(400, array('ok' => false, 'error' => 'invalid_event'));
}

$generationId = isset($data['generation_id']) ? (int)$data['generation_id'] : 0;
$kurs = isset($data['kurs']) ? (int)$data['kurs'] : 0;
$createdAt = isset($data['created_at']) ? (string)$data['created_at'] : date('Y-m-d H:i:s');
$prices = $data['brands']['skupka'] ?? null;

if ($generationId <= 0 || $kurs <= 0 || !is_array($prices)) {
    respond(400, array('ok' => false, 'error' => 'missing_required_fields'));
}

$wpLoadPath = dirname(__DIR__) . '/wp-load.php';
if (!is_file($wpLoadPath)) {
    respond(500, array('ok' => false, 'error' => 'wp_load_not_found'));
}

require_once $wpLoadPath;
global $wpdb;

if (!isset($wpdb) || !is_object($wpdb)) {
    respond(500, array('ok' => false, 'error' => 'wordpress_db_not_available'));
}

$createSql = "
CREATE TABLE IF NOT EXISTS `{$tableName}` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `source_price_id` INT NOT NULL,
    `kurs` INT NOT NULL,
    `price_375_from` INT NOT NULL,
    `price_375_to` INT NOT NULL,
    `price_583_from` INT NOT NULL,
    `price_583_to` INT NOT NULL,
    `price_585_from` INT NOT NULL,
    `price_585_to` INT NOT NULL,
    `price_750_from` INT NOT NULL,
    `price_750_to` INT NOT NULL,
    `price_850_from` INT NOT NULL,
    `price_850_to` INT NOT NULL,
    `price_875_from` INT NOT NULL,
    `price_875_to` INT NOT NULL,
    `price_916_from` INT NOT NULL,
    `price_916_to` INT NOT NULL,
    `price_999_from` INT NOT NULL,
    `price_999_to` INT NOT NULL,
    `created_at` DATETIME NOT NULL,
    UNIQUE KEY `uq_source_price_id` (`source_price_id`),
    KEY `idx_created_at` (`created_at`)
) DEFAULT CHARSET=utf8mb4";

if ($wpdb->query($createSql) === false) {
    respond(500, array('ok' => false, 'error' => 'table_create_failed'));
}

$columns = array('source_price_id', 'kurs');
$values = array($generationId, $kurs);
$formats = array('%d', '%d');

foreach ($samples as $sample) {
    foreach (array('from', 'to') as $side) {
        $key = $sample . '_' . $side;
        if (!isset($prices[$key])) {
            respond(400, array('ok' => false, 'error' => 'missing_price_' . $key));
        }
        $columns[] = 'price_' . $key;
        $values[] = (int)$prices[$key];
        $formats[] = '%d';
    }
}

$columns[] = 'created_at';
$values[] = $createdAt;
$formats[] = '%s';

$quotedColumns = array_map(function ($column) {
    return '`' . str_replace('`', '``', $column) . '`';
}, $columns);

$sqlTemplate = 'INSERT INTO `' . $tableName . '` (' . implode(', ', $quotedColumns) . ') VALUES ('
    . implode(', ', $formats) . ') ON DUPLICATE KEY UPDATE `source_price_id` = `source_price_id`';
$preparedSql = $wpdb->prepare($sqlTemplate, $values);

if ($wpdb->query($preparedSql) === false) {
    respond(500, array('ok' => false, 'error' => 'insert_failed'));
}

$publicFields = array();
foreach ($samples as $sample) {
    $publicFields['proba_' . $sample . '_begin'] = (int)$prices[$sample . '_from'];
    $publicFields['proba_' . $sample . '_end'] = (int)$prices[$sample . '_to'];
}

$publicPayload = array(
    'ok' => true,
    'source_price_id' => $generationId,
    'kurs' => $kurs,
    'updated_at' => $createdAt,
    'fields' => $publicFields,
);
$json = json_encode($publicPayload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
$jsonPath = __DIR__ . '/current-gold-prices.json';
$temporaryPath = $jsonPath . '.tmp.' . getmypid();

if ($json === false || file_put_contents($temporaryPath, $json, LOCK_EX) === false) {
    @unlink($temporaryPath);
    respond(500, array('ok' => false, 'error' => 'public_json_write_failed'));
}

if (!@rename($temporaryPath, $jsonPath)) {
    @unlink($temporaryPath);
    respond(500, array('ok' => false, 'error' => 'public_json_replace_failed'));
}

@chmod($jsonPath, 0644);

respond(200, array(
    'ok' => true,
    'source_price_id' => $generationId,
    'public_json_updated' => true,
));
