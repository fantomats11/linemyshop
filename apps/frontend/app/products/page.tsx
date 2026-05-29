"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  approveProduct,
  getProductSyncReadiness,
  hideProduct,
  listProducts,
  ProductLineStatusResponse,
  ProductSyncResponse,
  ProductSummary,
  publishProduct,
  rejectProduct,
  refreshProductLineStatus,
  syncProduct,
} from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { isRenderableProductImageUrl } from "../../lib/images";
import {
  actionLinkClassName,
  approveButtonClassName,
  DisplayStatusBadge,
  EmptyPanel,
  ErrorPanel,
  LoadingPanel,
  PageHeader,
  productionSyncButtonClassName,
  rejectButtonClassName,
  StatCard,
  StatusBadge,
  SuccessPanel,
  syncButtonClassName,
  TableShell,
} from "../../lib/ui";

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<ProductSyncResponse | null>(null);
  const [lineActionResult, setLineActionResult] = useState<ProductLineStatusResponse | null>(null);
  const [pendingProductId, setPendingProductId] = useState<number | null>(null);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortKey, setSortKey] = useState("updated_desc");
  const [page, setPage] = useState(1);
  const [productionSyncProductId, setProductionSyncProductId] = useState<number | null>(null);
  const [productionConfirmText, setProductionConfirmText] = useState("");

  const loadProducts = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setProducts(await listProducts());
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "ไม่สามารถโหลดรายการสินค้าได้",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  async function handleApprove(productId: number) {
    setPendingProductId(productId);
    setError(null);
    setSyncResult(null);
    setLineActionResult(null);
    try {
      await approveProduct(productId);
      await loadProducts();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถอนุมัติสินค้าได้",
      );
    } finally {
      setPendingProductId(null);
    }
  }

  async function handleReject(productId: number) {
    const reason = window.prompt("ระบุเหตุผลในการปฏิเสธสินค้า");
    if (!reason?.trim()) {
      return;
    }

    setPendingProductId(productId);
    setError(null);
    setSyncResult(null);
    setLineActionResult(null);
    try {
      await rejectProduct(productId, reason.trim());
      await loadProducts();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถปฏิเสธสินค้าได้",
      );
    } finally {
      setPendingProductId(null);
    }
  }

  async function runSync(productId: number, confirm?: string) {
    setPendingProductId(productId);
    setError(null);
    setSyncResult(null);
    setLineActionResult(null);
    try {
      setSyncResult(await syncProduct(productId, confirm));
      await loadProducts();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถส่งสินค้าไป LINE MyShop ได้",
      );
    } finally {
      setPendingProductId(null);
    }
  }

  async function handleSyncClick(productId: number) {
    setPendingProductId(productId);
    setError(null);
    setSyncResult(null);
    try {
      const readiness = await getProductSyncReadiness(productId);
      if (!readiness.ready) {
        setError(
          `ยังไม่พร้อมส่ง LINE: ${readiness.errors.join(", ") || "ไม่ทราบสาเหตุ"}`,
        );
        return;
      }
      if (readiness.mock_mode) {
        await runSync(productId);
        return;
      }

      setProductionSyncProductId(productId);
      setProductionConfirmText("");
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถตรวจสอบความพร้อมก่อนส่ง LINE ได้",
      );
    } finally {
      setPendingProductId(null);
    }
  }

  async function handleRefreshLineStatus(productId: number) {
    setPendingProductId(productId);
    setError(null);
    setLineActionResult(null);
    try {
      setLineActionResult(await refreshProductLineStatus(productId));
      await loadProducts();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถ refresh สถานะ LINE ได้",
      );
    } finally {
      setPendingProductId(null);
    }
  }

  async function handlePublish(productId: number) {
    const confirm = window.prompt("พิมพ์ CONFIRM PUBLISH เพื่อเปิดขายบน LINE MyShop");
    if (confirm !== "CONFIRM PUBLISH") {
      return;
    }
    setPendingProductId(productId);
    setError(null);
    setLineActionResult(null);
    try {
      setLineActionResult(await publishProduct(productId, confirm));
      await loadProducts();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถเปิดขายสินค้าได้",
      );
    } finally {
      setPendingProductId(null);
    }
  }

  async function handleHide(productId: number) {
    const confirm = window.prompt("พิมพ์ CONFIRM HIDE เพื่อซ่อนสินค้าบน LINE MyShop");
    if (confirm !== "CONFIRM HIDE") {
      return;
    }
    setPendingProductId(productId);
    setError(null);
    setLineActionResult(null);
    try {
      setLineActionResult(await hideProduct(productId, confirm, "hidden from dashboard"));
      await loadProducts();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถซ่อนสินค้าได้",
      );
    } finally {
      setPendingProductId(null);
    }
  }

  async function handleBatchRefresh() {
    for (const productId of selectedProductIds) {
      await handleRefreshLineStatus(productId);
    }
    setSelectedProductIds([]);
  }

  async function handleBatchSync() {
    const confirm = window.prompt(
      "ถ้าเป็น production mode ให้พิมพ์ CONFIRM PRODUCTION SYNC เพื่อ sync สินค้าที่เลือก",
      "CONFIRM PRODUCTION SYNC",
    );
    if (confirm !== "CONFIRM PRODUCTION SYNC") {
      return;
    }
    setError(null);
    for (const productId of selectedProductIds) {
      setPendingProductId(productId);
      try {
        setSyncResult(await syncProduct(productId, confirm));
      } catch (caughtError) {
        setError(
          caughtError instanceof ApiError
            ? `สินค้า ${productId}: ${caughtError.message}`
            : `สินค้า ${productId}: ไม่สามารถส่ง LINE ได้`,
        );
        break;
      }
    }
    setPendingProductId(null);
    setSelectedProductIds([]);
    await loadProducts();
  }

  async function handleBatchPublish() {
    const confirm = window.prompt("พิมพ์ CONFIRM PUBLISH เพื่อเปิดขายสินค้าที่เลือก");
    if (confirm !== "CONFIRM PUBLISH") {
      return;
    }
    setError(null);
    for (const productId of selectedProductIds) {
      setPendingProductId(productId);
      try {
        setLineActionResult(await publishProduct(productId, confirm));
      } catch (caughtError) {
        setError(
          caughtError instanceof ApiError
            ? `สินค้า ${productId}: ${caughtError.message}`
            : `สินค้า ${productId}: ไม่สามารถเปิดขายได้`,
        );
        break;
      }
    }
    setPendingProductId(null);
    setSelectedProductIds([]);
    await loadProducts();
  }

  async function handleBatchHide() {
    const confirm = window.prompt("พิมพ์ CONFIRM HIDE เพื่อซ่อนสินค้าที่เลือก");
    if (confirm !== "CONFIRM HIDE") {
      return;
    }
    setError(null);
    for (const productId of selectedProductIds) {
      setPendingProductId(productId);
      try {
        setLineActionResult(await hideProduct(productId, confirm, "hidden from batch action"));
      } catch (caughtError) {
        setError(
          caughtError instanceof ApiError
            ? `สินค้า ${productId}: ${caughtError.message}`
            : `สินค้า ${productId}: ไม่สามารถซ่อนได้`,
        );
        break;
      }
    }
    setPendingProductId(null);
    setSelectedProductIds([]);
    await loadProducts();
  }

  async function handleConfirmProductionSync() {
    if (productionSyncProductId === null) {
      return;
    }
    await runSync(productionSyncProductId, "CONFIRM PRODUCTION SYNC");
    setProductionSyncProductId(null);
    setProductionConfirmText("");
  }

  const draftCount = products.filter((product) => product.status === "draft").length;
  const approvedCount = products.filter((product) => product.status === "approved").length;
  const rejectedCount = products.filter((product) => product.status === "rejected").length;
  const totalStock = products.reduce((sum, product) => sum + product.total_stock, 0);
  const pageSize = 10;
  const filteredProducts = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    const filtered = products.filter((product) => {
      const matchesStatus = statusFilter === "all" || product.status === statusFilter;
      const matchesQuery =
        !normalizedQuery ||
        [
          product.id.toString(),
          product.product_group,
          product.name,
          product.color,
          product.gender,
          product.category,
        ]
          .join(" ")
          .toLowerCase()
          .includes(normalizedQuery);

      return matchesStatus && matchesQuery;
    });

    return [...filtered].sort((first, second) => {
      if (sortKey === "name_asc") {
        return first.name.localeCompare(second.name, "th");
      }
      if (sortKey === "stock_desc") {
        return second.total_stock - first.total_stock;
      }
      if (sortKey === "variants_desc") {
        return second.variant_count - first.variant_count;
      }
      if (sortKey === "status_asc") {
        return first.status.localeCompare(second.status);
      }

      return (
        new Date(second.updated_at).getTime() - new Date(first.updated_at).getTime()
      );
    });
  }, [products, searchQuery, sortKey, statusFilter]);
  const totalPages = Math.max(1, Math.ceil(filteredProducts.length / pageSize));
  const paginatedProducts = filteredProducts.slice((page - 1) * pageSize, page * pageSize);
  const selectedCount = selectedProductIds.length;

  useEffect(() => {
    setPage(1);
  }, [searchQuery, statusFilter, sortKey]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="สินค้า"
        title="รายการสินค้า"
        description="ตรวจสินค้า ดูสต๊อก อนุมัติ สร้างรูป และส่งข้อมูลไป LINE MyShop"
        action={
          <Link href="/products/new" className={approveButtonClassName}>
            เพิ่มสินค้าใหม่
          </Link>
        }
      />

      {error ? <ErrorPanel message={error} onRetry={loadProducts} /> : null}

      {syncResult ? (
        <SuccessPanel
          title={syncResult.mock_mode ? "ส่งทดสอบสำเร็จ" : "ส่งขึ้น LINE สำเร็จ"}
        >
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                รหัสงาน
              </dt>
              <dd className="mt-1 font-semibold">{syncResult.sync_job_id}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                LINE Product ID
              </dt>
              <dd className="mt-1 font-semibold">
                {syncResult.external_product_id ?? "-"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                จำนวน SKU ที่ส่ง
              </dt>
              <dd className="mt-1 font-semibold">{syncResult.variants_synced}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                โหมดทดสอบ
              </dt>
              <dd className="mt-1 font-semibold">{syncResult.mock_mode ? "ใช่" : "ไม่ใช่"}</dd>
            </div>
          </dl>
          {syncResult.warnings.length > 0 ? (
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900">
              <div className="font-semibold">คำเตือน</div>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {syncResult.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </SuccessPanel>
      ) : null}

      {lineActionResult ? (
        <SuccessPanel title="อัปเดตสถานะ LINE แล้ว">
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                รหัสสินค้า
              </dt>
              <dd className="mt-1 font-semibold">{lineActionResult.product_id}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                LINE Product ID
              </dt>
              <dd className="mt-1 font-semibold">{lineActionResult.external_product_id}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                หน้าร้าน
              </dt>
              <dd className="mt-1 font-semibold">
                {lineActionResult.is_display ? "เปิดขาย" : "ซ่อนอยู่"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                รหัสงาน
              </dt>
              <dd className="mt-1 font-semibold">{lineActionResult.sync_job_id ?? "-"}</dd>
            </div>
          </dl>
        </SuccessPanel>
      ) : null}

      {isLoading ? (
        <LoadingPanel />
      ) : products.length === 0 ? (
        <EmptyPanel>ยังไม่มีสินค้าในระบบ</EmptyPanel>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard label="สินค้าทั้งหมด" value={products.length} />
            <StatCard label="รออนุมัติ" value={draftCount} tone="amber" />
            <StatCard label="อนุมัติแล้ว" value={approvedCount} tone="emerald" />
            <StatCard label="ปฏิเสธแล้ว" value={rejectedCount} tone="rose" />
            <StatCard label="Stock รวม" value={totalStock} tone="sky" />
          </div>

          <div className="grid gap-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm lg:grid-cols-[1fr_180px_220px]">
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                ค้นหา
              </span>
              <input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="ค้นหาชื่อสินค้า, product_group, สี, หมวดหมู่"
                className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              />
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                สถานะ
              </span>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              >
                <option value="all">ทั้งหมด</option>
                <option value="draft">แบบร่าง</option>
                <option value="approved">อนุมัติแล้ว</option>
                <option value="rejected">ปฏิเสธแล้ว</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                เรียงลำดับ
              </span>
              <select
                value={sortKey}
                onChange={(event) => setSortKey(event.target.value)}
                className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              >
                <option value="updated_desc">อัปเดตล่าสุด</option>
                <option value="name_asc">ชื่อสินค้า A-Z</option>
                <option value="status_asc">สถานะ</option>
                <option value="stock_desc">สต๊อกมากสุด</option>
                <option value="variants_desc">จำนวน SKU มากสุด</option>
              </select>
            </label>
          </div>

          {selectedCount > 0 ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950 shadow-sm">
              <div className="font-semibold">เลือกสินค้า {selectedCount} รายการ</div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void handleBatchRefresh()}
                  className={syncButtonClassName}
                >
                  ดึงสถานะ LINE ที่เลือก
                </button>
                <button
                  type="button"
                  onClick={() => void handleBatchSync()}
                  className={productionSyncButtonClassName}
                >
                  ส่ง LINE ที่เลือก
                </button>
                <button
                  type="button"
                  onClick={() => void handleBatchPublish()}
                  className={approveButtonClassName}
                >
                  เปิดขายที่เลือก
                </button>
                <button
                  type="button"
                  onClick={() => void handleBatchHide()}
                  className={rejectButtonClassName}
                >
                  ซ่อนที่เลือก
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedProductIds([])}
                  className={actionLinkClassName}
                >
                  ล้างการเลือก
                </button>
              </div>
            </div>
          ) : null}

          {filteredProducts.length === 0 ? (
            <EmptyPanel>ไม่พบสินค้าที่ตรงกับเงื่อนไข</EmptyPanel>
          ) : (
            <TableShell>
              <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-100/80 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label="เลือกสินค้าทั้งหน้านี้"
                      checked={
                        paginatedProducts.length > 0
                        && paginatedProducts.every((product) =>
                          selectedProductIds.includes(product.id),
                        )
                      }
                      onChange={(event) => {
                        if (event.target.checked) {
                          setSelectedProductIds((current) =>
                            Array.from(
                              new Set([
                                ...current,
                                ...paginatedProducts.map((product) => product.id),
                              ]),
                            ),
                          );
                        } else {
                          const idsOnPage = new Set(
                            paginatedProducts.map((product) => product.id),
                          );
                          setSelectedProductIds((current) =>
                            current.filter((id) => !idsOnPage.has(id)),
                          );
                        }
                      }}
                    />
                  </th>
                  <th className="px-4 py-3">รูป</th>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">กลุ่มสินค้า</th>
                  <th className="px-4 py-3">ชื่อสินค้า</th>
                  <th className="px-4 py-3">สี</th>
                  <th className="px-4 py-3">เพศ</th>
                  <th className="px-4 py-3">หมวดหมู่</th>
                  <th className="px-4 py-3">สถานะ</th>
                  <th className="px-4 py-3">สถานะส่ง LINE</th>
                  <th className="px-4 py-3">LINE Product ID</th>
                  <th className="px-4 py-3">หน้าร้าน</th>
                  <th className="px-4 py-3">ส่งล่าสุด</th>
                  <th className="px-4 py-3 text-right">จำนวน SKU</th>
                  <th className="px-4 py-3 text-right">สต๊อก</th>
                  <th className="px-4 py-3">อัปเดตล่าสุด</th>
                  <th className="px-4 py-3 text-right">จัดการ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 bg-white">
                {paginatedProducts.map((product) => {
                  const isPending = pendingProductId === product.id;
                  const shouldRenderImage = isRenderableProductImageUrl(product.image_url);
                  return (
                    <tr key={product.id} className="hover:bg-sky-50/40">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          aria-label={`เลือกสินค้า ${product.id}`}
                          checked={selectedProductIds.includes(product.id)}
                          onChange={(event) => {
                            setSelectedProductIds((current) =>
                              event.target.checked
                                ? [...current, product.id]
                                : current.filter((id) => id !== product.id),
                            );
                          }}
                        />
                      </td>
                      <td className="px-4 py-3">
                        {shouldRenderImage ? (
                          <img
                            src={product.image_url ?? ""}
                            alt={product.name}
                            className="h-12 w-12 rounded-md border border-zinc-200 object-cover shadow-sm"
                          />
                        ) : (
                          <div className="flex h-12 w-20 items-center justify-center rounded-md border border-dashed border-zinc-300 bg-zinc-50 px-2 text-center text-[11px] font-medium leading-tight text-zinc-500">
                            ยังไม่มีรูปสินค้า
                          </div>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 font-medium text-zinc-900">
                        {product.id}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                        {product.product_group}
                      </td>
                      <td className="min-w-52 px-4 py-3 text-zinc-900">{product.name}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                        {product.color}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                        {product.gender}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                        {product.category}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <StatusBadge status={product.status} />
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        {product.sync_status ? (
                          <StatusBadge status={product.sync_status} />
                        ) : (
                          <span className="text-zinc-400">ยังไม่มีข้อมูล</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                        {product.external_product_id ?? "-"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <DisplayStatusBadge source={product} />
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-600">
                        {product.last_synced_at ? formatDateTime(product.last_synced_at) : "-"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                        {product.variant_count}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                        {product.total_stock}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-600">
                        {formatDateTime(product.updated_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-2">
                          <Link
                            href={`/products/${product.id}`}
                            className={actionLinkClassName}
                          >
                            ดู
                          </Link>
                          {product.status === "draft" ? (
                            <button
                              type="button"
                              disabled={isPending}
                              onClick={() => void handleApprove(product.id)}
                              className={approveButtonClassName}
                            >
                              อนุมัติ
                            </button>
                          ) : null}
                          {product.status === "draft" || product.status === "approved" ? (
                            <button
                              type="button"
                              disabled={isPending}
                              onClick={() => void handleReject(product.id)}
                              className={rejectButtonClassName}
                            >
                              ปฏิเสธ
                            </button>
                          ) : null}
                          {product.status === "approved" ? (
                            <button
                              type="button"
                              disabled={isPending}
                              onClick={() => void handleSyncClick(product.id)}
                              className={syncButtonClassName}
                            >
                              {isPending ? "กำลังส่ง..." : "ส่ง LINE"}
                            </button>
                          ) : null}
                          {product.external_product_id ? (
                            <>
                              <button
                                type="button"
                                disabled={isPending}
                                onClick={() => void handleRefreshLineStatus(product.id)}
                                className={actionLinkClassName}
                              >
                                ดึงสถานะ
                              </button>
                              {product.is_display ? (
                                <button
                                  type="button"
                                  disabled={isPending}
                                  onClick={() => void handleHide(product.id)}
                                  className={rejectButtonClassName}
                                >
                                  ซ่อน
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  disabled={isPending || product.status !== "approved"}
                                  onClick={() => void handlePublish(product.id)}
                                  className={approveButtonClassName}
                                >
                                  เปิดขาย
                                </button>
                              )}
                            </>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              </table>
            </TableShell>
          )}

          <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-600 shadow-sm sm:flex-row sm:items-center sm:justify-between">
            <div>
              แสดง {paginatedProducts.length} จาก {filteredProducts.length} รายการ
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((currentPage) => Math.max(1, currentPage - 1))}
                className="rounded-md border border-zinc-200 px-3 py-2 font-semibold text-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                ก่อนหน้า
              </button>
              <span className="px-2 font-medium text-zinc-700">
                หน้า {page} / {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() =>
                  setPage((currentPage) => Math.min(totalPages, currentPage + 1))
                }
                className="rounded-md border border-zinc-200 px-3 py-2 font-semibold text-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                ถัดไป
              </button>
            </div>
          </div>
        </>
      )}

      {productionSyncProductId !== null ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/40 px-4">
          <div className="w-full max-w-lg rounded-lg border border-zinc-200 bg-white p-5 shadow-xl">
            <h2 className="text-lg font-semibold text-zinc-950">
              ยืนยันการส่งขึ้น LINE จริง
            </h2>
            <p className="mt-2 text-sm text-zinc-600">
              การทำงานนี้จะส่งข้อมูลสินค้าไปยัง LINE MyShop production จริง
              กรุณาพิมพ์ข้อความด้านล่างให้ตรงก่อนดำเนินการ
            </p>
            <div className="mt-4 rounded-md bg-zinc-100 px-3 py-2 font-mono text-sm font-semibold text-zinc-900">
              CONFIRM PRODUCTION SYNC
            </div>
            <input
              value={productionConfirmText}
              onChange={(event) => setProductionConfirmText(event.target.value)}
              className="mt-3 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              placeholder="พิมพ์ CONFIRM PRODUCTION SYNC"
            />
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setProductionSyncProductId(null);
                  setProductionConfirmText("");
                }}
                className={actionLinkClassName}
              >
                ยกเลิก
              </button>
              <button
                type="button"
                disabled={productionConfirmText !== "CONFIRM PRODUCTION SYNC"}
                onClick={() => void handleConfirmProductionSync()}
                className={productionSyncButtonClassName}
              >
                ยืนยันส่งขึ้น LINE จริง
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
