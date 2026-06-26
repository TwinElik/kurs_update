<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

$secret = 'CHANGE_ME_SECRET_TOKEN';
$tableName = 'diamant_gold_prices';
$samples = array('375', '583', '585', '750', '850', '875', '916', '999');

function respond(int $statusCode, array $payload): void
{
    http_response_code($statusCode);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    respond(405, array('ok' => false, 'error' => 'method_not_allowed'));
}

$rawBody = file_get_contents('php://input');
$data = json_decode($rawBody, true);

if (!is_array($data)) {
    respond(400, array('ok' => false, 'error' => 'invalid_json'));
}

$headerToken = isset($_SERVER['HTTP_X_GOLD_PRICE_TOKEN']) ? (string)$_SERVER['HTTP_X_GOLD_PRICE_TOKEN'] : '';
$bodyToken = isset($data['token']) ? (string)$data['token'] : '';
$token = $headerToken !== '' ? $headerToken : $bodyToken;

if (!hash_equals($secret, $token)) {
    respond(403, array('ok' => false, 'error' => 'forbidden'));
}

if (($data['event'] ?? '') !== 'gold_price_updated') {
    respond(400, array('ok' => false, 'error' => 'invalid_event'));
}

$generationId = isset($data['generation_id']) ? (int)$data['generation_id'] : 0;
$kurs = isset($data['kurs']) ? (int)$data['kurs'] : 0;
$createdAt = isset($data['created_at']) ? (string)$data['created_at'] : date('Y-m-d H:i:s');
$prices = $data['brands']['diamant'] ?? null;

if ($generationId <= 0 || $kurs <= 0 || !is_array($prices)) {
    respond(400, array('ok' => false, 'error' => 'missing_required_fields'));
}

$siteRoot = dirname(__DIR__);
$configPath = $siteRoot . '/config.php';

if (!is_file($configPath)) {
    respond(500, array('ok' => false, 'error' => 'config_not_found'));
}

require_once $configPath;

$dbPort = defined('DB_PORT') ? (int)DB_PORT : 3306;
$mysqli = @new mysqli(DB_HOSTNAME, DB_USERNAME, DB_PASSWORD, DB_DATABASE, $dbPort);

if ($mysqli->connect_errno) {
    respond(500, array('ok' => false, 'error' => 'db_connect_failed'));
}

$mysqli->set_charset('utf8mb4');

$createSql = "
CREATE TABLE IF NOT EXISTS `{$tableName}` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `source_price_id` INT NOT NULL,
    `kurs` INT NOT NULL,
    `375_from` INT NOT NULL,
    `375_to` INT NOT NULL,
    `583_from` INT NOT NULL,
    `583_to` INT NOT NULL,
    `585_from` INT NOT NULL,
    `585_to` INT NOT NULL,
    `750_from` INT NOT NULL,
    `750_to` INT NOT NULL,
    `850_from` INT NOT NULL,
    `850_to` INT NOT NULL,
    `875_from` INT NOT NULL,
    `875_to` INT NOT NULL,
    `916_from` INT NOT NULL,
    `916_to` INT NOT NULL,
    `999_from` INT NOT NULL,
    `999_to` INT NOT NULL,
    `created_at` DATETIME NOT NULL,
    UNIQUE KEY `uq_source_price_id` (`source_price_id`),
    INDEX `idx_created_at` (`created_at`)
)";

if (!$mysqli->query($createSql)) {
    respond(500, array('ok' => false, 'error' => 'table_create_failed'));
}

$columns = array('source_price_id', 'kurs');
$values = array($generationId, $kurs);
$types = 'ii';

foreach ($samples as $sample) {
    foreach (array('from', 'to') as $side) {
        $key = $sample . '_' . $side;
        if (!isset($prices[$key])) {
            respond(400, array('ok' => false, 'error' => 'missing_price_' . $key));
        }
        $columns[] = $key;
        $values[] = (int)$prices[$key];
        $types .= 'i';
    }
}

$columns[] = 'created_at';
$values[] = $createdAt;
$types .= 's';

$quotedColumns = array_map(function ($column) {
    return '`' . str_replace('`', '``', $column) . '`';
}, $columns);

$placeholders = implode(', ', array_fill(0, count($values), '?'));
$sql = 'INSERT INTO `' . $tableName . '` (' . implode(', ', $quotedColumns) . ') VALUES (' . $placeholders . ')
        ON DUPLICATE KEY UPDATE `source_price_id` = `source_price_id`';

$stmt = $mysqli->prepare($sql);

if (!$stmt) {
    respond(500, array('ok' => false, 'error' => 'prepare_failed'));
}

$refs = array();
$refs[] = $types;
foreach ($values as $index => $value) {
    $refs[] = &$values[$index];
}

call_user_func_array(array($stmt, 'bind_param'), $refs);

if (!$stmt->execute()) {
    respond(500, array('ok' => false, 'error' => 'insert_failed'));
}

$stmt->close();
$mysqli->close();

respond(200, array('ok' => true, 'source_price_id' => $generationId));
