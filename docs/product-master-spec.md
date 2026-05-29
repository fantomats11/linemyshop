# Product Master Spec

This document defines the initial product master model for apparel products imported from CSV or Excel.

## Conceptual Model

### Parent Product

A parent product groups related variants that should appear as one product family.

The parent product is identified by:

- `product_group`

Parent-level fields usually include:

- `product_name`
- `color`
- `gender`
- `category`
- `price`
- `sale_price`
- `image_1`
- `image_2`
- `image_3`
- `description`
- `note`

### Variant / SKU

Each row represents one variant and one SKU.

Variant-level fields include:

- `size`
- `waist`
- `hip`
- `length`
- `sku`
- `barcode`
- `stock`
- `status`

## CSV Columns

The first supported CSV format uses these columns:

```text
product_group,product_name,color,gender,category,price,sale_price,size,waist,hip,length,sku,barcode,stock,image_1,image_2,image_3,description,note,status
```

## Field Definitions

| Field | Scope | Required | Description |
| --- | --- | --- | --- |
| `product_group` | Parent | Yes | Stable group key for one parent product. |
| `product_name` | Parent | Yes | Product display name. |
| `color` | Parent | Yes | Product color, such as `ยีนส์เข้ม`. |
| `gender` | Parent | Yes | Target gender or audience. |
| `category` | Parent | Yes | Product category. |
| `price` | Parent | Yes | Regular selling price. |
| `sale_price` | Parent | No | Discounted price, if available. |
| `size` | Variant | Yes | Variant size, such as `M`, `L`, `XL`, `XXL`. |
| `waist` | Variant | No | Waist measurement range. |
| `hip` | Variant | No | Hip measurement range. |
| `length` | Variant | No | Product length. |
| `sku` | Variant | Yes | Unique SKU. |
| `barcode` | Variant | Yes | Barcode value. Can equal SKU when no barcode exists. |
| `stock` | Variant | Yes | Stock quantity for this variant. |
| `image_1` | Parent | No | Primary image URL. |
| `image_2` | Parent | No | Secondary image URL. |
| `image_3` | Parent | No | Third image URL. |
| `description` | Parent | No | Product description. |
| `note` | Parent / Internal | No | Internal note. |
| `status` | Variant | Yes | Initial workflow state. First import uses `draft`. |

## Initial Statuses

The first implementation should support at least:

- `draft`
- `approved`
- `synced_mock`
- `sync_failed`

Additional statuses can be added later when the approval workflow becomes more detailed.

## Data Ownership

- CSV and Excel files are source inputs.
- PostgreSQL is the local product master database after import.
- LINE MyShop is a downstream channel.
- The local system should remain the source of approval state and sync logs.

