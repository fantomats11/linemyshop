"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ApiError,
  CreateProductVariantInput,
  MeasurementField,
  createProduct,
  ProductDetail,
  uploadProductReferenceImages,
} from "../../../lib/api";
import {
  categoryLabel,
  categoryMeasurementPreset,
  inferGenderFromCategory,
  productCategoryOptions,
} from "../../../lib/categories";
import {
  actionLinkClassName,
  approveButtonClassName,
  ErrorPanel,
  PageHeader,
  rejectButtonClassName,
  SuccessPanel,
  TableShell,
} from "../../../lib/ui";

type VariantDraft = CreateProductVariantInput;

const defaultCategory = "แฟชั่นผู้หญิง>กางเกง";

function measurementDraft(category: string): MeasurementField[] {
  return categoryMeasurementPreset(category).map((label) => ({ label, value: "" }));
}

function applyMeasurementPreset(
  current: MeasurementField[] | undefined,
  category: string,
): MeasurementField[] {
  const previousValues = current ?? [];
  return categoryMeasurementPreset(category).map((label, index) => ({
    label,
    value: previousValues[index]?.value ?? "",
  }));
}

const defaultVariant = (size = "M", category = defaultCategory): VariantDraft => ({
  sku: "",
  barcode: "",
  size,
  measurements: measurementDraft(category),
  price: "",
  sale_price: "",
  stock_on_hand: 0,
  reserved_stock: 0,
  status: "draft",
});

export default function NewProductPage() {
  const [productGroup, setProductGroup] = useState("");
  const [name, setName] = useState("");
  const [color, setColor] = useState("");
  const [gender, setGender] = useState("หญิง");
  const [category, setCategory] = useState(defaultCategory);
  const [description, setDescription] = useState("");
  const [note, setNote] = useState("");
  const [variants, setVariants] = useState<VariantDraft[]>([
    defaultVariant("M", defaultCategory),
    defaultVariant("L", defaultCategory),
    defaultVariant("XL", defaultCategory),
    defaultVariant("XXL", defaultCategory),
  ]);
  const [referenceFiles, setReferenceFiles] = useState<File[]>([]);
  const [createdProduct, setCreatedProduct] = useState<ProductDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateVariant(index: number, patch: Partial<VariantDraft>) {
    setVariants((current) =>
      current.map((variant, currentIndex) =>
        currentIndex === index ? { ...variant, ...patch } : variant,
      ),
    );
  }

  function handleCategoryChange(nextCategory: string) {
    setCategory(nextCategory);
    const inferredGender = inferGenderFromCategory(nextCategory);
    if (inferredGender) {
      setGender(inferredGender);
    }
    setVariants((current) =>
      current.map((variant) => ({
        ...variant,
        measurements: applyMeasurementPreset(variant.measurements, nextCategory),
      })),
    );
  }

  function updateMeasurement(
    variantIndex: number,
    measurementIndex: number,
    value: string,
  ) {
    setVariants((current) =>
      current.map((variant, currentIndex) => {
        if (currentIndex !== variantIndex) {
          return variant;
        }
        const measurements = variant.measurements ?? measurementDraft(category);
        return {
          ...variant,
          measurements: measurements.map((measurement, currentMeasurementIndex) =>
            currentMeasurementIndex === measurementIndex
              ? { ...measurement, value }
              : measurement,
          ),
        };
      }),
    );
  }

  async function handleCreateProduct() {
    setIsSubmitting(true);
    setError(null);
    setCreatedProduct(null);
    try {
      const product = await createProduct({
        product_group: productGroup.trim(),
        name: name.trim(),
        color: color.trim(),
        gender: gender.trim(),
        category: category.trim(),
        description: description.trim() || null,
        note: note.trim() || null,
        status: "draft",
        variants: variants
          .filter((variant) => variant.sku.trim())
          .map((variant) => ({
            ...variant,
            sku: variant.sku.trim(),
            barcode: variant.barcode?.trim() || null,
            size: variant.size.trim(),
            waist: variant.waist?.trim() || undefined,
            hip: variant.hip?.trim() || undefined,
            length: variant.length?.trim() || undefined,
            price: variant.price.trim(),
            sale_price: variant.sale_price?.trim() || null,
            measurements: (variant.measurements ?? [])
              .map((measurement) => ({
                label: measurement.label.trim(),
                value: measurement.value.trim(),
              }))
              .filter((measurement) => measurement.label && measurement.value),
            stock_on_hand: Number(variant.stock_on_hand) || 0,
            reserved_stock: Number(variant.reserved_stock) || 0,
            status: "draft",
          })),
      });

      if (referenceFiles.length > 0) {
        await uploadProductReferenceImages(product.id, referenceFiles);
      }
      setCreatedProduct(product);
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถสร้างสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Product Intake"
        title="เพิ่มสินค้าใหม่"
        description="ให้ทีมงานกรอกข้อมูลสินค้า SKU และแนบรูป reference ก่อนส่งต่อขั้นตอนสร้างรูปขายจริง"
        action={
          <Link href="/products" className={actionLinkClassName}>
            กลับไปรายการสินค้า
          </Link>
        }
      />

      {error ? <ErrorPanel message={error} /> : null}
      {createdProduct ? (
        <SuccessPanel title="สร้างสินค้าแล้ว">
          <div className="space-y-2">
            <p>
              สร้างสินค้า id {createdProduct.id} แล้ว และบันทึกเป็นสถานะแบบร่าง
            </p>
            <Link href={`/products/${createdProduct.id}`} className={approveButtonClassName}>
              ไปหน้ารายละเอียดสินค้า
            </Link>
          </div>
        </SuccessPanel>
      ) : null}

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-zinc-950">ข้อมูลสินค้า</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {[
            ["กลุ่มสินค้า", productGroup, setProductGroup],
            ["ชื่อสินค้า", name, setName],
            ["สี", color, setColor],
          ].map(([label, value, setter]) => (
            <label key={label as string} className="block">
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                {label as string}
              </span>
              <input
                value={value as string}
                onChange={(event) =>
                  (setter as (nextValue: string) => void)(event.target.value)
                }
                className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              />
            </label>
          ))}
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              เพศ
            </span>
            <select
              value={gender}
              onChange={(event) => setGender(event.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            >
              <option value="หญิง">หญิง</option>
              <option value="ชาย">ชาย</option>
              <option value="Unisex">Unisex</option>
              <option value="เด็ก">เด็ก</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              หมวดหมู่
            </span>
            <select
              value={category}
              onChange={(event) => handleCategoryChange(event.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            >
              {productCategoryOptions.map((option) => (
                <option key={option.id} value={option.th}>
                  {categoryLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label className="block sm:col-span-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              รายละเอียด
            </span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            />
          </label>
          <label className="block sm:col-span-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              หมายเหตุ
            </span>
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={2}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            />
          </label>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-zinc-950">SKU และไซซ์</h2>
            <p className="mt-1 text-sm text-zinc-500">
              1 แถวคือ 1 SKU เช่น ไซซ์ M, L, XL พร้อมราคาและสต๊อก
            </p>
          </div>
          <button
            type="button"
            onClick={() =>
              setVariants((current) => [...current, defaultVariant("M", category)])
            }
            className={actionLinkClassName}
          >
            เพิ่ม SKU
          </button>
        </div>
        <TableShell>
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <thead className="bg-zinc-100/80 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3">SKU</th>
                <th className="px-4 py-3">ไซซ์</th>
                {categoryMeasurementPreset(category).map((label) => (
                  <th key={label} className="px-4 py-3">{label}</th>
                ))}
                <th className="px-4 py-3">ราคา</th>
                <th className="px-4 py-3">สต๊อก</th>
                <th className="px-4 py-3 text-right">จัดการ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 bg-white">
              {variants.map((variant, index) => (
                <tr key={index}>
                  {(["sku", "size"] as const).map((field) => (
                    <td key={field} className="px-4 py-3">
                      <input
                        value={String(variant[field] ?? "")}
                        onChange={(event) =>
                          updateVariant(index, { [field]: event.target.value })
                        }
                        className="w-28 rounded-md border border-zinc-200 px-2 py-1.5 text-sm text-zinc-900 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                      />
                    </td>
                  ))}
                  {(variant.measurements ?? measurementDraft(category)).map(
                    (measurement, measurementIndex) => (
                      <td key={measurement.label} className="px-4 py-3">
                        <input
                          aria-label={`${variant.size} ${measurement.label}`}
                          value={measurement.value}
                          onChange={(event) =>
                            updateMeasurement(index, measurementIndex, event.target.value)
                          }
                          className="w-28 rounded-md border border-zinc-200 px-2 py-1.5 text-sm text-zinc-900 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                        />
                      </td>
                    ),
                  )}
                  <td className="px-4 py-3">
                    <input
                      value={String(variant.price ?? "")}
                      onChange={(event) => updateVariant(index, { price: event.target.value })}
                      className="w-28 rounded-md border border-zinc-200 px-2 py-1.5 text-sm text-zinc-900 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <input
                      value={String(variant.stock_on_hand)}
                      onChange={(event) =>
                        updateVariant(index, { stock_on_hand: Number(event.target.value) })
                      }
                      inputMode="numeric"
                      className="w-20 rounded-md border border-zinc-200 px-2 py-1.5 text-sm text-zinc-900 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                    />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() =>
                        setVariants((current) =>
                          current.filter((_variant, currentIndex) => currentIndex !== index),
                        )
                      }
                      className={rejectButtonClassName}
                    >
                      ลบ
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableShell>
      </section>

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-zinc-950">รูปอ้างอิง</h2>
        <p className="mt-1 text-sm text-zinc-500">
          รูปที่อัปโหลดตรงนี้ใช้เป็นต้นแบบสำหรับสร้างรูปสินค้า ยังไม่ถูกใช้เป็นรูปขายจริง
        </p>
        <input
          type="file"
          multiple
          accept="image/*"
          onChange={(event) => setReferenceFiles(Array.from(event.target.files ?? []))}
          className="mt-4 rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 shadow-sm"
        />
      </section>

      <div className="flex justify-end">
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => void handleCreateProduct()}
          className={approveButtonClassName}
        >
          {isSubmitting ? "กำลังสร้างสินค้า..." : "สร้างสินค้าแบบร่าง"}
        </button>
      </div>
    </div>
  );
}
