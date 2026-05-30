"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  approveProductImage,
  approveProduct,
  createImageGenerationJob,
  createProductImage,
  getProduct,
  getProductImageGenerationBrief,
  getProductSyncReadiness,
  hideProduct,
  ProductLineStatusResponse,
  ProductDetail,
  ImageGenerationJob,
  ProductImageGenerationBrief,
  ProductSyncPreview,
  ProductSyncReadiness,
  ProductSyncResponse,
  previewProductSync,
  promoteReferenceImage,
  publishProduct,
  rejectProduct,
  rejectProductImage,
  refreshProductLineStatus,
  runImageGenerationJob,
  setMainProductImage,
  syncProduct,
  updateProduct,
  updateProductVariant,
  updateVariantInventory,
  uploadGeneratedImagesForJob,
} from "../../../lib/api";
import { formatDateTime, formatMoney, imageTypeLabel, statusLabel } from "../../../lib/format";
import {
  hasBriefImageOnly,
  isApprovedStorefrontImage,
  productImageUrls,
} from "../../../lib/images";
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
} from "../../../lib/ui";

type ProductDetailPageProps = {
  productId: string;
};

export default function ProductDetailClient({ productId }: ProductDetailPageProps) {
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageMessage, setImageMessage] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState("");
  const [imageType, setImageType] = useState("product");
  const [imagePosition, setImagePosition] = useState("1");
  const [syncResult, setSyncResult] = useState<ProductSyncResponse | null>(null);
  const [lineActionResult, setLineActionResult] = useState<ProductLineStatusResponse | null>(null);
  const [syncReadiness, setSyncReadiness] = useState<ProductSyncReadiness | null>(null);
  const [syncPreview, setSyncPreview] = useState<ProductSyncPreview | null>(null);
  const [imageGenerationBrief, setImageGenerationBrief] =
    useState<ProductImageGenerationBrief | null>(null);
  const [imageGenerationJob, setImageGenerationJob] = useState<ImageGenerationJob | null>(null);
  const [selectedImageSlotPositions, setSelectedImageSlotPositions] = useState<number[]>([]);
  const [generatedImageFiles, setGeneratedImageFiles] = useState<File[]>([]);
  const [syncMetadataError, setSyncMetadataError] = useState<string | null>(null);
  const [isSyncMetadataLoading, setIsSyncMetadataLoading] = useState(false);
  const [isProductionConfirmOpen, setIsProductionConfirmOpen] = useState(false);
  const [productionConfirmText, setProductionConfirmText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadProduct = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setProduct(await getProduct(productId));
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "ไม่สามารถโหลดข้อมูลสินค้าได้",
      );
    } finally {
      setIsLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    void loadProduct();
  }, [loadProduct]);

  const loadSyncOperations = useCallback(async () => {
    setIsSyncMetadataLoading(true);
    setSyncMetadataError(null);
    try {
      const [readiness, preview] = await Promise.all([
        getProductSyncReadiness(productId),
        previewProductSync(productId),
      ]);
      setSyncReadiness(readiness);
      setSyncPreview(preview);
    } catch (caughtError) {
      setSyncMetadataError(
        caughtError instanceof Error
          ? caughtError.message
          : "ไม่สามารถโหลดข้อมูลการส่ง LINE ได้",
      );
      setSyncReadiness(null);
      setSyncPreview(null);
    } finally {
      setIsSyncMetadataLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    void loadSyncOperations();
  }, [loadSyncOperations]);

  const loadImageGenerationBrief = useCallback(async () => {
    try {
      setImageGenerationBrief(await getProductImageGenerationBrief(productId));
    } catch {
      setImageGenerationBrief(null);
    }
  }, [productId]);

  useEffect(() => {
    void loadImageGenerationBrief();
  }, [loadImageGenerationBrief]);

  useEffect(() => {
    if (!imageGenerationBrief || selectedImageSlotPositions.length > 0) {
      return;
    }
    const requiredPositions = imageGenerationBrief.slots
      .filter((slot) => slot.required)
      .map((slot) => slot.position);
    setSelectedImageSlotPositions(requiredPositions);
  }, [imageGenerationBrief, selectedImageSlotPositions.length]);

  async function handleApprove() {
    setIsSubmitting(true);
    setError(null);
    setSyncResult(null);
    setLineActionResult(null);
    try {
      await approveProduct(productId);
      await loadProduct();
      await loadImageGenerationBrief();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถอนุมัติสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleReject() {
    const reason = window.prompt("ระบุเหตุผลในการปฏิเสธสินค้า");
    if (!reason?.trim()) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSyncResult(null);
    setLineActionResult(null);
    try {
      await rejectProduct(productId, reason.trim());
      await loadProduct();
      await loadImageGenerationBrief();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถปฏิเสธสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function runSync(confirm?: string) {
    setIsSubmitting(true);
    setError(null);
    setSyncResult(null);
    setLineActionResult(null);
    try {
      setSyncResult(await syncProduct(productId, confirm));
      await loadProduct();
      await loadImageGenerationBrief();
      await loadSyncOperations();
      return true;
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถส่งสินค้าไป LINE MyShop ได้",
      );
      return false;
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSync() {
    setIsSubmitting(true);
    setError(null);
    setSyncResult(null);
    try {
      const readiness = syncReadiness ?? (await getProductSyncReadiness(productId));
      setSyncReadiness(readiness);

      if (!readiness.ready) {
        setError(
          `ยังไม่พร้อมส่ง LINE: ${readiness.errors.join(", ") || "ไม่ทราบสาเหตุ"}`,
        );
        return;
      }

      if (readiness.mock_mode) {
        await runSync();
        return;
      }

      setProductionConfirmText("");
      setIsProductionConfirmOpen(true);
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถตรวจสอบความพร้อมก่อนส่ง LINE ได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleConfirmProductionSync() {
    const didSync = await runSync("CONFIRM PRODUCTION SYNC");
    if (didSync) {
      setIsProductionConfirmOpen(false);
      setProductionConfirmText("");
    }
  }

  async function handleRefreshLineStatus() {
    setIsSubmitting(true);
    setError(null);
    setLineActionResult(null);
    try {
      setLineActionResult(await refreshProductLineStatus(productId));
      await loadProduct();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถ refresh สถานะ LINE ได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePublish() {
    const confirm = window.prompt("พิมพ์ CONFIRM PUBLISH เพื่อเปิดขายบน LINE MyShop");
    if (confirm !== "CONFIRM PUBLISH") {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setLineActionResult(null);
    try {
      setLineActionResult(await publishProduct(productId, confirm));
      await loadProduct();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถเปิดขายสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleHide() {
    const confirm = window.prompt("พิมพ์ CONFIRM HIDE เพื่อซ่อนสินค้าบน LINE MyShop");
    if (confirm !== "CONFIRM HIDE") {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setLineActionResult(null);
    try {
      setLineActionResult(await hideProduct(productId, confirm, "hidden from product detail"));
      await loadProduct();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถซ่อนสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleEditProduct() {
    if (!product) {
      return;
    }
    const name = window.prompt("ชื่อสินค้า", product.name);
    if (name === null) {
      return;
    }
    const description = window.prompt("รายละเอียดสินค้า", product.description ?? "");
    if (description === null) {
      return;
    }
    const note = window.prompt("หมายเหตุ", product.note ?? "");
    if (note === null) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await updateProduct(productId, {
        name: name.trim(),
        description: description.trim() || null,
        note: note.trim() || null,
      });
      await loadProduct();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถแก้ไขข้อมูลสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleEditVariant(variantId: number, currentPrice: string, currentStock: number | null) {
    const price = window.prompt("ราคา", currentPrice);
    if (price === null) {
      return;
    }
    const stock = window.prompt(
      "stock_on_hand",
      currentStock === null ? "0" : String(currentStock),
    );
    if (stock === null) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await updateProductVariant(variantId, { price: price.trim() });
      await updateVariantInventory(variantId, { stock_on_hand: Number(stock) || 0 });
      await loadProduct();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถแก้ไข variant ได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateImage() {
    if (!imageUrl.trim()) {
      setError("กรุณาระบุ URL รูปสินค้า");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setImageMessage(null);
    try {
      await createProductImage(productId, {
        url: imageUrl.trim(),
        image_type: imageType,
        position: Number(imagePosition) || 1,
      });
      setImageUrl("");
      setImageType("product");
      setImagePosition(product ? String(product.images.length + 2) : "1");
      setImageMessage("เพิ่มรูปสินค้าแล้ว รอการตรวจและอนุมัติ");
      await loadProduct();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถเพิ่มรูปสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleApproveImage(imageId: number) {
    const reviewNote = window.prompt("หมายเหตุการอนุมัติรูปสินค้า", "");
    setIsSubmitting(true);
    setError(null);
    setImageMessage(null);
    try {
      await approveProductImage(imageId, reviewNote);
      setImageMessage("อนุมัติรูปสินค้าแล้ว");
      await loadProduct();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถอนุมัติรูปสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRejectImage(imageId: number) {
    const reviewNote = window.prompt("เหตุผลในการปฏิเสธรูปสินค้า", "");
    setIsSubmitting(true);
    setError(null);
    setImageMessage(null);
    try {
      await rejectProductImage(imageId, reviewNote);
      setImageMessage("ปฏิเสธรูปสินค้าแล้ว");
      await loadProduct();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถปฏิเสธรูปสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSetMainImage(imageId: number) {
    setIsSubmitting(true);
    setError(null);
    setImageMessage(null);
    try {
      await setMainProductImage(imageId);
      setImageMessage("ตั้งรูปหลักแล้ว");
      await loadProduct();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถตั้งรูปหลักได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateImageGenerationJob() {
    setIsSubmitting(true);
    setError(null);
    setImageMessage(null);
    try {
      setImageGenerationJob(await createImageGenerationJob(productId));
      setImageMessage("เตรียมงานสร้างรูปแล้ว จากนี้กดสร้างด้วย fal.ai หรืออัปโหลดรูปที่สร้างจากช่องทางอื่นได้");
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถสร้าง image generation job ได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePromoteReferenceImage(imageId: number) {
    setIsSubmitting(true);
    setError(null);
    setImageMessage(null);
    try {
      await promoteReferenceImage(imageId);
      setImageMessage("ใช้รูปอ้างอิงเป็นรูปสินค้าหลักแล้ว");
      await loadProduct();
      await loadImageGenerationBrief();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถใช้รูปอ้างอิงเป็นรูปสินค้าได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  function toggleImageSlot(position: number) {
    setSelectedImageSlotPositions((currentPositions) =>
      currentPositions.includes(position)
        ? currentPositions.filter((currentPosition) => currentPosition !== position)
        : [...currentPositions, position].sort((first, second) => first - second),
    );
  }

  async function handleRunImageGenerationJob() {
    if (selectedImageSlotPositions.length === 0) {
      setError("กรุณาเลือกรูปที่ต้องการสร้างอย่างน้อย 1 รูป");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setImageMessage(null);
    try {
      const job = imageGenerationJob ?? (await createImageGenerationJob(productId));
      setImageGenerationJob(job);
      const completedJob = await runImageGenerationJob(job.id, {
        quality: "medium",
        imageSize: "square",
        outputFormat: "jpeg",
        numImagesPerSlot: 1,
        slotPositions: selectedImageSlotPositions,
        approve: false,
      });
      setImageGenerationJob(completedJob);
      setImageMessage(
        "สร้างรูปด้วย fal.ai แล้ว อัปโหลดเข้า WordPress และบันทึกเป็นรูปแบบร่างแล้ว",
      );
      await loadProduct();
      await loadImageGenerationBrief();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถสร้างรูปด้วย fal.ai ได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUploadGeneratedImages() {
    if (!imageGenerationJob) {
      setError("กรุณาสร้าง image generation job ก่อน");
      return;
    }
    if (generatedImageFiles.length === 0) {
      setError("กรุณาเลือกไฟล์รูปที่สร้างแล้ว");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setImageMessage(null);
    try {
      await uploadGeneratedImagesForJob(imageGenerationJob.id, generatedImageFiles, {
        approve: false,
      });
      setGeneratedImageFiles([]);
      setImageMessage("อัปโหลดรูปเข้า WordPress และบันทึกเป็นรูปแบบร่างแล้ว");
      await loadProduct();
      await loadImageGenerationBrief();
      await loadSyncOperations();
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "ไม่สามารถอัปโหลดรูปที่สร้างแล้วได้",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return <LoadingPanel />;
  }

  if (!product) {
    return (
      <div className="space-y-4">
        <ErrorPanel message={error ?? "ไม่พบข้อมูลสินค้า"} onRetry={loadProduct} />
        <Link href="/products" className={actionLinkClassName}>
          กลับไปรายการสินค้า
        </Link>
      </div>
    );
  }

  const totalStock = product.variants.reduce(
    (sum, variant) => sum + (variant.inventory?.stock_on_hand ?? 0),
    0,
  );
  const reservedStock = product.variants.reduce(
    (sum, variant) => sum + (variant.inventory?.reserved_stock ?? 0),
    0,
  );
  const availableStock = product.variants.reduce(
    (sum, variant) => sum + (variant.inventory?.available_stock ?? 0),
    0,
  );
  const approvedStorefrontImages = product.images.filter(isApprovedStorefrontImage);
  const renderableImageUrls = productImageUrls(product.images.map((image) => image.url));
  const hasOnlyBriefImages = hasBriefImageOnly(product.images.map((image) => image.url));
  const measurementLabels = product.variants[0]?.measurements.map(
    (measurement) => measurement.label,
  ) ?? ["เอว", "สะโพก", "ความยาว"];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`กลุ่มสินค้า: ${product.product_group}`}
        title={product.name}
        description="ตรวจรายละเอียดสินค้า รูปภาพ SKU และสต๊อกก่อนอนุมัติหรือส่งขึ้น LINE"
        action={
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={product.status} />
            <DisplayStatusBadge source={product} />
          </div>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Link href="/products" className={actionLinkClassName}>
          กลับไปรายการสินค้า
        </Link>
        {product.status === "draft" ? (
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => void handleApprove()}
            className={approveButtonClassName}
          >
            อนุมัติ
          </button>
        ) : null}
        {product.status === "draft" || product.status === "approved" ? (
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => void handleReject()}
            className={rejectButtonClassName}
          >
            ปฏิเสธ
          </button>
        ) : null}
        {product.status === "approved" ? (
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => void handleSync()}
            className={
              syncReadiness?.mock_mode === false
                ? productionSyncButtonClassName
                : syncButtonClassName
            }
          >
            {isSubmitting
              ? "กำลังส่ง..."
              : syncReadiness?.mock_mode
                ? "ส่งทดสอบ"
                : "ส่ง LINE"}
          </button>
        ) : null}
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => void handleEditProduct()}
          className={actionLinkClassName}
        >
          แก้ไขข้อมูล
        </button>
        {product.external_product_id ? (
          <>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => void handleRefreshLineStatus()}
              className={actionLinkClassName}
            >
              ดึงสถานะ LINE
            </button>
            {product.is_display ? (
              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => void handleHide()}
                className={rejectButtonClassName}
              >
                ซ่อนบน LINE
              </button>
            ) : (
              <button
                type="button"
                disabled={isSubmitting || product.status !== "approved"}
                onClick={() => void handlePublish()}
                className={approveButtonClassName}
              >
                เปิดขายบน LINE
              </button>
            )}
          </>
        ) : null}
      </div>

      {error ? <ErrorPanel message={error} onRetry={loadProduct} /> : null}

      {imageMessage ? (
        <SuccessPanel title="อัปเดตรูปสินค้าแล้ว">{imageMessage}</SuccessPanel>
      ) : null}

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
                สถานะ
              </dt>
              <dd className="mt-1 font-semibold">{lineActionResult.status}</dd>
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

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="จำนวน SKU" value={product.variants.length} />
        <StatCard label="รูปสินค้าที่อนุมัติ" value={approvedStorefrontImages.length} tone="sky" />
        <StatCard label="สต๊อกทั้งหมด" value={totalStock} tone="emerald" />
        <StatCard label="จองไว้" value={reservedStock} tone="amber" />
        <StatCard label="พร้อมขาย" value={availableStock} tone="zinc" />
      </div>

      <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-zinc-950">ข้อมูลสินค้า</h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs font-medium text-zinc-500">ID</dt>
            <dd className="mt-1 text-sm text-zinc-900">{product.id}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">สี</dt>
            <dd className="mt-1 text-sm text-zinc-900">{product.color}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">เพศ</dt>
            <dd className="mt-1 text-sm text-zinc-900">{product.gender}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">หมวดหมู่</dt>
            <dd className="mt-1 text-sm text-zinc-900">{product.category}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">LINE Product ID</dt>
            <dd className="mt-1 text-sm text-zinc-900">
              {product.external_product_id ?? "-"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">สถานะส่ง LINE</dt>
            <dd className="mt-1">
              {product.sync_status ? (
                <StatusBadge status={product.sync_status} />
              ) : (
                <span className="text-sm text-zinc-500">ยังไม่มีข้อมูล</span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">สถานะหน้าร้าน</dt>
            <dd className="mt-1">
              <DisplayStatusBadge source={product} />
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-zinc-500">ส่ง LINE ล่าสุด</dt>
            <dd className="mt-1 text-sm text-zinc-900">
              {product.last_synced_at ? formatDateTime(product.last_synced_at) : "-"}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs font-medium text-zinc-500">รายละเอียด</dt>
            <dd className="mt-1 text-sm text-zinc-900">{product.description ?? "-"}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs font-medium text-zinc-500">หมายเหตุ</dt>
            <dd className="mt-1 text-sm text-zinc-900">{product.note ?? "-"}</dd>
          </div>
        </dl>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-zinc-950">
                ความพร้อมก่อนส่งขึ้น LINE
              </h2>
              <p className="mt-1 text-sm text-zinc-500">
                ตรวจว่าสินค้านี้มีข้อมูลและรูปครบพอสำหรับส่งขึ้น LINE MyShop หรือยัง
              </p>
            </div>
            <button
              type="button"
              disabled={isSyncMetadataLoading}
              onClick={() => void loadSyncOperations()}
              className={actionLinkClassName}
            >
              รีเฟรช
            </button>
          </div>

          {isSyncMetadataLoading ? (
            <div className="mt-4 text-sm text-zinc-500">กำลังตรวจความพร้อม...</div>
          ) : syncMetadataError ? (
            <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
              {syncMetadataError}
            </div>
          ) : syncReadiness ? (
            <div className="mt-4 space-y-4">
              <dl className="grid gap-3 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium text-zinc-500">โหมด</dt>
                  <dd className="mt-1 text-sm font-semibold text-zinc-900">
                    {syncReadiness.mock_mode ? "โหมดทดสอบ" : "โหมดส่งจริง"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-zinc-500">สถานะความพร้อม</dt>
                  <dd className="mt-1">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${
                        syncReadiness.ready
                          ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
                          : "bg-rose-50 text-rose-800 ring-rose-200"
                      }`}
                    >
                      {syncReadiness.ready ? "พร้อมส่งขึ้น LINE" : "ยังไม่พร้อมส่ง"}
                    </span>
                  </dd>
                </div>
              </dl>
              {syncReadiness.errors.length > 0 ? (
                <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                  <div className="font-semibold">ข้อผิดพลาด</div>
                  <ul className="mt-1 list-disc space-y-1 pl-5">
                    {syncReadiness.errors.map((syncError) => (
                      <li key={syncError}>{syncError}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {syncReadiness.warnings.length > 0 ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  <div className="font-semibold">คำเตือน</div>
                  <ul className="mt-1 list-disc space-y-1 pl-5">
                    {syncReadiness.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mt-4 text-sm text-zinc-500">ยังไม่มีข้อมูลความพร้อม</div>
          )}
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-zinc-950">พรีวิวก่อนส่ง LINE</h2>
          <p className="mt-1 text-sm text-zinc-500">
            ดูข้อมูลที่จะส่งออกก่อนกดส่งจริง ใช้สำหรับตรวจสอบเมื่อมีปัญหา
          </p>

          {isSyncMetadataLoading ? (
            <div className="mt-4 text-sm text-zinc-500">กำลังโหลดพรีวิว...</div>
          ) : syncMetadataError ? (
            <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
              {syncMetadataError}
            </div>
          ) : syncPreview ? (
            <div className="mt-4 space-y-4">
              <dl className="grid gap-3 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium text-zinc-500">งานที่จะทำ</dt>
                  <dd className="mt-1 text-sm text-zinc-900">{syncPreview.action}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-zinc-500">Method</dt>
                  <dd className="mt-1 text-sm text-zinc-900">{syncPreview.method}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-xs font-medium text-zinc-500">Endpoint</dt>
                  <dd className="mt-1 break-all text-sm text-zinc-900">
                    {syncPreview.endpoint}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-zinc-500">โหมด</dt>
                  <dd className="mt-1 text-sm font-semibold text-zinc-900">
                    {syncPreview.mock_mode ? "โหมดทดสอบ" : "โหมดส่งจริง"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-zinc-500">ความพร้อม</dt>
                  <dd className="mt-1 text-sm text-zinc-900">
                    {syncPreview.ready ? "พร้อม" : "ยังไม่พร้อม"}
                  </dd>
                </div>
              </dl>

              {syncPreview.errors.length > 0 ? (
                <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                  <div className="font-semibold">ข้อผิดพลาด</div>
                  <ul className="mt-1 list-disc space-y-1 pl-5">
                    {syncPreview.errors.map((syncError) => (
                      <li key={syncError}>{syncError}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {syncPreview.warnings.length > 0 ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  <div className="font-semibold">คำเตือน</div>
                  <ul className="mt-1 list-disc space-y-1 pl-5">
                    {syncPreview.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  ข้อมูลภายในระบบ
                </div>
                <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-50">
                  {JSON.stringify(syncPreview.internal_payload, null, 2)}
                </pre>
              </div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  ข้อมูลที่จะส่งให้ LINE
                </div>
                <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-50">
                  {syncPreview.outbound_payload
                    ? JSON.stringify(syncPreview.outbound_payload, null, 2)
                    : "-"}
                </pre>
              </div>
            </div>
          ) : (
            <div className="mt-4 text-sm text-zinc-500">ยังไม่มีข้อมูลพรีวิว</div>
          )}
        </div>
      </section>

      {imageGenerationBrief ? (
        <section className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-zinc-950">
                แผนสร้างรูปสินค้า
              </h2>
              <p className="mt-1 text-sm text-zinc-500">
                ชุดรูปที่ระบบแนะนำให้สร้างจากรูปอ้างอิง ก่อนตรวจอนุมัติและส่งขึ้น LINE
              </p>
            </div>
            <span
              className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${
                imageGenerationBrief.ready
                  ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
                  : "bg-rose-50 text-rose-800 ring-rose-200"
              }`}
            >
              {imageGenerationBrief.ready ? "พร้อมสร้างรูป" : "ยังไม่พร้อม"}
            </span>
          </div>
          {imageGenerationBrief.warnings.length > 0 ? (
            <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {imageGenerationBrief.warnings.join(", ")}
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm">
            <div>
              <div className="font-semibold text-zinc-950">
                เลือกรูปที่จะสร้างด้วย fal.ai
              </div>
              <div className="mt-1 text-xs text-zinc-500">
                เลือกอยู่ {selectedImageSlotPositions.length} จาก {imageGenerationBrief.slots.length} รูป
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() =>
                  setSelectedImageSlotPositions(
                    imageGenerationBrief.slots
                      .filter((slot) => slot.required)
                      .map((slot) => slot.position),
                  )
                }
                className={actionLinkClassName}
              >
                เลือกเฉพาะรูปจำเป็น
              </button>
              <button
                type="button"
                onClick={() =>
                  setSelectedImageSlotPositions(
                    imageGenerationBrief.slots.map((slot) => slot.position),
                  )
                }
                className={actionLinkClassName}
              >
                เลือกทั้งหมด
              </button>
            </div>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-7">
            {imageGenerationBrief.slots.map((slot) => (
              <label
                key={slot.position}
                className={`block rounded-lg border p-3 ${
                  selectedImageSlotPositions.includes(slot.position)
                    ? "border-sky-300 bg-sky-50"
                    : "border-zinc-200 bg-zinc-50"
                }`}
              >
                <div className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    checked={selectedImageSlotPositions.includes(slot.position)}
                    onChange={() => toggleImageSlot(slot.position)}
                    className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-sky-600 focus:ring-sky-500"
                  />
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-zinc-500">
                      รูป {slot.position} · {imageTypeLabel(slot.image_type)}
                    </div>
                    <div className="mt-1 text-sm font-semibold text-zinc-950">
                      {slot.title}
                    </div>
                  </div>
                </div>
                <div className="mt-2 line-clamp-4 text-xs leading-5 text-zinc-600">
                  {slot.prompt}
                </div>
                <div className="mt-2 text-xs font-medium text-zinc-500">
                  {slot.required ? "จำเป็น" : "เสริม"}
                </div>
              </label>
            ))}
          </div>
          <div className="mt-5 rounded-lg border border-zinc-200 bg-zinc-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-zinc-950">
                  สร้างรูปสำหรับหน้าร้าน
                </div>
              <p className="mt-1 text-sm text-zinc-500">
                  สร้างภาพผ่าน fal.ai จากรูปอ้างอิง แล้วบันทึกเป็นรูปแบบร่างให้ตรวจอีกครั้ง
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={isSubmitting || !imageGenerationBrief.ready}
                  onClick={() => void handleCreateImageGenerationJob()}
                  className={syncButtonClassName}
                >
                  เตรียมงานสร้างรูป
                </button>
                <button
                  type="button"
                  disabled={
                    isSubmitting ||
                    !imageGenerationBrief.ready ||
                    selectedImageSlotPositions.length === 0
                  }
                  onClick={() => void handleRunImageGenerationJob()}
                  className={productionSyncButtonClassName}
                >
                  สร้าง {selectedImageSlotPositions.length} รูปด้วย fal.ai
                </button>
              </div>
            </div>
            {imageGenerationJob ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-950">
                  งานสร้างรูป #{imageGenerationJob.id} · {statusLabel(imageGenerationJob.status)}
                </div>
                <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    onChange={(event) =>
                      setGeneratedImageFiles(Array.from(event.target.files ?? []))
                    }
                    className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm"
                  />
                  <button
                    type="button"
                    disabled={isSubmitting || generatedImageFiles.length === 0}
                    onClick={() => void handleUploadGeneratedImages()}
                    className={approveButtonClassName}
                  >
                    อัปโหลดรูปที่สร้างไว้แล้ว
                  </button>
                </div>
                <p className="text-xs text-zinc-500">
                  เลขงานคือรหัสคิวสร้างรูป ไม่ใช่ลำดับรูปสินค้า ปุ่ม fal.ai จะสร้างรูปตามแผนด้วยค่า medium/square/jpeg ส่วนช่องอัปโหลดใช้เมื่อมีไฟล์จากช่องทางอื่น รูปทั้งหมดจะเป็นแบบร่าง ต้องตรวจอนุมัติและตั้งรูปหลักก่อนส่งขึ้น LINE
                </p>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold text-zinc-950">รูปภาพสินค้า</h2>
          <p className="mt-1 text-sm text-zinc-500">เรียงตามลำดับรูปที่จะใช้บนหน้าร้าน</p>
        </div>
        {approvedStorefrontImages.length === 0 ? (
          <EmptyPanel>
            <div className="font-medium text-zinc-700">ยังไม่มีรูปสินค้า</div>
            {hasOnlyBriefImages ? (
              <div className="mt-1 text-xs text-zinc-500">
                มีเฉพาะภาพ brief สำหรับอ้างอิง
              </div>
            ) : null}
          </EmptyPanel>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {approvedStorefrontImages.map((image) => (
              <div
                key={image.id}
                className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm"
              >
                <img
                  src={image.url}
                  alt={`${product.name} รูปที่ ${image.position}`}
                  className="aspect-square w-full object-cover"
                />
                <div className="border-t border-zinc-100 px-3 py-2 text-xs font-medium text-zinc-500">
                  ลำดับรูป: {image.position}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold text-zinc-950">จัดการรูปสินค้า</h2>
          <p className="mt-1 text-sm text-zinc-500">
            เพิ่ม URL รูปสินค้าจริงและตรวจรูปก่อนนำไปใช้กับหน้าร้าน
          </p>
        </div>

        <div className="grid gap-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm lg:grid-cols-[1fr_160px_120px_auto]">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              URL รูปภาพ
            </span>
            <input
              value={imageUrl}
              onChange={(event) => setImageUrl(event.target.value)}
              placeholder="https://... หรือ /product-images/..."
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              ประเภทรูป
            </span>
            <select
              value={imageType}
              onChange={(event) => setImageType(event.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            >
              <option value="product">product</option>
              <option value="lifestyle">lifestyle</option>
              <option value="detail">detail</option>
              <option value="size_chart">size_chart</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              ลำดับรูป
            </span>
            <input
              value={imagePosition}
              onChange={(event) => setImagePosition(event.target.value)}
              inputMode="numeric"
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => void handleCreateImage()}
              className={approveButtonClassName}
            >
              เพิ่มรูป
            </button>
          </div>
        </div>

        <TableShell>
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <thead className="bg-zinc-100/80 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3">ตัวอย่าง</th>
                <th className="px-4 py-3">URL</th>
                <th className="px-4 py-3">ประเภท</th>
                <th className="px-4 py-3">สถานะ</th>
                <th className="px-4 py-3">รูปหลัก</th>
                <th className="px-4 py-3">หมายเหตุ</th>
                <th className="px-4 py-3 text-right">จัดการ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 bg-white">
              {product.images.map((image) => {
                const canPreview = renderableImageUrls.includes(image.url);
                const canApprove = image.image_type !== "brief" && image.status !== "approved";
                const canPromoteReference =
                  image.image_type === "brief" && image.status !== "rejected";
                const canSetMain =
                  image.image_type === "product" && image.status === "approved" && !image.is_main;
                return (
                  <tr key={image.id} className="hover:bg-sky-50/40">
                    <td className="px-4 py-3">
                      {canPreview ? (
                        <img
                          src={image.url}
                          alt={`รูปสินค้า ${image.position}`}
                          className="h-12 w-12 rounded-md border border-zinc-200 object-cover shadow-sm"
                        />
                      ) : (
                        <div className="flex h-12 w-20 items-center justify-center rounded-md border border-dashed border-zinc-300 bg-zinc-50 px-2 text-center text-[11px] font-medium leading-tight text-zinc-500">
                          {image.image_type === "brief" ? "ภาพ brief" : "ไม่มี preview"}
                        </div>
                      )}
                    </td>
                    <td className="min-w-80 px-4 py-3 text-zinc-700">{image.url}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                      {imageTypeLabel(image.image_type)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <StatusBadge status={image.status} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                      {image.is_main ? "ใช่" : "-"}
                    </td>
                    <td className="min-w-48 px-4 py-3 text-zinc-700">
                      {image.review_note ?? "-"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        {canPromoteReference ? (
                          <button
                            type="button"
                            disabled={isSubmitting}
                            onClick={() => void handlePromoteReferenceImage(image.id)}
                            className={approveButtonClassName}
                          >
                            ใช้เป็นรูปสินค้า
                          </button>
                        ) : null}
                        {canApprove ? (
                          <button
                            type="button"
                            disabled={isSubmitting}
                            onClick={() => void handleApproveImage(image.id)}
                            className={approveButtonClassName}
                          >
                            อนุมัติรูป
                          </button>
                        ) : null}
                        {image.status !== "rejected" ? (
                          <button
                            type="button"
                            disabled={isSubmitting}
                            onClick={() => void handleRejectImage(image.id)}
                            className={rejectButtonClassName}
                          >
                            ปฏิเสธรูป
                          </button>
                        ) : null}
                        {canSetMain ? (
                          <button
                            type="button"
                            disabled={isSubmitting}
                            onClick={() => void handleSetMainImage(image.id)}
                            className={syncButtonClassName}
                          >
                            ตั้งรูปหลัก
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableShell>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold text-zinc-950">SKU และสต๊อก</h2>
          <p className="mt-1 text-sm text-zinc-500">ข้อมูล SKU, ราคา และ stock แยกตามไซซ์</p>
        </div>
        {product.variants.length === 0 ? (
          <EmptyPanel>ยังไม่มี variant</EmptyPanel>
        ) : (
          <TableShell>
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-100/80 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-4 py-3">SKU</th>
                  <th className="px-4 py-3">Barcode</th>
                  <th className="px-4 py-3">Size</th>
                  {measurementLabels.map((label) => (
                    <th key={label} className="px-4 py-3">{label}</th>
                  ))}
                  <th className="px-4 py-3 text-right">Price</th>
                  <th className="px-4 py-3 text-right">Sale Price</th>
                  <th className="px-4 py-3">สถานะ</th>
                  <th className="px-4 py-3 text-right">สต๊อกทั้งหมด</th>
                  <th className="px-4 py-3 text-right">จองไว้</th>
                  <th className="px-4 py-3 text-right">พร้อมขาย</th>
                  <th className="px-4 py-3 text-right">จัดการ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 bg-white">
                {product.variants.map((variant) => (
                  <tr key={variant.id} className="hover:bg-sky-50/40">
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-zinc-900">
                      {variant.sku}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                      {variant.barcode ?? "-"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-700">
                      {variant.size}
                    </td>
                    {measurementLabels.map((label) => (
                      <td key={label} className="whitespace-nowrap px-4 py-3 text-zinc-700">
                        {variant.measurements.find((measurement) => measurement.label === label)
                          ?.value ?? "-"}
                      </td>
                    ))}
                    <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                      {formatMoney(variant.price)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                      {formatMoney(variant.sale_price)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <StatusBadge status={variant.status} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                      {variant.inventory?.stock_on_hand ?? "-"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                      {variant.inventory?.reserved_stock ?? "-"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-zinc-700">
                      {variant.inventory?.available_stock ?? "-"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right">
                      <button
                        type="button"
                        disabled={isSubmitting}
                        onClick={() =>
                          void handleEditVariant(
                            variant.id,
                            variant.price,
                            variant.inventory?.stock_on_hand ?? null,
                          )
                        }
                        className={actionLinkClassName}
                      >
                        แก้ราคา/stock
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableShell>
        )}
      </section>

      {isProductionConfirmOpen ? (
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
                  setIsProductionConfirmOpen(false);
                  setProductionConfirmText("");
                }}
                className={actionLinkClassName}
              >
                ยกเลิก
              </button>
              <button
                type="button"
                disabled={
                  isSubmitting || productionConfirmText !== "CONFIRM PRODUCTION SYNC"
                }
                onClick={() => void handleConfirmProductionSync()}
                className={productionSyncButtonClassName}
              >
                {isSubmitting ? "กำลังส่ง..." : "ยืนยันส่งขึ้น LINE จริง"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
