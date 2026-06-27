# Diamant site endpoint

The OpenCart endpoint receives signed gold-price events and inserts them into
MySQL 5.7. It never accepts the shared secret in an HTTP header or JSON body.

## Files

```text
update-gold-price.php
endpoint_token.example.php
create_diamant_gold_prices.sql
```

## Deploy

1. Upload `update-gold-price.php` to:

```text
/var/www/u0861209/data/www/diamant.uz/api/update-gold-price.php
```

2. Copy `endpoint_token.example.php` as `endpoint_token.php` in the same folder.
Replace its value with a random secret of at least 32 bytes. The real
`endpoint_token.php` is ignored by Git and must not be committed.

3. Put the same secret on the VPS:

```env
DIAMANT_SYNC_ENABLED=1
DIAMANT_ENDPOINT_URL=https://diamant.uz/api/update-gold-price.php
DIAMANT_ENDPOINT_TOKEN=THE_SAME_RANDOM_HMAC_SECRET_AS_ON_THE_SITE
```

4. Run `create_diamant_gold_prices.sql` in the Diamant database.

5. Test from the VPS:

```bash
python scripts/test_diamant_endpoint.py
```

Expected response:

```json
{"ok":true,"source_price_id":1234567890}
```

## Signature protocol

The VPS serializes compact UTF-8 JSON and calculates:

```text
HMAC_SHA256(secret, timestamp + "." + raw_request_body)
```

Headers:

```text
X-Gold-Price-Timestamp: Unix timestamp
X-Gold-Price-Signature: lowercase hexadecimal HMAC
```

The PHP endpoint calculates the signature from the exact raw request body,
uses `hash_equals`, and rejects requests older than five minutes. Server clocks
must be synchronized through NTP.

## Safe rollout order

1. Upload the new PHP endpoint and secret to the site.
2. Put the same secret in VPS `.env`.
3. Pull the new VPS code and restart bot/worker services.
4. Run the test script.
