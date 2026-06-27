<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');

$tableName = 'diamant_gold_prices';
$samples = array('375', '583', '585', '750', '850', '875', '916', '999');

function respond(int $statusCode, array $payload): void
{
    http_response_code($statusCode);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    respond(405, array('ok' => false, 'error' => 'method_not_allowed'));
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

$sql = 'SELECT * FROM `' . $tableName . '` ORDER BY `id` DESC LIMIT 1';
$result = $mysqli->query($sql);
if (!$result) {
    $mysqli->close();
    respond(500, array('ok' => false, 'error' => 'query_failed'));
}

$row = $result->fetch_assoc();
$result->free();
$mysqli->close();

if (!$row) {
    respond(404, array('ok' => false, 'error' => 'prices_not_found'));
}

$prices = array();
foreach ($samples as $sample) {
    $prices[$sample] = array(
        'from' => (int)$row['price_' . $sample . '_from'],
        'to' => (int)$row['price_' . $sample . '_to'],
    );
}

respond(200, array(
    'ok' => true,
    'source_price_id' => (int)$row['source_price_id'],
    'kurs' => (int)$row['kurs'],
    'created_at' => (string)$row['created_at'],
    'prices' => $prices,
));
