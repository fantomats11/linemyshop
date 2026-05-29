# Workflow

This document defines the intended business workflow for the LINE MyShop Product Master system.

## Primary Flow

```text
Brief / CSV
-> Validate
-> Import to PostgreSQL
-> Preview in dashboard
-> Approve
-> Sync to LINE MyShop mock
-> Log everything
```

## Roles

### Product Owner

- Provides product briefs.
- Reviews validation results.
- Previews imported products.
- Approves products before sync.
- Confirms any future production API sync.

### System / Agent

- Reads CSV or Excel briefs.
- Validates rows against product master rules.
- Imports valid rows to PostgreSQL.
- Shows products and variants in a dashboard.
- Suggests next actions when data is incomplete or risky.
- Syncs only approved products to the mock LINE MyShop client.
- Logs import, approval, sync, and error events.

## Product Lifecycle

### 1. Draft

Initial state for imported product variants.

- CSV rows use `status = draft`.
- Draft products can be validated and previewed.
- Draft products cannot be synced.

### 2. Validation Passed

The product row has passed required field, type, and business-rule checks.

- Validation should report warnings separately from errors.
- Rows with errors must not be imported as approved.

### 3. Imported

The row has been stored in PostgreSQL as a SKU / variant.

- One CSV row maps to one SKU / one variant.
- Variants are grouped by `product_group`.

### 4. Approved

The product or variant is approved by the product owner.

- Approval is required before sync.
- Approval action must be logged.

### 5. Synced Mock

Approved data has been sent to the mock LINE MyShop client.

- Mock sync result must be logged.
- Mock sync must not call production APIs.

### 6. Production Sync Later

Production sync is intentionally out of scope for the first implementation phase.

- Requires explicit confirmation.
- Requires production credentials.
- Requires additional safety checks.
- Requires clear audit logs.

## Key Constraints

- 1 row = 1 SKU / 1 variant.
- 1 `product_group` = 1 parent product.
- Variant is usually size.
- Stock is per variant.
- Product must be approved before sync.
- API sync must be logged.
- The agent can suggest actions but cannot production-sync without approval.

