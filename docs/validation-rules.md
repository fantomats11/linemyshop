# Validation Rules

This document defines initial validation rules for imported apparel product briefs.

## Row-Level Rules

Each CSV row must represent exactly one SKU / one variant.

Required fields:

- `product_group`
- `product_name`
- `color`
- `gender`
- `category`
- `price`
- `size`
- `sku`
- `barcode`
- `stock`
- `status`

## Data Type Rules

### Price

- `price` must be numeric.
- `price` must be greater than 0.

### Sale Price

- `sale_price` may be blank.
- If present, `sale_price` must be numeric.
- If present, `sale_price` should be greater than or equal to 0.
- If present, `sale_price` should not be greater than `price`.

### Stock

- `stock` must be an integer.
- `stock` must be greater than or equal to 0.
- Stock is tracked per variant, not only per parent product.

### SKU

- `sku` must be present.
- `sku` must be unique across imported rows.
- `sku` should be stable after import.

### Barcode

- `barcode` must be present.
- If no external barcode exists, `barcode` can equal `sku`.

### Status

- Initial CSV import should use `draft`.
- Rows with unsupported statuses should fail validation.

## Product Group Rules

- One `product_group` maps to one parent product.
- Rows with the same `product_group` should share the same parent-level values:
  - `product_name`
  - `color`
  - `gender`
  - `category`
  - `price`
  - `sale_price`

If parent-level values conflict inside one group, validation should report an error.

## Variant Rules

- Variant is usually represented by `size`.
- The same `product_group` should not contain duplicate `size` values unless a future workflow explicitly supports multiple variants per size.
- Measurement fields such as `waist`, `hip`, and `length` can be stored as text initially because apparel briefs often use ranges.

## Image Rules

- Image URLs may be blank during early import.
- If present, image fields should be valid URLs.
- `image_1` should be treated as the primary image.

## Approval and Sync Rules

- Draft products cannot be synced.
- Product variants must be approved before sync.
- Sync attempts must be logged.
- Mock sync is allowed for approved products.
- Production sync requires explicit confirmation and is out of scope for the first implementation phase.

## Error vs Warning

Validation should separate hard errors from warnings.

Hard errors block import or approval:

- Missing required field.
- Invalid numeric field.
- Duplicate SKU.
- Conflicting parent fields inside one `product_group`.
- Unsupported status.

Warnings do not block import but should be visible:

- Missing optional images.
- Blank description.
- Blank internal note.
- `sale_price` blank.

