# LINE MyShop Sync Spec

This document defines the first sync design for LINE MyShop.

Production API calls are not part of the first implementation phase.

## Sync Mode

Initial mode:

- Mock by default.
- No production API calls while `LINE_MYSHOP_MOCK_MODE=true`.
- No production credentials required for mock mode.

Future mode:

- Production sync only after explicit confirmation.
- Production sync must use real credentials through environment variables or a secure local secret flow.
- Production sync must have extra audit logging and confirmation prompts.

Implemented API adapter mode:

- `LINE_MYSHOP_MOCK_MODE=false` switches sync to the real API adapter.
- `LINE_MYSHOP_BASE_URL` is required in real mode.
- `LINE_MYSHOP_API_KEY` is required in real mode and is sent as `Authorization: Bearer <key>`.
- Endpoint paths are configurable through environment variables so the backend can match the confirmed LINE MyShop API contract without changing sync workflow code.
- Real API requests and responses are logged to `api_logs` with `service = line_myshop`.

## Sync Eligibility

A product or variant can be synced only when:

- It exists in the local database.
- It has passed validation.
- It has been approved.
- It has not already been successfully synced in the same mode, unless re-sync is explicitly requested.

Draft products cannot be synced.

## Mock Client Behavior

The mock LINE MyShop client should:

- Accept approved parent products and variants.
- Return a simulated success or failure response.
- Never call external APIs.
- Produce deterministic results where possible for testing.
- Log request payloads and responses locally.

## Suggested Payload Shape

The exact LINE MyShop production payload will be confirmed later. The mock payload can start with this internal shape:

```json
{
  "product_group": "jeans-winter-flare-dark",
  "product_name": "กางเกงยีนส์ขาม้าบานกันหนาว",
  "color": "ยีนส์เข้ม",
  "gender": "หญิง",
  "category": "กางเกงยีนส์",
  "price": 1750,
  "sale_price": null,
  "images": [
    "https://example.com/images/jeans-dark-1.jpg",
    "https://example.com/images/jeans-dark-2.jpg",
    "https://example.com/images/jeans-dark-3.jpg"
  ],
  "description": "กางเกงยีนส์ขาม้าบานกันหนาว สี ยีนส์เข้ม",
  "variants": [
    {
      "size": "M",
      "waist": "26-28",
      "hip": "34-36",
      "length": "40",
      "sku": "S25GUM2547",
      "barcode": "S25GUM2547",
      "stock": 0
    }
  ]
}
```

## Logging Requirements

Every sync attempt should create a log entry with:

- Timestamp.
- Sync mode, such as `mock`.
- Product group.
- SKU list.
- Request payload.
- Response payload.
- Result status.
- Error message, if any.
- Actor or process that initiated the sync.

## Safety Requirements

- Mock sync can be run during development.
- Production sync must require explicit confirmation.
- The agent can suggest sync actions but cannot production-sync without approval.
- Failed syncs must not mark products as successfully synced.
